"""
RxNav API Scraper — Drug class and interaction data
API-based (no HTML scraping needed).
"""
import time
import logging
from datetime import datetime
from base_scraper import BaseScraper
from config import RATE_LIMIT_DELAY, ESSENTIAL_MEDICINES

logger = logging.getLogger("scraper.rxnav")


class RxNavScraper(BaseScraper):
    def __init__(self):
        super().__init__("RxNav")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0

        self.logger.info("Starting RxNav API Scraping...")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        stats_lock = threading.Lock()

        def process_drug(drug_name):
            nonlocal failed, found, skipped, inserted
            try:
                # Moderate delay because RxNav might enforce rate limits
                time.sleep(RATE_LIMIT_DELAY)

                # Step 1: Get RxCUI
                rxcui = self._get_rxcui(drug_name)
                if not rxcui:
                    with stats_lock:
                        skipped += 1
                    return

                with stats_lock:
                    found += 1

                # Step 2: Get drug class
                drug_class = self._get_drug_class(rxcui)

                # Step 3: Get interactions
                interactions = self._get_interactions(rxcui)

                # Store drug info
                drug_data = {
                    "generic_name": drug_name,
                    "source": "RxNav",
                    "source_url": f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}",
                }

                try:
                    self.db.upsert_medicine(drug_data)
                    with stats_lock:
                        inserted += 1
                except Exception:
                    pass

                # Store interaction info as guideline
                if interactions:
                    interaction_text = "\n".join(interactions[:20])
                    self.db.upsert_guideline({
                        "disease_id": 1,
                        "guideline_type": "medications",
                        "title": f"Drug Interactions: {drug_name}",
                        "content": f"Drug Class: {drug_class or 'Unknown'}\n\n"
                                   f"Known Interactions:\n{interaction_text}",
                        "source": "RxNav",
                        "source_url": f"https://rxnav.nlm.nih.gov/REST/interaction/interaction.json?rxcui={rxcui}",
                    })

            except Exception as e:
                with stats_lock:
                    failed += 1
                self.logger.warning("Error processing %s: %s", drug_name, e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_drug, d) for d in ESSENTIAL_MEDICINES]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in RxNav scraper: %s", e)

        completed_at = datetime.now()
        self.log_run("medicines,guidelines", "success", found, inserted, 0, skipped,
                     started_at=started_at, completed_at=completed_at, records_failed=failed)

    def _get_rxcui(self, drug_name):
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                ids = data.get("idGroup", {}).get("rxnormId", [])
                return ids[0] if ids else None
        except Exception:
            pass
        return None

    def _get_drug_class(self, rxcui):
        url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}"
        try:
            time.sleep(0.5)
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
                if entries:
                    return entries[0].get("rxclassMinConceptItem", {}).get("className", "")
        except Exception:
            pass
        return None

    def _get_interactions(self, rxcui):
        url = f"https://rxnav.nlm.nih.gov/REST/interaction/interaction.json?rxcui={rxcui}"
        try:
            time.sleep(0.5)
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                groups = data.get("interactionTypeGroup", [])
                interactions = []
                for group in groups:
                    for itype in group.get("interactionType", []):
                        for pair in itype.get("interactionPair", []):
                            desc = pair.get("description", "")
                            if desc:
                                interactions.append(desc)
                return interactions
        except Exception:
            pass
        return []
