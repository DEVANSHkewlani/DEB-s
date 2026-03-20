"""
Scraper Orchestrator — runs all scrapers in priority order with frequency control.

Usage:
    python3 main.py                  # Run all due scrapers
    python3 main.py --daily          # Run only daily scrapers
    python3 main.py --weekly         # Run only weekly scrapers
    python3 main.py --force          # Force all scrapers regardless of schedule
    python3 main.py --audit          # Run only the data quality audit
"""
import sys
import os
import time
import logging
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Ensure scraper directory is in path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scraper'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scraper', 'scrapers'))

from scraper.db import DatabaseManager
from scraper.config import MAX_THREADS

# ── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scraper.main")


# ── Scraper Registry ────────────────────────────────────────────────────────
# Format: (name, import_path, class_name, frequency_days, priority)
SCRAPER_REGISTRY = [
    # Priority 1: Outbreak & Trends (daily)
    ("IDSP",            "scrapers.idsp_scraper",       "IDSPScraper",           1,  1),
    ("MoHFW",           "scrapers.mohfw_scraper",      "MoHFWScraper",          1,  1),
    ("NCDC",            "scrapers.ncdc_scraper",       "NCDCScraper",           1,  1),
    ("WHO_Outbreaks",   "api_loaders",                 "WHOOutbreaksLoader",    1,  1),
    ("WHO_GHO_API",     "api_loaders",                 "WHOGHOLoader",          7,  1),
    ("MedlinePlus_API", "api_loaders",                 "MedlinePlusLoader",    30,  1),

    # Priority 2: Medicine Data & Other Core Data
    ("NIH_ICD",         "api_loaders",                 "NIHICDLoader",         30,  2),
    ("CDC_API",         "api_loaders",                 "CDCAPILoader",          7,  2),
    ("PIB",             "scrapers.pib_scraper",        "PIBScraper",            1,  2),
    
    # Priority 3: Medicine Data (weekly)
    ("OpenFDA",      "scrapers.openfda_scraper",     "OpenFDAScraper",        7,  3),
    ("RxNav",        "scrapers.rxnav_scraper",       "RxNavScraper",          7,  3),
    ("Drugs.com",    "scrapers.drugs_scraper",       "DrugsScraper",          7,  3),

    # Priority 4: Guidelines (monthly with change detection)
    ("NHS",          "scrapers.nhs_scraper",         "NHSScraper",           30,  5),
    ("Mayo Clinic",  "scrapers.mayo_scraper",        "MayoClinicScraper",    30,  5),
    ("MedlinePlus",  "scrapers.medline_scraper",     "MedlineScraper",       30,  5),
    ("Cleveland",    "scrapers.cleveland_scraper",   "ClevelandClinicScraper",30,  5),

    # Priority 5: News & Education (daily/weekly)
    ("WHO-SEARO",    "scrapers.who_searo_scraper",   "WHOSEAROScraper",       7,  3),
]


def _import_scraper(module_path, class_name):
    """Dynamically import a scraper class."""
    import importlib
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.warning("Could not import %s.%s: %s", module_path, class_name, e)
        return None


def _is_due(db, source_name, frequency_days, force=False):
    """Check if a scraper is due to run based on its last successful run."""
    if force:
        return True

    try:
        result = db.execute_query(
            """
            SELECT completed_at FROM scraper_logs
            WHERE source_name = %s AND status = 'success'
            ORDER BY completed_at DESC LIMIT 1
            """,
            (source_name,),
            fetch=True,
        )
        if result and result[0]:
            last_run = result[0]
            if isinstance(last_run, str):
                last_run = datetime.fromisoformat(last_run)
            if isinstance(last_run, datetime):
                next_due = last_run + timedelta(days=frequency_days)
                if datetime.now() < next_due:
                    return False
    except Exception:
        pass  # If check fails, run to be safe
    return True


def run_scraper_safe(entry, force=False):
    """Run a single scraper with error handling."""
    name, module_path, class_name, freq, priority = entry
    db = DatabaseManager()

    if not _is_due(db, name, freq, force):
        logger.info("⏭  %s — not due yet (every %dd)", name, freq)
        return

    ScraperClass = _import_scraper(module_path, class_name)
    if not ScraperClass:
        return

    logger.info("▶  Starting %s scraper...", name)
    start = time.time()

    try:
        scraper = ScraperClass()
        scraper.run()
        elapsed = time.time() - start
        logger.info("✅ %s completed in %.1fs", name, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        logger.error("❌ %s failed after %.1fs: %s", name, elapsed, e)


def run_all(force=False, frequency_filter=None, max_workers=None):
    """
    Run all registered scrapers in priority order.
    
    Args:
        force: Ignore schedule and run all
        frequency_filter: Only run scrapers with this frequency (1=daily, 7=weekly, 30=monthly)
        max_workers: Override thread count
    """
    workers = max_workers or min(MAX_THREADS, 4)

    # Filter by frequency if specified
    scrapers = SCRAPER_REGISTRY
    if frequency_filter is not None:
        scrapers = [s for s in scrapers if s[3] <= frequency_filter]

    # Sort by priority
    scrapers = sorted(scrapers, key=lambda x: x[4])

    logger.info("=" * 60)
    logger.info("DEB's Health Navigator — Scraper Run")
    logger.info("Scrapers: %d | Workers: %d | Force: %s",
                len(scrapers), workers, force)
    logger.info("=" * 60)

    # Run priority 1 scrapers first (sequentially for data integrity)
    priority_1 = [s for s in scrapers if s[4] == 1]
    for entry in priority_1:
        run_scraper_safe(entry, force)

    # Run everything else in parallel by priority group
    remaining = [s for s in scrapers if s[4] > 1]
    priority_groups = {}
    for s in remaining:
        priority_groups.setdefault(s[4], []).append(s)

    for priority in sorted(priority_groups.keys()):
        group = priority_groups[priority]
        logger.info("── Running priority %d scrapers (%d) ──", priority, len(group))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(run_scraper_safe, entry, force) for entry in group]
            for f in futures:
                try:
                    f.result(timeout=600)  # 10-minute timeout per scraper
                except Exception as e:
                    logger.error("Scraper thread error: %s", e)

    logger.info("=" * 60)
    logger.info("All scraper runs complete.")
    logger.info("=" * 60)


def run_schema_migration():
    """Run database schema migration before scraping."""
    logger.info("Running schema migration...")
    try:
        DatabaseManager.run_schema_migration()
    except Exception as e:
        logger.error("Schema migration failed: %s", e)


def run_audit():
    """Run the data quality audit."""
    logger.info("Running data quality audit...")
    try:
        from audit_db import run_audit as _audit
        report = _audit()
        logger.info("Audit complete: %d issues found", report.get("total_issues", 0))
    except Exception as e:
        logger.error("Audit failed: %s", e)


def main():
    parser = argparse.ArgumentParser(description="DEB's Health Navigator Scraper")
    parser.add_argument("--force", action="store_true", help="Force all scrapers regardless of schedule")
    parser.add_argument("--daily", action="store_true", help="Run only daily scrapers")
    parser.add_argument("--weekly", action="store_true", help="Run only daily + weekly scrapers")
    parser.add_argument("--audit", action="store_true", help="Run only the data quality audit")
    parser.add_argument("--migrate", action="store_true", help="Run only schema migration")
    parser.add_argument("--workers", type=int, default=None, help="Override thread count")
    args = parser.parse_args()

    # Always run migration first
    run_schema_migration()

    if args.audit:
        run_audit()
        return

    if args.migrate:
        return

    freq_filter = None
    if args.daily:
        freq_filter = 1
    elif args.weekly:
        freq_filter = 7

    run_all(force=args.force, frequency_filter=freq_filter, max_workers=args.workers)

    # Run audit after scraping
    run_audit()


if __name__ == "__main__":
    main()
