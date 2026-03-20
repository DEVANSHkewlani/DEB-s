"""
IDSP (Integrated Disease Surveillance Programme) Scraper
PRIORITY: CRITICAL — highest value source in the entire system

Extracts:
- Weekly PDF bulletins with state/disease/cases/deaths tables
- Real-time HTML alert table for active outbreaks
- Stores raw bulletin text in bulletin_texts for LangChain context
"""
import re
import hashlib
from datetime import datetime, date
from base_scraper import BaseScraper
from config import IDSP_URLS, TARGET_DISEASES
from pdf_parser import PDFParser


class IDSPScraper(BaseScraper):
    def __init__(self):
        super().__init__("IDSP")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = pdfs = 0
        error_msg = None

        try:
            # ── Part 1: PDF Bulletin Extraction ──────────────────────────
            self.logger.info("Starting IDSP PDF bulletin scraping...")
            pdf_stats = self._scrape_pdf_bulletins()
            found += pdf_stats["found"]
            inserted += pdf_stats["inserted"]
            skipped += pdf_stats["skipped"]
            failed += pdf_stats["failed"]
            pdfs += pdf_stats["pdfs"]

            # ── Part 2: HTML Real-time Alert Table ───────────────────────
            self.logger.info("Starting IDSP real-time alert scraping...")
            alert_stats = self._scrape_alert_table()
            found += alert_stats["found"]
            inserted += alert_stats["inserted"]
            skipped += alert_stats["skipped"]
            failed += alert_stats["failed"]

        except Exception as e:
            error_msg = str(e)
            self.logger.error("IDSP scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run(
            "outbreaks,trends,bulletins", 
            "success" if error_msg is None else "error",
            found, inserted, 0, skipped,
            error=error_msg,
            started_at=started_at, completed_at=completed_at,
            records_failed=failed, pdfs_processed=pdfs,
        )

    # ── PDF Bulletin Scraping ────────────────────────────────────────────────

    def _scrape_pdf_bulletins(self):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0, "pdfs": 0}

        # Fetch the bulletin listing page
        html = self.fetch_html(IDSP_URLS["WEEKLY_BULLETIN"], use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            self.logger.warning("Could not fetch IDSP bulletin listing page")
            return stats

        # Find all PDF links
        pdf_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if ".pdf" in href.lower():
                full_url = href if href.startswith("http") else IDSP_URLS["BASE"] + "/" + href.lstrip("/")
                pdf_links.append((full_url, link.get_text(strip=True)))

        from concurrent.futures import ThreadPoolExecutor, as_completed
        self.logger.info("Found %d PDF links on IDSP bulletin page", len(pdf_links))

        def process_pdf(pdf_url, title):
            local_stats = {"found": 0, "inserted": 0, "failed": 0, "pdfs": 0, "skipped": 0}
            # Check if already processed (using URL hash in scraper_logs)
            url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
            if self.is_already_scraped(pdf_url, table="disease_guidelines"):
                local_stats["skipped"] += 1
                return local_stats

            try:
                self.logger.info("Processing IDSP PDF: %s", title[:80])
                text = self.extract_pdf_from_url(pdf_url)
                if not text or len(text.strip()) < 100:
                    local_stats["failed"] += 1
                    return local_stats

                local_stats["pdfs"] += 1

                # Extract week number and date from title/text
                week_num, bulletin_date = self._extract_week_info(title, text)

                # Extract structured data rows: State | Disease | Cases | Deaths
                rows = self._extract_outbreak_rows(text)
                local_stats["found"] += len(rows)

                for row in rows:
                    try:
                        disease_name = self.normalizer.normalize_disease_name(row["disease"])
                        state_name = self.normalizer.normalize_state(row["state"])
                        disease_id = self.db.get_disease_id_by_name(disease_name)
                        if not disease_id:
                            disease_id = self.db.upsert_disease({
                                "name": disease_name,
                                "category": "Infectious",
                            })

                        # Insert into outbreaks
                        self.db.upsert_outbreak_greatest({
                            "disease_id": disease_id,
                            "state": state_name or "Unknown",
                            "district": row.get("district", "Unknown"),
                            "cases_reported": row.get("cases", 0),
                            "deaths_reported": row.get("deaths", 0),
                            "reported_date": bulletin_date or date.today(),
                            "source": "IDSP",
                            "source_url": pdf_url,
                            "severity": self.normalizer.compute_severity(
                                row.get("cases", 0), row.get("deaths", 0)
                            ),
                            "status": row.get("status", "active"),
                            "latitude": 0.0,
                            "longitude": 0.0,
                        })

                        # Insert into trends
                        self.db.upsert_trend_greatest({
                            "disease_id": disease_id,
                            "state": state_name or "Unknown",
                            "district": row.get("district", "Unknown"),
                            "period_type": "weekly",
                            "period_start": bulletin_date or date.today(),
                            "cases_count": row.get("cases", 0),
                            "source": "IDSP",
                            "source_url": pdf_url,
                            "source_confidence": "high",
                            "data_type": "weekly",
                            "report_week": week_num,
                        })

                        local_stats["inserted"] += 1
                    except Exception as e:
                        local_stats["failed"] += 1
                        self.logger.warning("Failed to insert IDSP row: %s", e)

                # Store raw text in bulletin_texts for LangChain
                self.db.upsert_bulletin_text({
                    "source": "IDSP",
                    "disease_mentioned": None,  # multiple diseases in one bulletin
                    "state_mentioned": None,
                    "raw_text": text[:50000],  # cap at 50k chars
                    "published_date": bulletin_date or date.today(),
                    "url": pdf_url,
                    "week_number": week_num,
                })

            except Exception as e:
                local_stats["failed"] += 1
                self.logger.warning("Error processing IDSP PDF %s: %s", pdf_url, e)
                
            return local_stats

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_pdf, p[0], p[1]) for p in pdf_links]
            for future in as_completed(futures):
                try:
                    s = future.result()
                    for k in stats:
                        stats[k] += s.get(k, 0)
                except Exception as e:
                    self.logger.error("Future failed in IDSP scraper: %s", e)

        return stats

    # ── HTML Alert Table Scraping ────────────────────────────────────────────

    def _scrape_alert_table(self):
        stats = {"found": 0, "inserted": 0, "skipped": 0, "failed": 0}

        html = self.fetch_html(IDSP_URLS["STATE_REPORTS"], use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            self.logger.warning("Could not fetch IDSP alert page")
            return stats

        # Look for HTML tables with outbreak data
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Check if this looks like an outbreak table
            header_row = rows[0].get_text(strip=True).lower()
            if not any(kw in header_row for kw in ["disease", "state", "cases", "outbreak"]):
                continue

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                try:
                    cell_texts = [c.get_text(strip=True) for c in cells]
                    # Try to identify columns
                    parsed = self._parse_table_row(cell_texts)
                    if not parsed:
                        continue

                    stats["found"] += 1

                    disease_name = self.normalizer.normalize_disease_name(parsed["disease"])
                    state_name = self.normalizer.normalize_state(parsed.get("state", ""))
                    disease_id = self.db.get_disease_id_by_name(disease_name)
                    if not disease_id:
                        disease_id = self.db.upsert_disease({
                            "name": disease_name,
                            "category": "Infectious",
                        })

                    self.db.upsert_outbreak_greatest({
                        "disease_id": disease_id,
                        "state": state_name or "Unknown",
                        "district": parsed.get("district", "Unknown"),
                        "cases_reported": parsed.get("cases", 0),
                        "deaths_reported": parsed.get("deaths", 0),
                        "reported_date": date.today(),
                        "source": "IDSP",
                        "source_url": IDSP_URLS["STATE_REPORTS"],
                        "severity": self.normalizer.compute_severity(
                            parsed.get("cases", 0), parsed.get("deaths", 0)
                        ),
                        "status": parsed.get("status", "active"),
                        "latitude": 0.0,
                        "longitude": 0.0,
                    })
                    stats["inserted"] += 1

                except Exception as e:
                    stats["failed"] += 1
                    self.logger.warning("Failed to parse IDSP alert row: %s", e)

        return stats

    # ── Helper Methods ───────────────────────────────────────────────────────

    def _extract_week_info(self, title, text):
        """Extract ISO week number and date from bulletin title/text."""
        week_num = None
        bulletin_date = None

        # "Week 20, 2024" or "W20/2024"
        week_match = re.search(r'[Ww](?:eek)?\s*(\d{1,2})[,/\s]+(\d{4})', title + " " + text[:500])
        if week_match:
            week_num = int(week_match.group(1))
            year = int(week_match.group(2))
            try:
                bulletin_date = datetime.strptime(f'{year}-W{week_num:02d}-1', '%G-W%V-%u').date()
            except (ValueError, OverflowError):
                pass

        if not bulletin_date:
            # Try to find a date in the title
            date_match = re.search(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', title)
            if date_match:
                try:
                    bulletin_date = self.normalizer.normalize_date(date_match.group(0))
                except Exception:
                    pass

        return week_num, bulletin_date

    def _extract_outbreak_rows(self, text):
        """
        Extract structured outbreak rows from PDF text.
        IDSP bulletins typically have: State | Disease | Cases | Deaths | Status
        """
        rows = []
        lines = text.split("\n")

        current_disease = None
        current_state = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line is a disease section header
            for disease in TARGET_DISEASES:
                if disease.lower() in line.lower() and len(line) < 100:
                    current_disease = disease
                    break

            # Try to extract state + numbers pattern
            # Pattern: State Name (possibly multi-word) followed by numbers
            match = re.match(
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Pradesh|Nadu|Bengal|Kashmir|Islands?))?)'
                r'\s+(\d+)\s+(\d+)',
                line
            )
            if match:
                state_text = match.group(1).strip()
                cases = int(match.group(2))
                deaths = int(match.group(3))

                normalized_state = self.normalizer.normalize_state(state_text)
                if normalized_state and current_disease:
                    rows.append({
                        "state": normalized_state,
                        "disease": current_disease,
                        "cases": cases,
                        "deaths": deaths,
                        "status": "active",
                    })
                continue

            # Alternative: Disease | State | District | Cases | Deaths
            parts = re.split(r'\s{2,}|\t', line)
            if len(parts) >= 4:
                try:
                    # Try to find numeric columns
                    numeric_indices = [i for i, p in enumerate(parts) if p.strip().isdigit()]
                    if len(numeric_indices) >= 2:
                        # Assume text columns come first, numbers last
                        text_parts = [p for i, p in enumerate(parts) if i not in numeric_indices]
                        disease_text = text_parts[0] if text_parts else current_disease
                        state_text = text_parts[1] if len(text_parts) > 1 else current_state

                        disease_name = self.normalizer.normalize_disease_name(disease_text)
                        if disease_name in TARGET_DISEASES:
                            rows.append({
                                "state": self.normalizer.normalize_state(state_text) or "Unknown",
                                "disease": disease_name,
                                "cases": int(parts[numeric_indices[0]]),
                                "deaths": int(parts[numeric_indices[1]]) if len(numeric_indices) > 1 else 0,
                                "status": "active",
                            })
                except (ValueError, IndexError):
                    pass

        return rows

    def _parse_table_row(self, cells):
        """Parse a single HTML table row into a structured dict."""
        if len(cells) < 3:
            return None

        # Try to identify which cells are disease, state, cases, deaths
        disease = None
        state = None
        cases = 0
        deaths = 0

        for cell in cells:
            cell = cell.strip()
            if not cell:
                continue

            # Check if it's a number
            if cell.isdigit():
                num = int(cell)
                if cases == 0:
                    cases = num
                else:
                    deaths = num
                continue

            # Check if it matches a disease
            norm = self.normalizer.normalize_disease_name(cell)
            if norm in TARGET_DISEASES and not disease:
                disease = norm
                continue

            # Check if it matches a state
            norm_state = self.normalizer.normalize_state(cell)
            if norm_state and not state:
                state = norm_state
                continue

        if disease:
            return {
                "disease": disease,
                "state": state or "Unknown",
                "district": "Unknown",
                "cases": cases,
                "deaths": deaths,
                "status": "active",
            }
        return None
