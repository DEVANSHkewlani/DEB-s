"""
ECDC (European Centre for Disease Prevention and Control) Scraper
PRIORITY: HIGH — Surveillance data and threat assessments

Extracts:
- Weekly threat assessment PDFs
- Infectious disease topic analyses
- Stores in education_resources + bulletin_texts
"""
from datetime import datetime
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES, ECDC_URLS


class ECDCScraper(BaseScraper):
    def __init__(self):
        super().__init__("ECDC")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        self.logger.info("Starting ECDC Scraping...")

        try:
            # ── Part 1: Disease Topics ───────────────────────────────────
            url = ECDC_URLS.get("TOPICS", URLS.get("ECDC_TOPICS"))
            if url:
                stats = self._scrape_topics(url)
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]

            # ── Part 2: Threat Reports ───────────────────────────────────
            threats_url = ECDC_URLS.get("THREATS")
            if threats_url:
                stats = self._scrape_threats(threats_url)
                found += stats["found"]
                inserted += stats["inserted"]
                pdfs += stats["pdfs"]
                failed += stats["failed"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("ECDC error: %s", e)

        completed_at = datetime.now()
        self.log_run("guidelines,education,bulletins",
                     "success" if error_msg is None else "error",
                     found, inserted, 0, skipped,
                     error=error_msg, started_at=started_at, completed_at=completed_at,
                     records_failed=failed, pdfs_processed=pdfs)

    def _scrape_topics(self, url):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0}

        html = self.fetch_html(url)
        soup = self.parse_html(html)
        if not soup:
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        links = soup.find_all("a", href=True)
        stats_lock = threading.Lock()
        
        def process_ecdc_link(link):
            text = link.get_text(strip=True)
            href = link["href"]

            # Match against target diseases
            matched = None
            for disease in TARGET_DISEASES:
                if disease.lower() in text.lower():
                    matched = disease
                    break
            if not matched:
                return

            full_url = href if href.startswith("http") else f"https://www.ecdc.europa.eu{href}"

            if self.is_already_scraped(full_url, table="disease_guidelines"):
                with stats_lock:
                    stats["skipped"] += 1
                return

            with stats_lock:
                stats["found"] += 1

            try:
                page_html = self.fetch_html(full_url)
                page_soup = self.parse_html(page_html)
                if not page_soup:
                    with stats_lock:
                        stats["failed"] += 1
                    return

                content = page_soup.find("article") or page_soup.find("main")
                if not content:
                    with stats_lock:
                        stats["failed"] += 1
                    return

                norm_name = self.normalizer.normalize_disease_name(matched)
                disease_id = self.db.get_disease_id_by_name(norm_name) or self.db.upsert_disease({
                    "name": norm_name, "category": "Infectious",
                })

                sections = self.extract_sections_from_soup(content)
                for header, section_text in sections.items():
                    if header == "full_text" or not section_text or len(section_text.strip()) < 20:
                        continue
                    content_type = self.map_section_to_content_type(header)
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": content_type,
                        "title": f"ECDC {content_type.replace('_', ' ').title()} for {matched}",
                        "content": self.normalizer.clean_text(section_text),
                        "source": "ECDC",
                        "source_url": full_url,
                    })

                with stats_lock:
                    stats["inserted"] += 1

            except Exception as e:
                with stats_lock:
                    stats["failed"] += 1
                self.logger.warning("ECDC topic error: %s", e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_ecdc_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in ECDC topic scraper: %s", e)

        return stats

    def _scrape_threats(self, url):
        stats = {"found": 0, "inserted": 0, "failed": 0, "pdfs": 0}

        html = self.fetch_html(url)
        soup = self.parse_html(html)
        if not soup:
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        links = soup.find_all("a", href=True)
        stats_lock = threading.Lock()
        
        def process_threat_link(link):
            href = link["href"]
            if ".pdf" not in href.lower():
                return

            full_url = href if href.startswith("http") else f"https://www.ecdc.europa.eu{href}"
            if self.is_already_scraped(full_url, table="education_resources"):
                return

            with stats_lock:
                stats["found"] += 1
            text = self.extract_pdf_from_url(full_url)
            if not text:
                with stats_lock:
                    stats["failed"] += 1
                return

            with stats_lock:
                stats["pdfs"] += 1

            self.db.upsert_education_resource({
                "title": link.get_text(strip=True)[:200] or "ECDC Threat Assessment",
                "description": self.normalizer.clean_text(text[:1000]),
                "content": self.normalizer.clean_text(text[:5000]),
                "source": "ECDC",
                "source_url": full_url,
                "resource_type": "threat_report",
            })

            self.db.upsert_bulletin_text({
                "source": "ECDC",
                "raw_text": text[:50000],
                "published_date": None,
                "url": full_url,
            })

            with stats_lock:
                stats["inserted"] += 1

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_threat_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in ECDC threat scraper: %s", e)
                    
        return stats
