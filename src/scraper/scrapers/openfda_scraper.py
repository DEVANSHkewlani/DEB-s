"""
OpenFDA Drug Data Scraper — Proactive bulk loading of common medicines
API-based (no HTML scraping).
"""
import re
import time
import logging
from datetime import datetime
from base_scraper import BaseScraper
from config import RATE_LIMIT_DELAY, TARGET_DISEASES, ESSENTIAL_MEDICINES

logger = logging.getLogger("scraper.openfda")


class OpenFDAScraper(BaseScraper):
    def __init__(self):
        super().__init__("OpenFDA")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0

        self.logger.info("Starting OpenFDA Drug Data Scraping...")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        stats_lock = threading.Lock()

        def process_drug(drug_name):
            nonlocal failed, found, skipped, inserted
            try:
                # We can't entirely avoid rate limits, but we can distribute requests reasonably.
                time.sleep(RATE_LIMIT_DELAY)
                api_url = (
                    f"https://api.fda.gov/drug/label.json"
                    f"?search=openfda.generic_name:\"{drug_name}\"&limit=1"
                )

                try:
                    resp = self.session.get(api_url, timeout=15)
                except Exception as e:
                    self.logger.debug("OpenFDA request failed for %s: %s", drug_name, e)
                    with stats_lock:
                        failed += 1
                    return

                if resp.status_code != 200:
                    with stats_lock:
                        skipped += 1
                    return

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    with stats_lock:
                        skipped += 1
                    return

                label = results[0]
                with stats_lock:
                    found += 1

                # Extract fields
                openfda = label.get("openfda", {})
                generic_names = openfda.get("generic_name", [drug_name])
                brand_names = openfda.get("brand_name", [])
                manufacturers = openfda.get("manufacturer_name", [])
                dosage_forms = openfda.get("dosage_form", [])
                # routes = openfda.get("route", []) # currently unused

                indications = " ".join(label.get("indications_and_usage", [""]))[:2000]
                warnings = " ".join(label.get("warnings", [""]))[:2000]
                dosage_admin = " ".join(label.get("dosage_and_administration", [""]))[:2000]
                interactions = " ".join(label.get("drug_interactions", [""]))[:2000]
                adverse = " ".join(label.get("adverse_reactions", [""]))[:2000]

                drug_data = {
                    "generic_name": generic_names[0] if generic_names else drug_name,
                    "brand_name": brand_names[0] if brand_names else None,
                    "manufacturer": manufacturers[0] if manufacturers else None,
                    "dosage_form": dosage_forms[0] if dosage_forms else None,
                    "source": "OpenFDA",
                    "source_url": api_url,
                }

                try:
                    self.db.upsert_medicine(drug_data)
                    with stats_lock:
                        inserted += 1
                except Exception as e:
                    self.logger.debug("Failed to insert medicine: %s", e)
                    with stats_lock:
                        failed += 1

                # Also store detailed label info as a guideline
                if indications:
                    # Find related disease
                    disease_id = 1
                    for disease in TARGET_DISEASES:
                        if disease.lower() in indications.lower() or disease.lower() in drug_name.lower():
                            did = self.db.get_disease_id_by_name(
                                self.normalizer.normalize_disease_name(disease)
                            )
                            if did:
                                disease_id = did
                                break

                    label_text = f"Indications: {indications}\n\n"
                    if dosage_admin:
                        label_text += f"Dosage: {dosage_admin}\n\n"
                    if warnings:
                        label_text += f"Warnings: {warnings}\n\n"
                    if interactions:
                        label_text += f"Interactions: {interactions}\n\n"
                    if adverse:
                        label_text += f"Adverse Reactions: {adverse}"

                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": "medications",
                        "title": f"OpenFDA Label: {drug_name}",
                        "content": self.normalizer.clean_text(label_text),
                        "source": "OpenFDA",
                        "source_url": api_url,
                    })

            except Exception as e:
                with stats_lock:
                    failed += 1
                self.logger.warning("Error processing %s: %s", drug_name, e)

        # Use 10 threads, since we are doing purely I/O-bound requests against OpenFDA
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_drug, d) for d in ESSENTIAL_MEDICINES]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Future failed in OpenFDA scraper: %s", e)

        completed_at = datetime.now()
        self.log_run("medicines,guidelines", "success", found, inserted, 0, skipped,
                     started_at=started_at, completed_at=completed_at, records_failed=failed)
