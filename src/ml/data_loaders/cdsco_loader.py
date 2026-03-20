"""
CDSCO (Central Drugs Standard Control Organisation) Loader
One-time bulk medicine seed.

Loads drug data by iterating through the CDSCO database.
Uses Playwright for JS-rendered content.

Usage:
    cd src/scraper && python3 -c "
    import sys; sys.path.insert(0, '.')
    from ml.data_loaders.cdsco_loader import CDSCOLoader
    CDSCOLoader().load_all()
    "
"""
import sys
import os
import re
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scraper'))

from db import DatabaseManager
from normalizer import DataNormalizer
from base_scraper import BaseScraper

logger = logging.getLogger("loader.cdsco")


class CDSCOLoader(BaseScraper):
    """
    One-time bulk loader for Indian drug data from CDSCO.
    Extracts brand names, generic names, manufacturers, schedule, strength.
    """

    BASE_URL = "https://cdscoonline.gov.in"

    def __init__(self):
        super().__init__("CDSCO")

    def load_all(self):
        logger.info("Starting CDSCO Drug Data Load...")
        total = 0

        try:
            total += self._scrape_approved_drugs()
        except Exception as e:
            logger.error("CDSCO loader error: %s", e)

        logger.info("CDSCO load complete. Total drug records: %d", total)

    def _scrape_approved_drugs(self):
        """Scrape the CDSCO approved drugs database."""
        inserted = 0

        # CDSCO uses dynamic JS pages — must use Playwright
        url = f"{self.BASE_URL}/CDSCO/Drugs"
        html = self.fetch_html(url, use_playwright=True)
        soup = self.parse_html(html)
        if not soup:
            logger.warning("Could not fetch CDSCO drugs page")
            return 0

        # Look for data tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Parse header
            header_cells = rows[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True).lower() for c in header_cells]

            # Identify column indices
            brand_idx = next((i for i, h in enumerate(headers) if "brand" in h or "trade" in h), None)
            generic_idx = next((i for i, h in enumerate(headers) if "generic" in h or "active" in h), None)
            manuf_idx = next((i for i, h in enumerate(headers) if "manufact" in h or "company" in h), None)
            dosage_idx = next((i for i, h in enumerate(headers) if "dosage" in h or "form" in h), None)
            strength_idx = next((i for i, h in enumerate(headers) if "strength" in h), None)
            schedule_idx = next((i for i, h in enumerate(headers) if "schedule" in h), None)

            if generic_idx is None and brand_idx is None:
                continue

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < max(filter(None, [brand_idx, generic_idx, 1])):
                    continue

                drug_data = {}
                if brand_idx is not None and brand_idx < len(cells):
                    drug_data["brand_name"] = cells[brand_idx].get_text(strip=True)
                if generic_idx is not None and generic_idx < len(cells):
                    drug_data["generic_name"] = cells[generic_idx].get_text(strip=True)
                if manuf_idx is not None and manuf_idx < len(cells):
                    drug_data["manufacturer"] = cells[manuf_idx].get_text(strip=True)
                if dosage_idx is not None and dosage_idx < len(cells):
                    drug_data["dosage_form"] = cells[dosage_idx].get_text(strip=True)
                if strength_idx is not None and strength_idx < len(cells):
                    drug_data["strength"] = cells[strength_idx].get_text(strip=True)
                if schedule_idx is not None and schedule_idx < len(cells):
                    drug_data["schedule"] = cells[schedule_idx].get_text(strip=True)

                # Must have at least generic_name
                if not drug_data.get("generic_name"):
                    continue

                drug_data["source"] = "CDSCO"
                drug_data["source_url"] = url

                try:
                    self.db.upsert_medicine(drug_data)
                    inserted += 1
                except Exception as e:
                    logger.debug("Drug insert error: %s", e)

        return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    CDSCOLoader().load_all()
