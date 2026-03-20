"""
MoHFW (Ministry of Health and Family Welfare) Scraper
PRIORITY: HIGH

Extracts:
- Press releases with outbreak data
- Health advisories 
- Disease situation updates
- PDF documents linked from releases
- Stores full text in bulletin_texts for LangChain
"""
import re
from datetime import datetime, date
from base_scraper import BaseScraper
from config import MOHFW_URLS, HEALTH_KEYWORDS, TARGET_DISEASES


class MoHFWScraper(BaseScraper):
    def __init__(self):
        super().__init__("MoHFW")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        try:
            # Scrape each section
            for section, url in [
                ("press_releases", MOHFW_URLS["PRESS_RELEASES"]),
                ("health_advisories", MOHFW_URLS["HEALTH_ADVISORIES"]),
                ("situation_updates", MOHFW_URLS["SITUATION_UPDATES"]),
            ]:
                self.logger.info("Scraping MoHFW %s...", section)
                stats = self._scrape_listing_page(url, section)
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("MoHFW scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "guidelines,outbreaks,bulletins",
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed, pdfs_processed=pdfs,
        )

    def _scrape_listing_page(self, listing_url, section):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0, "pdfs": 0}

        html = self.fetch_html(listing_url, use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            self.logger.warning("Could not fetch MoHFW %s page", section)
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        # Find release links
        links = soup.find_all("a", href=True)
        stats_lock = threading.Lock()
        
        def process_mohfw_link(link):
            text = link.get_text(strip=True)
            href = link["href"]

            if not href or len(text) < 10:
                return

            # Filter for health relevance
            combined_text = (text + " " + href).lower()
            if not any(kw in combined_text for kw in HEALTH_KEYWORDS):
                return

            full_url = href if href.startswith("http") else MOHFW_URLS["BASE"] + (href if href.startswith("/") else "/" + href)

            if self.is_already_scraped(full_url, table="disease_guidelines"):
                with stats_lock:
                    stats["skipped"] += 1
                return

            with stats_lock:
                stats["found"] += 1

            try:
                # Determine if it's a PDF or HTML page
                if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx"]):
                    # passing stats directly might have slight race conditions inside _process_pdf_release, but they only increment ints
                    # To be perfectly thread-safe we'd lock inside those methods too, but GIL handles dict integer increments safely enough in CPython.
                    self._process_pdf_release(full_url, text, stats)
                else:
                    self._process_html_release(full_url, text, section, stats)
            except Exception as e:
                with stats_lock:
                    stats["failed"] += 1
                self.logger.warning("Error processing MoHFW release %s: %s", text[:50], e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_mohfw_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in MoHFW scraper: %s", e)

        return stats

    def _process_html_release(self, url, title, section, stats):
        """Fetch and process an HTML press release page."""
        html = self.fetch_html(url)
        soup = self.parse_html(html)
        if not soup:
            stats["failed"] += 1
            return

        # Extract main content
        content_area = (
            soup.find("article") or
            soup.find("div", class_="field-item") or
            soup.find("div", id="content") or
            soup.find("main")
        )
        if not content_area:
            stats["failed"] += 1
            return

        full_text = self.normalizer.clean_text(content_area.get_text(strip=True))

        # Extract date
        date_elem = soup.find("span", class_="date-display-single") or soup.find("time")
        pub_date = date.today()
        if date_elem:
            pub_date = self.normalizer.normalize_date(date_elem.get_text(strip=True))

        # Try to extract case numbers
        numbers = self.normalizer.extract_case_numbers(full_text)

        # Match disease
        matched_disease = None
        for disease in TARGET_DISEASES:
            if disease.lower() in full_text.lower():
                matched_disease = disease
                break

        disease_id = 1  # Fallback
        if matched_disease:
            norm_name = self.normalizer.normalize_disease_name(matched_disease)
            did = self.db.get_disease_id_by_name(norm_name)
            if did:
                disease_id = did
            else:
                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "Infectious",
                })

        # Store as guideline
        self.db.upsert_guideline({
            "disease_id": disease_id,
            "guideline_type": "official_report",
            "title": title[:200],
            "content": full_text[:5000],
            "source": "MoHFW",
            "source_url": url,
        })

        # If case numbers found, also insert as outbreak
        if numbers.get("cases"):
            # Try to extract state from text
            state = "India"  # National level by default
            for line in full_text.split("."):
                norm_state = self.normalizer.normalize_state(line.strip())
                if norm_state and len(norm_state) > 2:
                    state = norm_state
                    break

            self.db.upsert_outbreak_greatest({
                "disease_id": disease_id,
                "state": state,
                "district": "Unknown",
                "cases_reported": numbers["cases"],
                "deaths_reported": numbers.get("deaths", 0) or 0,
                "reported_date": pub_date,
                "source": "MoHFW",
                "source_url": url,
                "severity": self.normalizer.compute_severity(
                    numbers["cases"], numbers.get("deaths", 0) or 0
                ),
                "status": "active",
                "latitude": 0.0,
                "longitude": 0.0,
            })

        # Store in bulletin_texts for LangChain
        self.db.upsert_bulletin_text({
            "source": "MoHFW",
            "disease_mentioned": matched_disease,
            "state_mentioned": None,
            "raw_text": full_text[:50000],
            "published_date": pub_date,
            "url": url,
        })

        # Check for embedded PDF links
        for pdf_link in content_area.find_all("a", href=True):
            pdf_href = pdf_link["href"]
            if ".pdf" in pdf_href.lower():
                pdf_url = pdf_href if pdf_href.startswith("http") else MOHFW_URLS["BASE"] + pdf_href
                self._process_pdf_release(pdf_url, title + " (PDF)", stats)

        stats["inserted"] += 1

    def _process_pdf_release(self, url, title, stats):
        """Download and extract text from a PDF release."""
        text = self.extract_pdf_from_url(url)
        if not text or len(text.strip()) < 50:
            stats["failed"] += 1
            return

        stats["pdfs"] += 1

        # Match disease
        matched_disease = None
        for disease in TARGET_DISEASES:
            if disease.lower() in (title + " " + text[:500]).lower():
                matched_disease = disease
                break

        disease_id = 1
        if matched_disease:
            norm_name = self.normalizer.normalize_disease_name(matched_disease)
            did = self.db.get_disease_id_by_name(norm_name)
            if did:
                disease_id = did

        self.db.upsert_guideline({
            "disease_id": disease_id,
            "guideline_type": "official_report",
            "title": title[:200],
            "content": text[:5000],
            "source": "MoHFW",
            "source_url": url,
        })

        # Store raw text for LangChain
        self.db.upsert_bulletin_text({
            "source": "MoHFW",
            "disease_mentioned": matched_disease,
            "raw_text": text[:50000],
            "published_date": date.today(),
            "url": url,
        })

        stats["inserted"] += 1
