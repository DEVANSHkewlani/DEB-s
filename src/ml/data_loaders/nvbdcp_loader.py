"""
NVBDCP (National Vector Borne Disease Control Programme) Loader
PRIORITY: CRITICAL — primary source for annual historical data

One-time bulk loader (not a periodic scraper).
Downloads Excel/CSV files and reshapes wide-format data to long-format
for insertion into the trends table.

Usage:
    cd src/scraper && python3 -c "
    import sys; sys.path.insert(0, '.')
    from ml.data_loaders.nvbdcp_loader import NVBDCPLoader
    NVBDCPLoader().load_all()
    "
"""
import sys
import os
import re
import tempfile
import logging
from datetime import date

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scraper'))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install with: pip install pandas openpyxl")
    sys.exit(1)

from db import DatabaseManager
from normalizer import DataNormalizer
from base_scraper import BaseScraper
from config import NVBDCP_URLS

logger = logging.getLogger("loader.nvbdcp")


class NVBDCPLoader(BaseScraper):
    """
    One-time bulk loader for NVBDCP historical data.
    Downloads Excel files, reshapes from wide to long format,
    and inserts into the trends table.
    """

    DISEASE_MAP = {
        "DENGUE": "Dengue",
        "MALARIA": "Malaria",
        "CHIKUNGUNYA": "Chikungunya",
        "KALA_AZAR": "Kala-azar",
        "JE": "Japanese Encephalitis",
        "FILARIA": "Leptospirosis",  # Filaria not in TARGET — map to closest
    }

    def __init__(self):
        super().__init__("NVBDCP")

    def load_all(self):
        """Load historical data for all NVBDCP diseases."""
        logger.info("Starting NVBDCP Historical Data Load...")
        total_inserted = 0

        for key, url in NVBDCP_URLS.items():
            if key == "BASE":
                continue

            disease_name = self.DISEASE_MAP.get(key)
            if not disease_name:
                continue

            logger.info("Loading %s data from %s...", disease_name, key)
            try:
                count = self._load_disease(url, disease_name)
                total_inserted += count
                logger.info("  → Inserted %d records for %s", count, disease_name)
            except Exception as e:
                logger.error("Error loading %s: %s", disease_name, e)

        logger.info("NVBDCP load complete. Total records: %d", total_inserted)

    def _load_disease(self, page_url, disease_name):
        """
        Fetch the NVBDCP disease page, find Excel/CSV links,
        download and parse them.
        """
        inserted = 0

        html = self.fetch_html(page_url, use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            return 0

        # Find Excel / CSV download links
        data_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            if any(ext in href for ext in [".xls", ".xlsx", ".csv"]):
                full_url = link["href"]
                if not full_url.startswith("http"):
                    full_url = NVBDCP_URLS["BASE"] + "/" + full_url.lstrip("/")
                data_links.append(full_url)

        if not data_links:
            logger.info("No Excel/CSV links found for %s, trying HTML tables...", disease_name)
            inserted += self._extract_html_tables(soup, disease_name, page_url)
            return inserted

        for data_url in data_links:
            try:
                inserted += self._process_excel(data_url, disease_name)
            except Exception as e:
                logger.warning("Error processing %s: %s", data_url, e)

        return inserted

    def _process_excel(self, url, disease_name):
        """Download and parse an Excel/CSV file."""
        inserted = 0

        try:
            resp = self.session.get(url, timeout=60, verify=False)
            if resp.status_code != 200:
                return 0

            # Save to temp file
            suffix = ".xlsx" if ".xlsx" in url.lower() else ".xls" if ".xls" in url.lower() else ".csv"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(resp.content)
            tmp.close()

            try:
                if suffix == ".csv":
                    df = pd.read_csv(tmp.name)
                else:
                    df = pd.read_excel(tmp.name, engine="openpyxl" if suffix == ".xlsx" else None)
            except Exception:
                # Try alternative engine
                df = pd.read_excel(tmp.name)
            finally:
                os.remove(tmp.name)

            if df.empty:
                return 0

            # ── Reshape wide → long ──────────────────────────────────────
            # Typical NVBDCP format: State/UT in first column, years as headers
            first_col = df.columns[0]

            # Find year columns
            year_cols = [c for c in df.columns if self._is_year(c)]
            if not year_cols:
                # Try numeric columns as years
                year_cols = [c for c in df.columns[1:] if str(c).strip().isdigit()]

            if not year_cols:
                logger.info("No year columns found in %s", url)
                return 0

            # Melt to long format
            df_long = pd.melt(
                df,
                id_vars=[first_col],
                value_vars=year_cols,
                var_name="year",
                value_name="cases",
            )

            # Clean
            df_long["cases"] = pd.to_numeric(df_long["cases"], errors="coerce").fillna(0).astype(int)
            df_long["year"] = df_long["year"].astype(str).str.strip()
            df_long = df_long[df_long["cases"] > 0]

            # Get disease ID
            norm_name = self.normalizer.normalize_disease_name(disease_name)
            disease_id = self.db.get_disease_id_by_name(norm_name)
            if not disease_id:
                disease_id = self.db.upsert_disease({
                    "name": norm_name,
                    "category": "Infectious",
                })

            # Insert into trends
            for _, row in df_long.iterrows():
                state = self.normalizer.normalize_state(str(row[first_col]))
                if not state or state in ("Total", "India", "Grand Total"):
                    continue

                try:
                    year_str = str(row["year"]).strip()
                    year_int = int(float(year_str))
                    report_date = date(year_int, 12, 31)
                except (ValueError, OverflowError):
                    continue

                self.db.upsert_trend_greatest({
                    "disease_id": disease_id,
                    "state": state,
                    "district": "Unknown",
                    "period_type": "annual",
                    "period_start": report_date,
                    "cases_count": int(row["cases"]),
                    "source": "NVBDCP",
                    "source_url": url,
                    "source_confidence": "high",
                    "data_type": "annual",
                })
                inserted += 1

        except Exception as e:
            logger.warning("Error processing Excel %s: %s", url, e)

        return inserted

    def _extract_html_tables(self, soup, disease_name, source_url):
        """Fallback: extract data from HTML tables on the page."""
        inserted = 0

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            # Check header row for year-like columns
            header_cells = rows[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True) for c in header_cells]
            year_indices = [(i, h) for i, h in enumerate(headers) if self._is_year(h)]

            if not year_indices:
                continue

            norm_name = self.normalizer.normalize_disease_name(disease_name)
            disease_id = self.db.get_disease_id_by_name(norm_name)
            if not disease_id:
                disease_id = self.db.upsert_disease({"name": norm_name, "category": "Infectious"})

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                state = self.normalizer.normalize_state(cells[0].get_text(strip=True))
                if not state or state.lower() in ("total", "india", "grand total"):
                    continue

                for idx, year_str in year_indices:
                    if idx >= len(cells):
                        continue
                    try:
                        cases = int(re.sub(r'[^\d]', '', cells[idx].get_text(strip=True)) or 0)
                    except (ValueError, IndexError):
                        continue
                    if cases <= 0:
                        continue

                    year_int = int(year_str)
                    self.db.upsert_trend_greatest({
                        "disease_id": disease_id,
                        "state": state,
                        "district": "Unknown",
                        "period_type": "annual",
                        "period_start": date(year_int, 12, 31),
                        "cases_count": cases,
                        "source": "NVBDCP",
                        "source_url": source_url,
                        "source_confidence": "high",
                        "data_type": "annual",
                    })
                    inserted += 1

        return inserted

    @staticmethod
    def _is_year(value):
        """Check if a value looks like a year (2000-2030)."""
        try:
            v = int(str(value).strip())
            return 2000 <= v <= 2030
        except (ValueError, TypeError):
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    NVBDCPLoader().load_all()
