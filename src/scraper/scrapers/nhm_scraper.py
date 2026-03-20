"""
NHM (National Health Mission) Scraper
PRIORITY: HIGH — Health scheme info and disease control guidelines

Extracts:
- Health scheme information (Ayushman Bharat, PMJAY, etc.)
- Disease control program guidelines
- PDF documents
"""
from datetime import datetime, date
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES, NHM_URLS, HEALTH_KEYWORDS


class NHMScraper(BaseScraper):
    def __init__(self):
        super().__init__("NHM")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        self.logger.info("Starting NHM Scraping...")

        try:
            for page_key, url in NHM_URLS.items():
                if page_key == "BASE":
                    continue

                self.logger.info("Scraping NHM %s...", page_key)
                stats = self._scrape_page(url, page_key)
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]

            # Also scrape legacy config URL
            legacy = URLS.get("NHM")
            if legacy:
                stats = self._scrape_page(legacy, "legacy")
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("NHM error: %s", e)

        completed_at = datetime.now()
        self.log_run("guidelines,education",
                     "success" if error_msg is None else "error",
                     found, inserted, 0, skipped,
                     error=error_msg, started_at=started_at, completed_at=completed_at,
                     records_failed=failed, pdfs_processed=pdfs)

    def _scrape_page(self, url, section):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0, "pdfs": 0}

        html = self.fetch_html(url, use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        links = soup.find_all("a", href=True)
        stats_lock = threading.Lock()
        
        def process_nhm_link(link):
            text = link.get_text(strip=True)
            href = link["href"]

            if not href or len(text) < 5:
                return

            full_url = href if href.startswith("http") else NHM_URLS["BASE"] + "/" + href.lstrip("/")

            # Filter for health relevance
            combined = (text + " " + href).lower()
            if not any(kw in combined for kw in HEALTH_KEYWORDS + ["scheme", "programme", "program", "guideline"]):
                return

            if self.is_already_scraped(full_url, table="disease_guidelines"):
                with stats_lock:
                    stats["skipped"] += 1
                return

            with stats_lock:
                stats["found"] += 1

            try:
                # ── PDF documents ────────────────────────────────────────
                if ".pdf" in href.lower():
                    pdf_text = self.extract_pdf_from_url(full_url)
                    if pdf_text and len(pdf_text.strip()) > 50:
                        with stats_lock:
                            stats["pdfs"] += 1

                        matched = None
                        for disease in TARGET_DISEASES:
                            if disease.lower() in (text + " " + pdf_text[:500]).lower():
                                matched = disease
                                break

                        disease_id = 1
                        if matched:
                            norm = self.normalizer.normalize_disease_name(matched)
                            did = self.db.get_disease_id_by_name(norm)
                            if did:
                                disease_id = did

                        self.db.upsert_guideline({
                            "disease_id": disease_id,
                            "guideline_type": "official_guideline",
                            "title": text[:200],
                            "content": self.normalizer.clean_text(pdf_text[:5000]),
                            "source": "NHM",
                            "source_url": full_url,
                        })

                        self.db.upsert_education_resource({
                            "title": text[:200],
                            "description": self.normalizer.clean_text(pdf_text[:500]),
                            "content": self.normalizer.clean_text(pdf_text[:5000]),
                            "source": "NHM",
                            "source_url": full_url,
                            "resource_type": "guideline",
                        })

                        with stats_lock:
                            stats["inserted"] += 1
                    else:
                        with stats_lock:
                            stats["failed"] += 1
                    return

                # ── HTML pages ───────────────────────────────────────────
                matched = None
                for disease in TARGET_DISEASES:
                    if disease.lower() in combined:
                        matched = disease
                        break

                disease_id = 1
                if matched:
                    norm = self.normalizer.normalize_disease_name(matched)
                    did = self.db.get_disease_id_by_name(norm)
                    if did:
                        disease_id = did
                else:
                    return

                html_page = self.fetch_html(full_url)
                page_soup = self.parse_html(html_page)
                if not page_soup:
                    with stats_lock:
                        stats["failed"] += 1
                    return

                content = page_soup.find("article") or page_soup.find("div", class_="content")
                if content:
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": "scheme_details",
                        "title": text[:200],
                        "content": self.normalizer.clean_text(content.get_text(strip=True)[:5000]),
                        "source": "NHM",
                        "source_url": full_url,
                    })
                    with stats_lock:
                        stats["inserted"] += 1

            except Exception as e:
                with stats_lock:
                    stats["failed"] += 1
                self.logger.warning("Error processing NHM link %s: %s", text[:50], e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_nhm_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in NHM scraper: %s", e)

        return stats
