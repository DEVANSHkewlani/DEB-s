"""
WHO (World Health Organization) Scraper
PRIORITY: HIGH

Extracts:
- Disease Outbreak News (DON) for India
- Disease factsheets with section-based content_type metadata
- RSS feed for India-related health news
- ChromaDB chunks for RAG
- Stores DON text in bulletin_texts
"""
import re
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
from base_scraper import BaseScraper
from config import (
    URLS, TARGET_DISEASES, WHO_SLUG_MAP, WHO_FACTSHEET_DISEASES,
    MAX_THREADS, HEALTH_KEYWORDS,
)


class WHOScraper(BaseScraper):
    def __init__(self):
        super().__init__("WHO")

    def run(self):
        started_at = datetime.now()
        found = inserted = updated = skipped = failed = 0
        error_msg = None

        try:
            # ── Part 1: Disease Factsheets (Section-based extraction) ────
            self.logger.info("Starting WHO Factsheet Scraping (section-based)...")
            fs_stats = self._scrape_factsheets()
            found += fs_stats["found"]
            inserted += fs_stats["inserted"]
            skipped += fs_stats["skipped"]
            failed += fs_stats["failed"]

            # ── Part 2: Disease Outbreak News ────────────────────────────
            self.logger.info("Starting WHO Disease Outbreak News Scraping...")
            don_stats = self._scrape_outbreak_news()
            found += don_stats["found"]
            inserted += don_stats["inserted"]
            skipped += don_stats["skipped"]
            failed += don_stats["failed"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("WHO scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "diseases,guidelines,outbreaks",
            "success" if error_msg is None else "error",
            found, inserted, updated, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed,
        )

    # ── Factsheet Scraping ───────────────────────────────────────────────────

    def _scrape_factsheets(self):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0}

        def process_disease(item):
            disease, slug = item
            try:
                url = f"{URLS['WHO_FACTSHEETS']}/detail/{slug}"

                # Change detection
                response_text, changed = self.fetch_with_cache(url)
                if not changed:
                    stats["skipped"] += 1
                    return

                if not response_text:
                    stats["skipped"] += 1
                    return

                soup = self.parse_html(response_text)
                if not soup:
                    stats["failed"] += 1
                    return

                content_div = soup.find("article", class_="sf-detail-body-wrapper")
                if not content_div:
                    content_div = soup.find("article") or soup.find("main")
                if not content_div:
                    stats["failed"] += 1
                    return

                # ── Section-based extraction ─────────────────────────────
                raw_sections = self.extract_sections_from_soup(content_div)

                # Map sections to content_types
                typed_sections = {}
                for header_text, content in raw_sections.items():
                    if header_text == "full_text":
                        continue
                    content_type = self.map_section_to_content_type(header_text)
                    typed_sections[content_type] = content

                # Extract metadata from full text
                all_text = raw_sections.get("full_text", "")
                incubation = self.normalizer.extract_incubation_period(all_text)
                mortality = self.normalizer.extract_mortality_rate(all_text)

                # ── Upsert disease record ────────────────────────────────
                disease_name = self.normalizer.normalize_disease_name(disease)
                disease_id = self.db.upsert_disease({
                    "name": disease_name,
                    "category": "Infectious",
                    "description": self.normalizer.clean_text(all_text[:1000]),
                    "symptoms": self.normalizer.clean_text(typed_sections.get("symptoms", "")),
                    "transmission_method": self.normalizer.clean_text(typed_sections.get("transmission", "")),
                    "incubation_period": incubation or "",
                    "risk_factors": self.normalizer.clean_text(typed_sections.get("risk_factors", "")),
                    "mortality_rate": mortality,
                    "source_urls": [url],
                })

                # ── Upsert guidelines per section ────────────────────────
                for content_type, content in typed_sections.items():
                    if not content or len(content.strip()) < 20:
                        continue

                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": content_type,
                        "title": f"WHO {content_type.replace('_', ' ').title()} for {disease}",
                        "content": self.normalizer.clean_text(content),
                        "source": "WHO",
                        "source_url": url,
                    })

                    # ── ChromaDB chunking ────────────────────────────────
                    chunks = self.chunk_medical_text(
                        content, url, disease_name, content_type, "WHO"
                    )
                    # ChromaDB insertion would go here if direct access is configured
                    # For now, the data is stored in disease_guidelines and can be
                    # embedded on the API side during RAG indexing

                stats["found"] += 1
                stats["inserted"] += 1

            except Exception as e:
                self.logger.warning("Error scraping WHO factsheet for %s: %s", disease, e)
                stats["failed"] += 1

        # Process all factsheet diseases in parallel
        items = list(WHO_FACTSHEET_DISEASES.items())
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            executor.map(process_disease, items)

        # Also process remaining TARGET_DISEASES using slug map
        remaining = []
        processed_diseases = set(WHO_FACTSHEET_DISEASES.keys())
        for disease in TARGET_DISEASES:
            if disease in processed_diseases:
                continue
            slug = WHO_SLUG_MAP.get(disease)
            if slug:
                remaining.append((disease, slug))

        if remaining:
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                executor.map(process_disease, remaining)

        return stats

    # ── Disease Outbreak News ────────────────────────────────────────────────

    def _scrape_outbreak_news(self):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0}

        try:
            html = self.fetch_html(URLS["WHO_DON"])
            soup = self.parse_html(html)
            if not soup:
                return stats

            # Find outbreak news items
            news_items = soup.find_all("div", class_="list-view--item")
            if not news_items:
                news_items = soup.find_all("a", class_="link-container")
            if not news_items:
                # Try broader selector
                news_items = soup.select("div.sf-list-vertical a, .list-view a")

            for item in news_items:
                try:
                    if item.name == "a":
                        link = item
                    else:
                        link = item.find("a")
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    if not href:
                        continue

                    url = href if href.startswith("http") else f"https://www.who.int{href}"

                    # Filter for India-related news
                    title_lower = title.lower()
                    india_related = any(kw in title_lower for kw in [
                        "india", "indian", "south-east asia", "searo",
                        "delhi", "mumbai", "kerala", "karnataka",
                    ])
                    if not india_related:
                        # Also check for diseases common in India
                        if not any(kw in title_lower for kw in [
                            "dengue", "malaria", "nipah", "cholera", 
                            "chikungunya", "encephalitis", "kala-azar",
                        ]):
                            continue

                    if self.is_already_scraped(url, table="outbreaks"):
                        stats["skipped"] += 1
                        continue

                    stats["found"] += 1

                    # Parse disease and location from title
                    parts = title.split(" - ")
                    disease_name = parts[0].strip()
                    location = parts[1].strip() if len(parts) > 1 else "India"

                    norm_disease = self.normalizer.normalize_disease_name(disease_name)
                    disease_id = self.db.get_disease_id_by_name(norm_disease)
                    if not disease_id:
                        disease_id = self.db.upsert_disease({
                            "name": norm_disease,
                            "category": "Infectious",
                        })

                    # Insert outbreak with high confidence
                    self.db.upsert_outbreak({
                        "disease_id": disease_id,
                        "state": location,
                        "district": "Unknown",
                        "reported_date": date.today(),
                        "source": "WHO",
                        "source_url": url,
                        "severity": "severe",  # WHO DONs are significant events
                        "status": "active",
                        "latitude": 0.0,
                        "longitude": 0.0,
                    })

                    # Store in bulletin_texts
                    self.db.upsert_bulletin_text({
                        "source": "WHO",
                        "disease_mentioned": norm_disease,
                        "state_mentioned": location if location != "India" else None,
                        "raw_text": title,
                        "published_date": date.today(),
                        "url": url,
                    })

                    stats["inserted"] += 1

                except Exception as e:
                    stats["failed"] += 1
                    self.logger.warning("Error processing WHO DON item: %s", e)

        except Exception as e:
            self.logger.warning("Error scraping WHO DON listing: %s", e)

        return stats
