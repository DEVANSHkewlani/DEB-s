"""
WHO SEARO (South-East Asia Regional Office) Scraper
PRIORITY: MEDIUM — Regional health topics and India-specific documents
"""
from datetime import datetime
from base_scraper import BaseScraper
from config import TARGET_DISEASES, HEALTH_KEYWORDS


class WHOSEAROScraper(BaseScraper):
    SEARO_URL = "https://www.who.int/southeastasia/health-topics"

    def __init__(self):
        super().__init__("WHO-SEARO")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0
        error_msg = None

        self.logger.info("Starting WHO SEARO Scraping...")

        try:
            html = self.fetch_html(self.SEARO_URL)
            soup = self.parse_html(html)
            if not soup:
                error_msg = "Could not fetch SEARO page"
            else:
                links = soup.find_all("a", href=True)
                for link in links:
                    text = link.get_text(strip=True)
                    href = link["href"]

                    if not href or len(text) < 5:
                        continue

                    combined = text.lower()
                    matched = None
                    for disease in TARGET_DISEASES:
                        if disease.lower() in combined:
                            matched = disease
                            break
                    if not matched:
                        if not any(kw in combined for kw in HEALTH_KEYWORDS[:10]):
                            continue

                    full_url = href if href.startswith("http") else f"https://www.who.int{href}"

                    if self.is_already_scraped(full_url, table="education_resources"):
                        skipped += 1
                        continue

                    found += 1

                    try:
                        page_html = self.fetch_html(full_url)
                        page_soup = self.parse_html(page_html)
                        if not page_soup:
                            failed += 1
                            continue

                        content = page_soup.find("article") or page_soup.find("main")
                        if not content:
                            failed += 1
                            continue

                        full_text = self.normalizer.clean_text(content.get_text(strip=True))

                        if matched:
                            norm_name = self.normalizer.normalize_disease_name(matched)
                            disease_id = self.db.get_disease_id_by_name(norm_name)
                            if disease_id:
                                sections = self.extract_sections_from_soup(content)
                                for header, sec_text in sections.items():
                                    if header == "full_text" or not sec_text or len(sec_text.strip()) < 20:
                                        continue
                                    content_type = self.map_section_to_content_type(header)
                                    self.db.upsert_guideline({
                                        "disease_id": disease_id,
                                        "guideline_type": content_type,
                                        "title": f"WHO-SEARO {text[:100]}",
                                        "content": self.normalizer.clean_text(sec_text),
                                        "source": "WHO-SEARO",
                                        "source_url": full_url,
                                    })

                        self.db.upsert_education_resource({
                            "title": text[:200],
                            "description": full_text[:500],
                            "content": full_text[:5000],
                            "source": "WHO-SEARO",
                            "source_url": full_url,
                            "resource_type": "regional_report",
                        })

                        inserted += 1

                    except Exception as e:
                        failed += 1
                        self.logger.warning("SEARO page error: %s", e)

        except Exception as e:
            error_msg = str(e)
            self.logger.error("WHO-SEARO error: %s", e)

        completed_at = datetime.now()
        self.log_run("guidelines,education",
                     "success" if error_msg is None else "error",
                     found, inserted, 0, skipped,
                     error=error_msg, started_at=started_at, completed_at=completed_at,
                     records_failed=failed)
