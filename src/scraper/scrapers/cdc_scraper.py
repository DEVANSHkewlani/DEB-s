"""
CDC (Centers for Disease Control and Prevention) Scraper
PRIORITY: HIGH

Extracts:
- Disease factsheets with section-based content_type metadata
- India traveler health information
- Uses change detection to avoid redundant fetches
"""
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES, CDC_SLUG_MAP, CDC_TRAVELER_INDIA, MAX_THREADS


class CDCScraper(BaseScraper):
    def __init__(self):
        super().__init__("CDC")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0
        error_msg = None

        self.logger.info("Starting CDC Scraping...")

        try:
            # ── Part 1: Disease Fact Sheets ──────────────────────────────
            def process_disease(disease):
                nonlocal found, inserted, skipped, failed
                slug = CDC_SLUG_MAP.get(disease)
                if not slug:
                    slug = disease.lower().replace(" ", "-").replace("'", "").replace("/", "-")

                url = f"{URLS['CDC_DISEASES']}/{slug}/index.html"

                response_text, changed = self.fetch_with_cache(url)
                if not changed or not response_text:
                    skipped += 1
                    return

                soup = self.parse_html(response_text)
                if not soup:
                    # Try Playwright
                    html = self.fetch_html(url)
                    soup = self.parse_html(html)
                if not soup:
                    failed += 1
                    return

                content = soup.find("div", id="content") or soup.find("article") or soup.find("main")
                if not content:
                    failed += 1
                    return

                # ── Section-based extraction ─────────────────────────────
                sections = self.extract_sections_from_soup(content)
                all_text = sections.get("full_text", "")

                norm_name = self.normalizer.normalize_disease_name(disease)
                incubation = self.normalizer.extract_incubation_period(all_text)
                mortality = self.normalizer.extract_mortality_rate(all_text)

                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "Infectious",
                    "description": self.normalizer.clean_text(all_text[:1000]),
                    "symptoms": self.normalizer.clean_text(
                        sections.get("symptoms", "") or
                        next((v for k, v in sections.items() if "symptom" in k or "sign" in k), "")
                    ),
                    "transmission_method": self.normalizer.clean_text(
                        next((v for k, v in sections.items() if "transmiss" in k or "spread" in k), "")
                    ),
                    "incubation_period": incubation or "",
                    "mortality_rate": mortality,
                    "source_urls": [url],
                })

                # Store each section as a typed guideline
                for header_text, section_content in sections.items():
                    if header_text == "full_text" or not section_content or len(section_content.strip()) < 20:
                        continue

                    content_type = self.map_section_to_content_type(header_text)

                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": content_type,
                        "title": f"CDC {content_type.replace('_', ' ').title()} for {disease}",
                        "content": self.normalizer.clean_text(section_content),
                        "source": "CDC",
                        "source_url": url,
                    })

                found += 1
                inserted += 1

            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                executor.map(process_disease, TARGET_DISEASES)

            # ── Part 2: Traveler Health for India ────────────────────────
            self.logger.info("Scraping CDC Traveler Health for India...")
            self._scrape_traveler_health()

        except Exception as e:
            error_msg = str(e)
            self.logger.error("CDC error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "diseases,guidelines",
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed,
        )

    def _scrape_traveler_health(self):
        """Extract India-specific health notices from CDC Traveler's Health."""
        url = CDC_TRAVELER_INDIA

        response_text, changed = self.fetch_with_cache(url)
        if not changed or not response_text:
            return

        soup = self.parse_html(response_text)
        if not soup:
            return

        content = soup.find("main") or soup.find("article")
        if not content:
            return

        sections = self.extract_sections_from_soup(content)
        for header, text in sections.items():
            if header == "full_text":
                continue

            # Check for disease keywords
            matched_disease = None
            for disease in TARGET_DISEASES:
                if disease.lower() in header.lower() or disease.lower() in text[:200].lower():
                    matched_disease = disease
                    break

            if matched_disease:
                disease_id = self.db.get_disease_id_by_name(
                    self.normalizer.normalize_disease_name(matched_disease)
                )
                if disease_id:
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": "travel_advisory",
                        "title": f"CDC India Travel Advisory: {matched_disease}",
                        "content": self.normalizer.clean_text(text),
                        "source": "CDC",
                        "source_url": url,
                    })
