from datetime import datetime
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES

class RareDiseasesScraper(BaseScraper):
    def __init__(self):
        super().__init__("GARD/Orphanet")

    def run(self):
        started_at = datetime.now()
        found = inserted = updated = skipped = 0

        print(f"[{datetime.now()}] Starting Rare Diseases (GARD) Scraping...")
        from concurrent.futures import ThreadPoolExecutor
        from config import MAX_THREADS

        def process_one(disease):
            nonlocal found, inserted, updated, skipped
            try:
                # GARD uses a search-based approach
                slug = disease.lower().replace(" ", "-").replace("'", "").replace("/", "-")
                url = f"https://rarediseases.info.nih.gov/diseases/{slug}"

                if self.is_already_scraped(url):
                    found += 1
                    return

                # GARD requires JavaScript rendering
                html = self.fetch_html(url, use_playwright=True)
                soup = self.parse_html(html)
                if not soup:
                    skipped += 1
                    return

                content_area = soup.find('div', class_='disease-details') or soup.find('article') or soup.find('main')
                if not content_area:
                    skipped += 1
                    return

                sections = {
                    "symptoms": "",
                    "treatment": "",
                    "causes": "",
                    "diagnosis": "",
                    "inheritance": "",
                }

                headers = content_area.find_all(['h2', 'h3'])
                for header in headers:
                    header_text = header.get_text(strip=True).lower()
                    section_content = []
                    curr = header.find_next_sibling()
                    while curr and curr.name not in ['h2', 'h3']:
                        section_content.append(curr.get_text(strip=True))
                        curr = curr.find_next_sibling()

                    full_content = "\n".join(section_content)
                    if "symptom" in header_text or "sign" in header_text:
                        sections["symptoms"] = full_content
                    elif "treatment" in header_text or "manage" in header_text:
                        sections["treatment"] = full_content
                    elif "cause" in header_text:
                        sections["causes"] = full_content
                    elif "diagnos" in header_text:
                        sections["diagnosis"] = full_content
                    elif "inherit" in header_text or "genetic" in header_text:
                        sections["inheritance"] = full_content

                description = self.normalizer.clean_text(content_area.get_text(strip=True)[:1000])
                disease_id = self.db.upsert_disease({
                    "name": self.normalizer.normalize_disease_name(disease),
                    "category": "Rare Disease",
                    "description": description,
                    "symptoms": self.normalizer.clean_text(sections["symptoms"]),
                    "source_urls": [url]
                })

                guideline_mappings = {
                    "treatment": "Treatment",
                    "symptoms": "Symptoms",
                    "diagnosis": "Diagnosis",
                }
                for g_type, g_title in guideline_mappings.items():
                    content = sections[g_type]
                    if content:
                        self.db.upsert_guideline({
                            "disease_id": disease_id,
                            "guideline_type": g_type,
                            "title": f"GARD {g_title} for {disease}",
                            "content": self.normalizer.clean_text(content),
                            "source": "GARD/NIH",
                            "source_url": url
                        })

                found += 1
            except Exception as e:
                print(f"Error scraping GARD for {disease}: {e}")
                skipped += 1

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            executor.map(process_one, TARGET_DISEASES)

        completed_at = datetime.now()
        self.log_run("diseases,guidelines", "success", found, inserted, updated, skipped, started_at=started_at, completed_at=completed_at)
