"""
State Health Department Scraper
PRIORITY: MEDIUM — supplements national sources with state-level detail

Scrapes 12 priority state health department portals for:
- Weekly/monthly disease bulletins (PDF and HTML)
- Outbreak announcements
- District-level surveillance data
"""
import re
from datetime import datetime, date
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES, STATE_PRIORITY_SITES, HEALTH_KEYWORDS


class StateScraper(BaseScraper):
    def __init__(self):
        super().__init__("StateDept")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        self.logger.info("Starting State Health Department Scraping...")

        # Merge priority sites with general state sites
        all_states = {}

        # Priority states (with type hints)
        for state, info in STATE_PRIORITY_SITES.items():
            all_states[state] = {"url": info["url"], "type": info.get("type", "general")}

        # Add remaining states from general config
        for state, url in URLS.get("STATE_SITES", {}).items():
            if state not in all_states:
                all_states[state] = {"url": url, "type": "general"}

        for state, info in all_states.items():
            self.logger.info("Scraping %s (%s)...", state, info["type"])
            try:
                stats = self._scrape_state(state, info["url"], info["type"])
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]
            except Exception as e:
                failed += 1
                self.logger.warning("Error scraping %s: %s", state, e)

        completed_at = datetime.now()
        self.log_run(
            "outbreaks,alerts,bulletins",
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed, pdfs_processed=pdfs,
        )

    def _scrape_state(self, state, url, site_type):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0, "pdfs": 0}

        # Use Playwright for JS-heavy state sites
        use_pw = site_type in ("html_weekly", "html_table", "irregular") or True
        html = self.fetch_html(url, use_playwright=use_pw)
        soup = self.parse_html(html)

        if not soup:
            stats["failed"] += 1
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        links = soup.find_all("a", href=True)
        
        def process_state_link(link):
            local_stats = {"found": 0, "inserted": 0, "failed": 0, "pdfs": 0, "skipped": 0}
            text = link.get_text(strip=True)
            href = link["href"]

            if not href or len(text) < 5:
                return local_stats

            # Check for health/bulletin keywords
            combined = (text + " " + href).lower()
            is_bulletin = any(kw in combined for kw in [
                "bulletin", "alert", "notification", "press release",
                "news", "report", "daily", "outbreak", "surveillance",
                "weekly", "monthly", "disease",
            ])
            if not is_bulletin:
                return local_stats

            full_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")

            if self.is_already_scraped(full_url, table="outbreaks"):
                local_stats["skipped"] += 1
                return local_stats

            local_stats["found"] += 1

            try:
                # Handle PDFs
                if ".pdf" in href.lower():
                    self._process_state_pdf(full_url, text, state, local_stats)
                    return local_stats

                # Handle HTML pages
                self._process_state_link(full_url, text, state, local_stats)

            except Exception as e:
                local_stats["failed"] += 1
                self.logger.warning("Error processing %s link %s: %s", state, text[:50], e)
                
            return local_stats

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_state_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    s = future.result()
                    for k in stats:
                        stats[k] += s.get(k, 0)
                except Exception as e:
                    self.logger.error("Future failed in State scraper: %s", e)

        return stats

    def _process_state_pdf(self, pdf_url, title, state, stats):
        """Extract data from a state health PDF bulletin."""
        text = self.extract_pdf_from_url(pdf_url)
        if not text or len(text.strip()) < 50:
            stats["failed"] += 1
            return

        stats["pdfs"] += 1

        # Extract case numbers
        numbers = self.normalizer.extract_case_numbers(text)

        # Match diseases
        matched_diseases = []
        for disease in TARGET_DISEASES:
            if disease.lower() in (title + " " + text[:2000]).lower():
                matched_diseases.append(disease)

        if not matched_diseases:
            matched_diseases = ["General Health"]

        for disease in matched_diseases:
            disease_id = self._get_or_create_disease(disease)

            self.db.upsert_outbreak_greatest({
                "disease_id": disease_id,
                "state": state,
                "district": "Unknown",
                "cases_reported": numbers.get("cases", 0) or 0,
                "deaths_reported": numbers.get("deaths", 0) or 0,
                "reported_date": date.today(),
                "source": f"{state} Health Dept",
                "source_url": pdf_url,
                "severity": self.normalizer.compute_severity(
                    numbers.get("cases", 0) or 0, numbers.get("deaths", 0) or 0
                ),
                "status": "active",
                "latitude": 0.0,
                "longitude": 0.0,
            })

        # Store raw text for LangChain
        self.db.upsert_bulletin_text({
            "source": f"{state} Health Dept",
            "disease_mentioned": matched_diseases[0] if matched_diseases else None,
            "state_mentioned": state,
            "raw_text": text[:50000],
            "published_date": date.today(),
            "url": pdf_url,
        })

        stats["inserted"] += 1

    def _process_state_link(self, url, text, state, stats):
        """Process a state health department HTML link."""
        # Match disease from link text
        matched_disease = None
        for disease in TARGET_DISEASES:
            if disease.lower() in text.lower():
                matched_disease = disease
                break

        disease_id = self._get_or_create_disease(matched_disease or text)

        self.db.upsert_outbreak_greatest({
            "disease_id": disease_id,
            "state": state,
            "district": "Unknown",
            "cases_reported": 0,
            "deaths_reported": 0,
            "reported_date": date.today(),
            "source": f"{state} Health Dept",
            "source_url": url,
            "severity": "low",
            "status": "notified",
            "latitude": 0.0,
            "longitude": 0.0,
        })

        stats["inserted"] += 1

    def _get_or_create_disease(self, name):
        """Get disease ID by name, creating it if needed."""
        norm_name = self.normalizer.normalize_disease_name(name)
        disease_id = self.db.get_disease_id_by_name(norm_name)
        if not disease_id:
            disease_id = self.db.upsert_disease({
                "name": norm_name,
                "category": "Infectious",
            })
        return disease_id or 1
