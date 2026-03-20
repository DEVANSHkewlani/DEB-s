"""
NCDC (National Centre for Disease Control) Scraper
PRIORITY: HIGH

Extracts:
- Weekly surveillance reports (PDFs)
- Disease advisories
- Disease trends data for last 4 weeks
- Stores raw text in bulletin_texts
"""
import re
from datetime import datetime, date
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES
from pdf_parser import PDFParser


class NCDCScraper(BaseScraper):
    def __init__(self):
        super().__init__("NCDC")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        self.logger.info("Starting NCDC Scraping...")

        try:
            url = URLS["NCDC_ANNOUNCEMENTS"]

            # Check for content change
            response_text, changed = self.fetch_with_cache(url, force=True)
            soup = self.parse_html(response_text) if response_text else None

            if not soup:
                # Try Playwright fallback
                html = self.fetch_html(url, use_playwright=True)
                soup = self.parse_html(html)

            if soup:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                import threading
                
                links = soup.find_all("a", href=True)
                
                # Use a lock to track stats correctly
                stats_lock = threading.Lock()
                
                def process_ncdc_link(link):
                    nonlocal found, inserted, failed, skipped, pdfs
                    text = link.get_text(strip=True)
                    href = link["href"].strip().replace(" ", "%20")
                    if not href:
                        return

                    full_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")

                    # ── PDF Bulletins and Advisories ──────────────────────
                    if href.lower().endswith(".pdf") and any(
                        kw in text.lower() for kw in ["bulletin", "advisory", "report", "surveillance", "weekly"]
                    ):
                        if self.is_already_scraped(full_url, table="disease_guidelines"):
                            with stats_lock:
                                skipped += 1
                            return

                        stats = self._process_pdf_bulletin(full_url, text)
                        with stats_lock:
                            found += stats["found"]
                            inserted += stats["inserted"]
                            failed += stats["failed"]
                            if stats["pdf"]:
                                pdfs += 1
                        return

                    # ── Disease info pages ────────────────────────────────
                    norm_disease = self.normalizer.normalize_disease_name(text)
                    if norm_disease in TARGET_DISEASES:
                        if self.is_already_scraped(full_url):
                            with stats_lock:
                                skipped += 1
                            return

                        try:
                            self._process_disease_page(full_url, norm_disease)
                            with stats_lock:
                                found += 1
                                inserted += 1
                        except Exception as e:
                            with stats_lock:
                                failed += 1
                            self.logger.warning("Error on NCDC disease page: %s", e)
                            
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(process_ncdc_link, l) for l in links]
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            self.logger.error("Future failed in NCDC scraper: %s", e)

        except Exception as e:
            error_msg = str(e)
            self.logger.error("NCDC scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "guidelines,outbreaks,bulletins",
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed, pdfs_processed=pdfs,
        )

    def _process_pdf_bulletin(self, url, title):
        """Download, extract, and store NCDC PDF bulletin content."""
        stats = {"found": 0, "inserted": 0, "failed": 0, "pdf": False}

        self.logger.info("Processing NCDC PDF: %s", title[:80])
        text = self.extract_pdf_from_url(url)
        if not text or len(text.strip()) < 50:
            stats["failed"] += 1
            return stats

        stats["pdf"] = True

        # Match disease from title and content
        matched_disease = None
        for disease in TARGET_DISEASES:
            if disease.lower() in (title + " " + text[:1000]).lower():
                matched_disease = disease
                break

        disease_id = 1  # Fallback
        if matched_disease:
            norm_name = self.normalizer.normalize_disease_name(matched_disease)
            did = self.db.get_disease_id_by_name(norm_name)
            if did:
                disease_id = did

        # Store as guideline
        self.db.upsert_guideline({
            "disease_id": disease_id,
            "guideline_type": "official_bulletin",
            "title": title[:200],
            "content": self.normalizer.clean_text(text[:5000]),
            "source": "NCDC",
            "source_url": url,
        })

        # Extract case numbers from bulletin text
        numbers = self.normalizer.extract_case_numbers(text)
        if numbers.get("cases") and matched_disease:
            self.db.upsert_outbreak_greatest({
                "disease_id": disease_id,
                "state": "India",
                "district": "Unknown",
                "cases_reported": numbers["cases"],
                "deaths_reported": numbers.get("deaths", 0) or 0,
                "reported_date": date.today(),
                "source": "NCDC",
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
            "source": "NCDC",
            "disease_mentioned": matched_disease,
            "state_mentioned": None,
            "raw_text": text[:50000],
            "published_date": date.today(),
            "url": url,
        })

        stats["found"] += 1
        stats["inserted"] += 1
        return stats

    def _process_disease_page(self, url, disease_name):
        """Scrape an NCDC disease info page with section-based extraction."""
        html = self.fetch_html(url)
        soup = self.parse_html(html)
        if not soup:
            return

        content = soup.find("div", class_="content") or soup.find("main") or soup.find("article")
        if not content:
            return

        full_text = self.normalizer.clean_text(content.get_text(strip=True))

        disease_id = self.db.upsert_disease({
            "name": disease_name,
            "category": "Infectious",
            "description": full_text[:1000],
            "source_urls": [url],
        })

        # Section-based extraction
        sections = self.extract_sections_from_soup(content)
        for header_text, section_content in sections.items():
            if header_text == "full_text":
                continue
            content_type = self.map_section_to_content_type(header_text)

            self.db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": content_type,
                "title": f"NCDC {content_type.replace('_', ' ').title()} for {disease_name}",
                "content": self.normalizer.clean_text(section_content),
                "source": "NCDC",
                "source_url": url,
            })

        # Fallback: if no sections found, store as general info
        if len(sections) <= 1:
            self.db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": "general_info",
                "title": f"NCDC {disease_name} Info",
                "content": full_text[:5000],
                "source": "NCDC",
                "source_url": url,
            })
