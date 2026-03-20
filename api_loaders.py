import os
import sys
import time
import logging
import argparse
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

# Setup paths so it works both standalone at root and imported by src/scraper/ scripts
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRAPER_DIR = os.path.join(PROJECT_ROOT, "src", "scraper")
if SCRAPER_DIR not in sys.path:
    sys.path.insert(0, SCRAPER_DIR)

from db import DatabaseManager
from state_coordinates import get_state_coordinates
try:
    from config import TARGET_DISEASES, API_CACHE_ENABLED, API_TIMEOUT, API_RETRIES, API_USER_AGENT, WHO_INDICATOR_MAP
except ImportError:
    TARGET_DISEASES = []
    API_CACHE_ENABLED = True
    API_TIMEOUT = 15
    API_RETRIES = 2
    API_USER_AGENT = "DEBsHealthNavigator/1.0 (health research project)"
    WHO_INDICATOR_MAP = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api_loaders")

class APIDataLoader:
    def __init__(self):
        self.db = DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": API_USER_AGENT})
        self.source_name = "APIDataLoader"

    def _get(self, url, params=None):
        """Shared GET with retries and timeout."""
        for attempt in range(API_RETRIES + 1):
            try:
                response = self.session.get(url, params=params, timeout=API_TIMEOUT)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == API_RETRIES:
                    logger.error(f"[ERROR] Request failed after {API_RETRIES + 1} attempts for {url}: {e}")
                    raise
                time.sleep(1)

    def _strip_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        return " ".join(text.split())

    def load_medlineplus(self, disease_name):
        """Fetch description, symptoms, and summaries from MedlinePlus."""
        # Cache check
        if API_CACHE_ENABLED:
            existing = self.db.execute_query(
                "SELECT description FROM diseases WHERE name = %s", (disease_name,), fetch=True
            )
            if existing and existing[0]:
                print(f"  [SKIP] {disease_name} — already in DB (MedlinePlus)")
                return None

        url = "https://wsearch.nlm.nih.gov/ws/query"
        params = {"db": "healthTopics", "term": disease_name, "rettype": "topic"}
        
        try:
            resp = self._get(url, params=params)
            time.sleep(0.8)  # Rate limit: 85 req/min
            
            root = ET.fromstring(resp.content)
            # Find the first document
            doc = root.find(".//document")
            if not doc:
                print(f"  [SKIP] {disease_name} — no results found (MedlinePlus)")
                return None

            full_summary_tag = doc.find(".//content[@name='FullSummary']")
            snippet_tag = doc.find(".//content[@name='snippet']")
            
            description = ""
            if full_summary_tag is not None and full_summary_tag.text:
                description = self._strip_html(full_summary_tag.text)
            elif snippet_tag is not None and snippet_tag.text:
                description = self._strip_html(snippet_tag.text)

            if description:
                description = description[:2000]

                # Update diseases table
                disease_id = self.db.upsert_disease({
                    "name": disease_name,
                    "description": description
                })

                # Insert summary guideline
                if disease_id:
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": "summary",
                        "title": "MedlinePlus Summary",
                        "content": description,
                        "source": "MedlinePlus/NIH",
                        "source_url": doc.attrib.get('url', "https://medlineplus.gov/")
                    })
                
                print(f"  [OK]   {disease_name} — description updated ({len(description)} chars)")
                return {"description": description}
            else:
                print(f"  [SKIP] {disease_name} — empty description (MedlinePlus)")
                return None
        except Exception as e:
            print(f"  [SKIP] {disease_name} — {str(e)} (MedlinePlus)")
            return None

    def load_who_gho(self, disease_name):
        """Fetch statistics/trends from WHO GHO OData API."""
        indicator_code = WHO_INDICATOR_MAP.get(disease_name)
        if not indicator_code:
            print(f"  [SKIP] {disease_name} — no WHO GHO mapping")
            return None

        url = f"https://ghoapi.azureedge.net/api/{indicator_code}"
        params = {
            "$filter": "SpatialDim eq 'IND'",
            "$orderby": "TimeDim desc",
            "$top": 5
        }
        
        try:
            resp = self._get(url, params=params)
            time.sleep(0.5)
            
            data = resp.json()
            values = data.get("value", [])
            
            if not values:
                print(f"  [SKIP] {disease_name} — no data from WHO GHO")
                return None
                
            # Get disease_id
            disease_id = self.db.get_disease_id_by_name(disease_name)
            if not disease_id:
                disease_id = self.db.upsert_disease({"name": disease_name})

            trends_added = 0
            latest_val = None
            
            for item in values:
                year = item.get("TimeDim")
                val_num = item.get("NumericValue")
                
                if val_num is not None and year is not None:
                    if latest_val is None:
                        latest_val = val_num
                        
                    period_start = datetime(int(year), 1, 1).date()
                    self.db.upsert_trend({
                        "disease_id": disease_id,
                        "state": "National",
                        "district": None,
                        "period_type": "annual",
                        "period_start": period_start,
                        "cases_count": int(val_num),
                        "source": "WHO GHO"
                    })
                    trends_added += 1

            if latest_val is not None:
                self.db.upsert_disease({
                    "name": disease_name,
                    "mortality_rate": latest_val # Using numeric value as rate statistic based on indicator
                })

            print(f"  [OK]   {disease_name} — mortality_rate updated, {trends_added} trend records added")
            return {"trends_added": trends_added}

        except Exception as e:
            print(f"  [SKIP] {disease_name} — {str(e)} (WHO GHO)")
            return None

    def load_nih_icd(self, disease_name):
        """Map disease name to ICD-10 code using NIH Clinical Tables API."""
        if API_CACHE_ENABLED:
            existing = self.db.execute_query(
                "SELECT icd_code FROM diseases WHERE name = %s", (disease_name,), fetch=True
            )
            if existing and existing[0]:
                print(f"  [SKIP] {disease_name} — icd_code already set")
                return None

        url = "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search"
        params = {
            "terms": disease_name.title(),
            "ef": "icd10cm,consumer_name",
            "maxList": 3
        }

        try:
            resp = self._get(url, params=params)
            time.sleep(0.3)
            
            data = resp.json()
            # Data format: [total, [codes], null, [[name, icd10cm, consumer_name], ...]]
            if len(data) >= 4 and len(data[3]) > 0:
                first_match = data[3][0]
                icd10cm = first_match[1]
                consumer_name = first_match[2]

                if icd10cm:
                    update_data = {"name": disease_name, "icd_code": icd10cm}
                    if consumer_name and isinstance(consumer_name, str):
                        update_data["common_names"] = [consumer_name]
                        
                    self.db.upsert_disease(update_data)
                    print(f"  [OK]   {disease_name} — icd_code: {icd10cm}")
                    return {"icd_code": icd10cm}

            print(f"  [SKIP] {disease_name} — no ICD code found (NIH)")
            return None
            
        except Exception as e:
            print(f"  [SKIP] {disease_name} — {str(e)} (NIH ICD)")
            return None

    def load_cdc_articles(self, disease_name):
        """Fetch prevention guidelines and articles from CDC."""
        url = "https://tools.cdc.gov/api/v2/resources/media"
        params = {
            "topic": disease_name,
            "mediaTypes": "Article",
            "sort": "date",
            "max": 3
        }
        
        try:
            resp = self._get(url, params=params)
            time.sleep(0.3)
            
            data = resp.json()
            results = data.get("results", [])
            
            if not results:
                print(f"  [SKIP] {disease_name} — no articles from CDC")
                return None

            disease_id = self.db.get_disease_id_by_name(disease_name)
            if not disease_id:
                disease_id = self.db.upsert_disease({"name": disease_name})

            guidelines_added = 0
            for item in results:
                title = item.get("name")
                desc = self._strip_html(item.get("description", ""))
                source_url = item.get("sourceUrl")
                
                if title and desc:
                    self.db.upsert_guideline({
                        "disease_id": disease_id,
                        "guideline_type": "prevention",
                        "title": title[:255],
                        "content": desc,
                        "source": "CDC",
                        "source_url": source_url
                    })
                    guidelines_added += 1

            if guidelines_added > 0:
                print(f"  [OK]   {disease_name} — {guidelines_added} guidelines added (CDC)")
            else:
                print(f"  [SKIP] {disease_name} — no valid articles found (CDC)")
            
            return {"guidelines_added": guidelines_added}

        except Exception as e:
            print(f"  [SKIP] {disease_name} — {str(e)} (CDC Articles)")
            return None

    def load_who_outbreaks(self):
        """Fetch global outbreak news from WHO."""
        url = "https://www.who.int/api/news/diseaseoutbreaknews"
        try:
            resp = self._get(url)
            time.sleep(0.3)
            
            data = resp.json()
            outbreaks_list = data.get("value", [])
            if not isinstance(outbreaks_list, list):
                print("  [SKIP] WHO Outbreaks returned invalid data format")
                return []

            print(f"  [OK]   {len(outbreaks_list)} outbreak events fetched")
            
            upserted_count = 0
            matched_diseases = {}
            
            for item in outbreaks_list:
                title = item.get("Title", "")
                summary = item.get("Summary", "") + " " + item.get("Overview", "")
                
                # Some APIs have tags, others don't, we just check the text body
                date_str = item.get("PublicationDate")
                
                if not date_str:
                    continue
                    
                # Parse date
                try:
                    rep_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
                except ValueError:
                    rep_date = datetime.now().date()
                
                # Check target diseases
                text_to_search = (title + " " + summary).lower()
                
                # Assign severity based on text
                severity = "low"
                if "critical" in text_to_search or "death" in text_to_search or "fatal" in text_to_search:
                    severity = "severe"
                elif "warning" in text_to_search or "severe" in text_to_search:
                    severity = "moderate"
                
                for disease_name in TARGET_DISEASES:
                    if disease_name.lower() in text_to_search:
                        disease_id = self.db.get_disease_id_by_name(disease_name)
                        if not disease_id:
                            disease_id = self.db.upsert_disease({"name": disease_name})
                            
                        # Try to get coordinates for India generically
                        coords = get_state_coordinates("India")
                        if not coords:
                            coords = {"lat": 20.5937, "lon": 78.9629}
                            
                        self.db.upsert_outbreak({
                            "disease_id": disease_id,
                            "state": "National",
                            "district": None,
                            "cases_reported": 0, # Cannot reliably parse count, leaving at 0
                            "reported_date": rep_date,
                            "source": "WHO Outbreak News",
                            "severity": severity,
                            "latitude": coords["lat"],
                            "longitude": coords["lon"]
                        })
                        upserted_count += 1
                        matched_diseases[disease_name] = matched_diseases.get(disease_name, 0) + 1
            
            for d, c in matched_diseases.items():
                print(f"  [MATCH] {d} — {c} outbreaks upserted")
            
            return data
                
        except Exception as e:
            print(f"  [SKIP] Failed to fetch WHO Outbreaks: {str(e)}")
            return []

    def enrich_all_diseases(self):
        """Iterate all target diseases through disease-level APIs."""
        print(f"\n[1/5] MedlinePlus (NIH) — Disease descriptions & summaries")
        for disease in TARGET_DISEASES:
            self.load_medlineplus(disease)
            
        print(f"\n[2/5] NIH Clinical Tables — ICD-10 codes & synonyms")
        for disease in TARGET_DISEASES:
            self.load_nih_icd(disease)
            
        print(f"\n[3/5] CDC Content API — Prevention guidelines")
        for disease in TARGET_DISEASES:
            self.load_cdc_articles(disease)

    def load_all_trends(self):
        """Fetch WHO GHO data for mapped diseases."""
        print(f"\n[4/5] WHO GHO API — India statistics & trends")
        for disease in TARGET_DISEASES:
            self.load_who_gho(disease)

    def refresh_outbreaks(self):
        """Fetch WHO Outbreaks."""
        print(f"\n[5/5] WHO Outbreak News — Live alerts")
        self.load_who_outbreaks()

    def run(self, mode='all'):
        start_time = datetime.now()
        print("="*60)
        print("DEB's Health Navigator — API Data Loader")
        print(f"Started at: {start_time}")
        print(f"Mode: {mode} | Diseases: {len(TARGET_DISEASES)}")
        print("="*60)
        
        if mode in ('all', 'diseases'):
            # Basic sync
            for disease in TARGET_DISEASES:
                self.db.upsert_disease({
                    "name": disease,
                    "category": "General Health"
                })
            self.enrich_all_diseases()
            
        if mode in ('all', 'trends'):
            self.load_all_trends()
            
        if mode in ('all', 'outbreaks'):
            self.refresh_outbreaks()
            
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Stats summary
        diseases_enriched = self.db.execute_query("SELECT count(*) FROM diseases WHERE description IS NOT NULL AND description != ''", fetch=True)[0]
        outbreaks_total = self.db.execute_query("SELECT count(*) FROM outbreaks", fetch=True)[0]
        guidelines_total = self.db.execute_query("SELECT count(*) FROM disease_guidelines", fetch=True)[0]
        trends_total = self.db.execute_query("SELECT count(*) FROM trends", fetch=True)[0]
        
        print("\n" + "="*60)
        print(f"COMPLETED in {str(duration).split('.')[0]}")
        print(f"- Diseases enriched: {diseases_enriched}/{len(TARGET_DISEASES)}")
        print(f"- Guidelines added:  {guidelines_total}")
        print(f"- Outbreaks upserted: {outbreaks_total}")
        print(f"- Trend records added: {trends_total}")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="DEB's Health Navigator — API Data Loader")
    parser.add_argument("--diseases", action="store_true", help="Only enrich disease descriptions/ICD/guidelines")
    parser.add_argument("--outbreaks", action="store_true", help="Only refresh outbreak alerts from WHO")
    parser.add_argument("--trends", action="store_true", help="Only fetch WHO GHO trend data")
    parser.add_argument("--disease", type=str, help="Run all loaders for one specific disease")
    args = parser.parse_args()

    loader = APIDataLoader()
    
    if args.disease:
        # One disease specifically
        print(f"Running pipeline for disease: {args.disease}")
        loader.db.upsert_disease({"name": args.disease, "category": "General Health"})
        loader.load_medlineplus(args.disease)
        loader.load_nih_icd(args.disease)
        loader.load_cdc_articles(args.disease)
        loader.load_who_gho(args.disease)
        return

    mode = 'all'
    if args.diseases: mode = 'diseases'
    elif args.outbreaks: mode = 'outbreaks'
    elif args.trends: mode = 'trends'
    elif any([args.diseases, args.outbreaks, args.trends]):
        pass 

    loader.run(mode=mode)

if __name__ == "__main__":
    main()
