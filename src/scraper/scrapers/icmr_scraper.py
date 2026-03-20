"""
ICMR (Indian Council of Medical Research) Scraper
PRIORITY: HIGH — PDF-first extraction for clinical guidelines and dosage tables

Extracts:
- Clinical practice guidelines (PDFs)
- Drug dosage tables from guideline PDFs → medicines table
- Section-based content from numbered headings
"""
from datetime import datetime
from base_scraper import BaseScraper
from config import URLS, TARGET_DISEASES, ICMR_URLS
from pdf_parser import PDFParser
import re


class ICMRScraper(BaseScraper):
    def __init__(self):
        super().__init__("ICMR")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        self.logger.info("Starting ICMR Scraping (PDF-first)...")

        try:
            # Scrape guidelines page
            for page_key in ["PUBLICATIONS", "GUIDELINES"]:
                url = ICMR_URLS.get(page_key)
                if not url:
                    continue

                self.logger.info("Scraping ICMR %s page...", page_key)
                stats = self._scrape_page(url)
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]

            # Also scrape from legacy config URL
            if "ICMR" in URLS:
                stats = self._scrape_page(URLS["ICMR"])
                found += stats["found"]
                inserted += stats["inserted"]
                skipped += stats["skipped"]
                failed += stats["failed"]
                pdfs += stats["pdfs"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("ICMR scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "guidelines,medicines",
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed, pdfs_processed=pdfs,
        )

    def _scrape_page(self, url):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0, "pdfs": 0}

        html = self.fetch_html(url, use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            return stats

        from concurrent.futures import ThreadPoolExecutor, as_completed
        links = soup.find_all("a", href=True)
        
        def process_link(link):
            local_stats = {"found": 0, "inserted": 0, "failed": 0, "pdfs": 0, "skipped": 0}
            text = link.get_text(strip=True)
            href = link["href"]

            if not href or len(text) < 5:
                return local_stats

            full_url = href if href.startswith("http") else ICMR_URLS["BASE"] + "/" + href.lstrip("/")

            # ── PDF-first: prioritize PDFs ───────────────────────────────
            if any(ext in href.lower() for ext in [".pdf", ".PDF"]):
                if self.is_already_scraped(full_url, table="disease_guidelines"):
                    local_stats["skipped"] += 1
                    return local_stats

                local_stats["found"] += 1
                try:
                    self._process_guideline_pdf(full_url, text, local_stats)
                except Exception as e:
                    local_stats["failed"] += 1
                    self.logger.warning("Error processing ICMR PDF %s: %s", text[:50], e)
                return local_stats

            # ── HTML pages with health topic content ─────────────────────
            combined = (text + " " + href).lower()
            for disease in TARGET_DISEASES:
                if disease.lower() in combined:
                    if self.is_already_scraped(full_url, table="disease_guidelines"):
                        local_stats["skipped"] += 1
                        break

                    local_stats["found"] += 1
                    try:
                        self._process_disease_page(full_url, disease, text, local_stats)
                    except Exception as e:
                        local_stats["failed"] += 1
                        self.logger.warning("Error processing ICMR page: %s", e)
                    break
                    
            return local_stats

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_link, l) for l in links]
            for future in as_completed(futures):
                try:
                    s = future.result()
                    for k in stats:
                        stats[k] += s.get(k, 0)
                except Exception as e:
                    self.logger.error("Future failed in ICMR scraper: %s", e)

        return stats

    def _process_guideline_pdf(self, url, title, stats):
        """Download and extract content from an ICMR guideline PDF."""
        self.logger.info("Processing ICMR PDF: %s", title[:80])
        text = self.extract_pdf_from_url(url)
        if not text or len(text.strip()) < 100:
            stats["failed"] += 1
            return

        stats["pdfs"] += 1

        # Match disease from title and content
        matched_disease = None
        for disease in TARGET_DISEASES:
            if disease.lower() in (title + " " + text[:1000]).lower():
                matched_disease = disease
                break

        disease_id = 1
        if matched_disease:
            norm_name = self.normalizer.normalize_disease_name(matched_disease)
            did = self.db.get_disease_id_by_name(norm_name)
            if did:
                disease_id = did
            else:
                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "Infectious",
                })

        # ── Section identification from numbered headings ────────────────
        pdf_sections = self._extract_pdf_sections(text)

        for content_type, section_content in pdf_sections.items():
            if not section_content or len(section_content.strip()) < 20:
                continue

            self.db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": content_type,
                "title": f"ICMR {content_type.replace('_', ' ').title()} — {title[:100]}",
                "content": self.normalizer.clean_text(section_content[:5000]),
                "source": "ICMR",
                "source_url": url,
            })

        # Fallback: store entire PDF as general guideline
        if not pdf_sections:
            self.db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": "clinical_guideline",
                "title": f"ICMR: {title[:200]}",
                "content": self.normalizer.clean_text(text[:5000]),
                "source": "ICMR",
                "source_url": url,
            })

        # ── Extract dosage tables → medicines table ──────────────────────
        self._extract_dosage_info(text, url, disease_id)

        # Store raw text in bulletin_texts for LangChain
        self.db.upsert_bulletin_text({
            "source": "ICMR",
            "disease_mentioned": matched_disease,
            "raw_text": text[:50000],
            "published_date": None,
            "url": url,
        })

        stats["inserted"] += 1

    def _process_disease_page(self, url, disease, title, stats):
        """Process an HTML disease info page."""
        html = self.fetch_html(url)
        soup = self.parse_html(html)
        if not soup:
            stats["failed"] += 1
            return

        content = soup.find("div", class_="content") or soup.find("main") or soup.find("article")
        if not content:
            stats["failed"] += 1
            return

        norm_name = self.normalizer.normalize_disease_name(disease)
        disease_id = self.db.upsert_disease({
            "name": norm_name,
            "category": "Infectious",
            "source_urls": [url],
        })

        sections = self.extract_sections_from_soup(content)
        for header_text, section_content in sections.items():
            if header_text == "full_text":
                continue
            content_type = self.map_section_to_content_type(header_text)
            self.db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": content_type,
                "title": f"ICMR {content_type.replace('_', ' ').title()} for {disease}",
                "content": self.normalizer.clean_text(section_content),
                "source": "ICMR",
                "source_url": url,
            })

        stats["inserted"] += 1

    def _extract_pdf_sections(self, text):
        """
        Extract sections from PDF text using numbered headings.
        ICMR PDFs typically use: 1.0, 1.1, 2.0, etc.
        """
        sections = {}
        current_section = None
        current_content = []

        for line in text.split("\n"):
            line = line.strip()

            # Check for numbered section header: "1.0 Treatment" or "3. Diagnosis"
            match = re.match(r'^(\d+\.?\d*)\s+(.+)', line)
            if match:
                header_text = match.group(2).strip()

                # Save previous section
                if current_section and current_content:
                    content_type = self.map_section_to_content_type(current_section)
                    if content_type not in sections:
                        sections[content_type] = ""
                    sections[content_type] += "\n".join(current_content) + "\n\n"

                current_section = header_text
                current_content = []
            else:
                if line and current_section:
                    current_content.append(line)

        # Save last section
        if current_section and current_content:
            content_type = self.map_section_to_content_type(current_section)
            if content_type not in sections:
                sections[content_type] = ""
            sections[content_type] += "\n".join(current_content)

        return sections

    def _extract_dosage_info(self, text, source_url, disease_id):
        """
        Extract drug dosage information from PDF text.
        Looks for patterns like "Drug Name: 500mg twice daily"
        """
        dosage_patterns = [
            r'(\w+(?:\s+\w+)?)\s*(?::|–|-)\s*(\d+\s*(?:mg|g|ml|mcg|IU)(?:\s*/\s*(?:kg|day|dose|hour|d))?(?:\s+(?:once|twice|thrice|daily|weekly|hourly|BD|TDS|QID|OD|HS|PRN|SOS))?)',
            r'Tab\.\s*(\w+)\s+(\d+\s*mg)',
            r'Inj\.\s*(\w+)\s+(\d+\s*(?:mg|ml|mcg|IU))',
        ]

        for pattern in dosage_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                drug_name = match.group(1).strip()
                dosage = match.group(2).strip() if match.lastindex >= 2 else ""

                # Skip obvious non-drug words
                if drug_name.lower() in ("the", "and", "for", "with", "from", "this", "that", "dose", "tab"):
                    continue

                try:
                    self.db.upsert_medicine({
                        "generic_name": drug_name,
                        "dosage_form": "tablet",
                        "strength": dosage,
                        "source": "ICMR",
                        "source_url": source_url,
                    })
                except Exception:
                    pass
