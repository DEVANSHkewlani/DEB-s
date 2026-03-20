import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Add the parent directory to sys.path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TARGET_DISEASES, MAX_THREADS
from db import DatabaseManager
from api_loaders import APIDataLoader

def enrich_disease_data():
    db = DatabaseManager()
    
    start_time = datetime.now()
    print("="*60)
    print("DEB's Health Navigator — Disease Knowledge Enrichment")
    print(f"Started at: {start_time}")
    print("="*60)

    # 1. First, ensure all diseases from config are in the DB
    print(f"\n[1/3] Synchronizing {len(TARGET_DISEASES)} diseases from config.py...")
    for disease in TARGET_DISEASES:
        db.upsert_disease({
            "name": disease,
            "category": "General Health" 
        })

    # 2. Run API loaders instead of old scrapers
    print(f"\n[2/3] Running API loaders to collect and unify data...")
    loader = APIDataLoader()
    loader.run(mode='all')

    # 3. Final Integration & Summary Report
    print(f"\n[3/3] Finalizing data integration and generating summary...")
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Fetch final stats
    diseases_total = db.execute_query("SELECT count(*) FROM diseases", fetch=True)[0]
    diseases_enriched = db.execute_query("SELECT count(*) FROM diseases WHERE description IS NOT NULL AND description != ''", fetch=True)[0]
    outbreaks_total = db.execute_query("SELECT count(*) FROM outbreaks", fetch=True)[0]
    guidelines_total = db.execute_query("SELECT count(*) FROM disease_guidelines", fetch=True)[0]
    
    print("\n" + "#"*60)
    print(" DATA COLLECTION COMPLETED SUCCESSFULLY ".center(60, "#"))
    print("#"*60)
    print(f"\nSummary of Scraped Data:")
    print(f"- Total Duration:    {str(duration).split('.')[0]}")
    print(f"- Total Diseases:    {diseases_total}")
    print(f"- Enriched Diseases: {diseases_enriched} ({int(diseases_enriched/diseases_total*100) if diseases_total > 0 else 0}%)")
    print(f"- Total Outbreaks:   {outbreaks_total}")
    print(f"- Total Guidelines:  {guidelines_total}")
    print("\n" + "#"*60)

if __name__ == "__main__":
    enrich_disease_data()

