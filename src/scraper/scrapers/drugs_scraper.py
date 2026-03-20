"""
Drugs.com Scraper — Enhanced with Indian brand names and interaction data
"""
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from base_scraper import BaseScraper
from config import TARGET_DISEASES, MAX_THREADS


class DrugsScraper(BaseScraper):
    def __init__(self):
        super().__init__("Drugs.com")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0

        self.logger.info("Starting Drugs.com Scraping...")

        def process_one(disease):
            nonlocal found, inserted, skipped, failed
            try:
                slug = disease.lower().replace(" ", "-").replace("'", "").replace("/", "-")
                url = f"https://www.drugs.com/health-guide/{slug}.html"

                response_text, changed = self.fetch_with_cache(url)
                if not changed or not response_text:
                    skipped += 1
                    return

                soup = self.parse_html(response_text)
                if not soup:
                    failed += 1
                    return

                content = soup.find("div", class_="contentBox") or soup.find("article") or soup.find("main")
                if not content:
                    failed += 1
                    return

                sections = self.extract_sections_from_soup(content)
                all_text = sections.get("full_text", "")

                norm_name = self.normalizer.normalize_disease_name(disease)
                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "General Health",
                    "description": self.normalizer.clean_text(all_text[:1000]),
                    "symptoms": self.normalizer.clean_text(
                        next((v for k, v in sections.items() if "symptom" in k), "")
                    ),
                    "source_urls": [url],
                })

                for header, text in sections.items():
                    if header == "full_text" or not text or len(text.strip()) < 20:
                        continue

                    content_type = self.map_section_to_content_type(header)
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": content_type,
                        "title": f"Drugs.com {content_type.replace('_', ' ').title()} for {disease}",
                        "content": self.normalizer.clean_text(text),
                        "source": "Drugs.com",
                        "source_url": url,
                    })

                found += 1
                inserted += 1

            except Exception as e:
                self.logger.warning("Error scraping Drugs.com for %s: %s", disease, e)
                failed += 1

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            executor.map(process_one, TARGET_DISEASES)

        completed_at = datetime.now()
        self.log_run("diseases,guidelines", "success", found, inserted, 0, skipped,
                     started_at=started_at, completed_at=completed_at, records_failed=failed)
