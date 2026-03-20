"""
Mayo Clinic Scraper — Comprehensive medical content
Extracts symptoms, causes, diagnosis, treatment, risk factors, complications.
Uses Playwright (dynamic site) + change detection.
"""
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from base_scraper import BaseScraper
from config import TARGET_DISEASES, MAX_THREADS


class MayoClinicScraper(BaseScraper):
    def __init__(self):
        super().__init__("Mayo Clinic")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0

        self.logger.info("Starting Mayo Clinic Scraping...")

        def process_one(disease):
            nonlocal found, inserted, skipped, failed
            try:
                slug = disease.lower().replace(" ", "-").replace("'", "").replace("/", "-")

                # ── Symptoms/Causes page ─────────────────────────────────
                url = f"https://www.mayoclinic.org/diseases-conditions/{slug}/symptoms-causes/syc-0"

                if self.is_already_scraped(url):
                    skipped += 1
                    return

                html = self.fetch_html(url, use_playwright=True)
                soup = self.parse_html(html)
                if not soup:
                    failed += 1
                    return

                content = soup.find("div", class_="content") or soup.find("article") or soup.find("main")
                if not content:
                    failed += 1
                    return

                sections = self.extract_sections_from_soup(content)
                all_text = sections.get("full_text", "")

                norm_name = self.normalizer.normalize_disease_name(disease)
                incubation = self.normalizer.extract_incubation_period(all_text)

                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "General Health",
                    "description": self.normalizer.clean_text(all_text[:1000]),
                    "symptoms": self.normalizer.clean_text(
                        next((v for k, v in sections.items() if "symptom" in k), "")
                    ),
                    "risk_factors": self.normalizer.clean_text(
                        next((v for k, v in sections.items() if "risk" in k), "")
                    ),
                    "incubation_period": incubation or "",
                    "source_urls": [url],
                })

                for header, text in sections.items():
                    if header == "full_text" or not text or len(text.strip()) < 20:
                        continue

                    content_type = self.map_section_to_content_type(header)
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": content_type,
                        "title": f"Mayo Clinic {content_type.replace('_', ' ').title()} for {disease}",
                        "content": self.normalizer.clean_text(text),
                        "source": "Mayo Clinic",
                        "source_url": url,
                    })

                # ── Diagnosis/Treatment page ─────────────────────────────
                treat_url = f"https://www.mayoclinic.org/diseases-conditions/{slug}/diagnosis-treatment/drc-0"
                treat_html = self.fetch_html(treat_url, use_playwright=True)
                treat_soup = self.parse_html(treat_html)
                if treat_soup:
                    treat_content = treat_soup.find("div", class_="content") or treat_soup.find("article")
                    if treat_content:
                        treat_sections = self.extract_sections_from_soup(treat_content)
                        for header, text in treat_sections.items():
                            if header == "full_text" or not text or len(text.strip()) < 20:
                                continue
                            content_type = self.map_section_to_content_type(header)
                            self.db.upsert_guideline({
                                "disease_id": disease_id,
                                "guideline_type": content_type,
                                "title": f"Mayo Clinic {content_type.replace('_', ' ').title()} for {disease}",
                                "content": self.normalizer.clean_text(text),
                                "source": "Mayo Clinic",
                                "source_url": treat_url,
                            })

                found += 1
                inserted += 1

            except Exception as e:
                self.logger.warning("Error scraping Mayo Clinic for %s: %s", disease, e)
                failed += 1

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            executor.map(process_one, TARGET_DISEASES)

        completed_at = datetime.now()
        self.log_run("diseases,guidelines", "success", found, inserted, 0, skipped,
                     started_at=started_at, completed_at=completed_at, records_failed=failed)
