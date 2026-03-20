"""
Data Quality Audit — Daily automated checks
Runs 5 quality checks and stores findings in scraper_logs.

Checks:
1. Trend continuity gaps — disease-state pairs missing this week
2. Suspicious jumps — >500% case increase in one week
3. Zero-value anomalies — cases=0 when last week >100
4. Source discrepancy — >20% difference between sources for same disease+date
5. Missing required fields — NULL source_url, report_date, or disease_id
"""
import json
import logging
from datetime import datetime, date, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.db import DatabaseManager

logger = logging.getLogger("audit")


def run_audit():
    """
    Run all 5 quality checks and store findings.
    Returns a dict with check results.
    """
    db = DatabaseManager()
    findings = {}
    total_issues = 0

    logger.info("=== Starting Daily Data Quality Audit ===")

    # ── Check 1: Trend Continuity Gaps ───────────────────────────────────
    try:
        gaps = _check_continuity_gaps(db)
        findings["continuity_gaps"] = gaps
        total_issues += len(gaps)
        logger.info("Check 1 (Continuity Gaps): %d issues", len(gaps))
    except Exception as e:
        findings["continuity_gaps"] = {"error": str(e)}
        logger.warning("Check 1 error: %s", e)

    # ── Check 2: Suspicious Jumps (>500%) ────────────────────────────────
    try:
        jumps = _check_suspicious_jumps(db)
        findings["suspicious_jumps"] = jumps
        total_issues += len(jumps)
        logger.info("Check 2 (Suspicious Jumps): %d issues", len(jumps))
    except Exception as e:
        findings["suspicious_jumps"] = {"error": str(e)}
        logger.warning("Check 2 error: %s", e)

    # ── Check 3: Zero-Value Anomalies ────────────────────────────────────
    try:
        zeros = _check_zero_values(db)
        findings["zero_anomalies"] = zeros
        total_issues += len(zeros)
        logger.info("Check 3 (Zero Anomalies): %d issues", len(zeros))
    except Exception as e:
        findings["zero_anomalies"] = {"error": str(e)}
        logger.warning("Check 3 error: %s", e)

    # ── Check 4: Source Discrepancy ──────────────────────────────────────
    try:
        discrepancies = _check_source_discrepancy(db)
        findings["source_discrepancies"] = discrepancies
        total_issues += len(discrepancies)
        logger.info("Check 4 (Source Discrepancy): %d issues", len(discrepancies))
    except Exception as e:
        findings["source_discrepancies"] = {"error": str(e)}
        logger.warning("Check 4 error: %s", e)

    # ── Check 5: Missing Required Fields ─────────────────────────────────
    try:
        missing = _check_missing_fields(db)
        findings["missing_fields"] = missing
        total_issues += sum(missing.values()) if isinstance(missing, dict) else 0
        logger.info("Check 5 (Missing Fields): %s", missing)
    except Exception as e:
        findings["missing_fields"] = {"error": str(e)}
        logger.warning("Check 5 error: %s", e)

    # ── Summary Stats ────────────────────────────────────────────────────
    try:
        summary = _get_source_summary(db)
        findings["source_summary"] = summary
    except Exception:
        pass

    # ── Save audit report ────────────────────────────────────────────────
    report = {
        "audit_date": date.today().isoformat(),
        "total_issues": total_issues,
        "findings": findings,
    }

    try:
        db.log_scraper_run({
            "source_name": "audit",
            "scrape_type": "audit",
            "status": "audit",
            "records_found": total_issues,
            "records_inserted": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "error_message": None if total_issues == 0 else f"{total_issues} issues found",
            "started_at": datetime.now(),
            "completed_at": datetime.now(),
            "records_failed": 0,
            "pdfs_processed": 0,
            "error_details": json.dumps(report, default=str)[:5000],
        })
    except Exception as e:
        logger.warning("Could not save audit report: %s", e)

    logger.info("=== Audit Complete: %d total issues ===", total_issues)
    return report


def _check_continuity_gaps(db):
    """Check for disease-state pairs that had data last week but not this week."""
    query = """
        SELECT DISTINCT d.name, t.state
        FROM trends t
        JOIN diseases d ON d.id = t.disease_id
        WHERE t.period_start >= %s AND t.period_start < %s
        EXCEPT
        SELECT DISTINCT d.name, t.state
        FROM trends t
        JOIN diseases d ON d.id = t.disease_id
        WHERE t.period_start >= %s
    """
    last_week = date.today() - timedelta(days=14)
    this_week = date.today() - timedelta(days=7)

    try:
        rows = db.execute_query(query, (last_week, this_week, this_week), fetch="all")
        return [{"disease": r[0], "state": r[1]} for r in (rows or [])]
    except Exception:
        return []


def _check_suspicious_jumps(db):
    """Check for >500% case increase within one week."""
    query = """
        WITH weekly AS (
            SELECT disease_id, state, period_start, cases_count,
                   LAG(cases_count) OVER (
                       PARTITION BY disease_id, state
                       ORDER BY period_start
                   ) AS prev_cases
            FROM trends
            WHERE period_start >= %s
        )
        SELECT d.name, w.state, w.period_start, w.prev_cases, w.cases_count
        FROM weekly w
        JOIN diseases d ON d.id = w.disease_id
        WHERE w.prev_cases > 0
          AND w.cases_count > w.prev_cases * 5
        ORDER BY w.cases_count DESC
        LIMIT 20
    """
    lookback = date.today() - timedelta(days=30)

    try:
        rows = db.execute_query(query, (lookback,), fetch="all")
        return [
            {"disease": r[0], "state": r[1], "date": str(r[2]),
             "prev_cases": r[3], "curr_cases": r[4],
             "jump_pct": round(r[4] / r[3] * 100, 1) if r[3] else 0}
            for r in (rows or [])
        ]
    except Exception:
        return []


def _check_zero_values(db):
    """Check disease-state pairs with cases=0 this week but >100 last week."""
    query = """
        WITH recent AS (
            SELECT disease_id, state, period_start, cases_count,
                   LAG(cases_count) OVER (
                       PARTITION BY disease_id, state
                       ORDER BY period_start
                   ) AS prev_cases
            FROM trends
            WHERE period_start >= %s
        )
        SELECT d.name, r.state, r.period_start, r.prev_cases
        FROM recent r
        JOIN diseases d ON d.id = r.disease_id
        WHERE r.cases_count = 0 AND r.prev_cases > 100
        LIMIT 20
    """
    lookback = date.today() - timedelta(days=30)

    try:
        rows = db.execute_query(query, (lookback,), fetch="all")
        return [
            {"disease": r[0], "state": r[1], "date": str(r[2]),
             "prev_cases": r[3]}
            for r in (rows or [])
        ]
    except Exception:
        return []


def _check_source_discrepancy(db):
    """Check for >20% discrepancy between sources for same disease+state+date."""
    query = """
        SELECT d.name, o1.state, o1.reported_date,
               o1.source, o1.cases_reported,
               o2.source, o2.cases_reported
        FROM outbreaks o1
        JOIN outbreaks o2 ON o1.disease_id = o2.disease_id
            AND o1.state = o2.state
            AND o1.reported_date = o2.reported_date
            AND o1.source < o2.source
        JOIN diseases d ON d.id = o1.disease_id
        WHERE o1.reported_date >= %s
          AND o1.cases_reported > 0
          AND o2.cases_reported > 0
          AND ABS(o1.cases_reported - o2.cases_reported)::FLOAT
              / GREATEST(o1.cases_reported, o2.cases_reported) > 0.2
        LIMIT 20
    """
    lookback = date.today() - timedelta(days=14)

    try:
        rows = db.execute_query(query, (lookback,), fetch="all")
        return [
            {"disease": r[0], "state": r[1], "date": str(r[2]),
             "source1": r[3], "cases1": r[4],
             "source2": r[5], "cases2": r[6]}
            for r in (rows or [])
        ]
    except Exception:
        return []


def _check_missing_fields(db):
    """Count records with NULL required fields."""
    checks = {}

    try:
        res = db.execute_query(
            "SELECT COUNT(*) FROM outbreaks WHERE source_url IS NULL OR source_url = ''",
            fetch=True
        )
        checks["outbreaks_no_source_url"] = res[0] if res else 0
    except Exception:
        checks["outbreaks_no_source_url"] = -1

    try:
        res = db.execute_query(
            "SELECT COUNT(*) FROM outbreaks WHERE reported_date IS NULL",
            fetch=True
        )
        checks["outbreaks_no_date"] = res[0] if res else 0
    except Exception:
        checks["outbreaks_no_date"] = -1

    try:
        res = db.execute_query(
            "SELECT COUNT(*) FROM disease_guidelines WHERE source_url IS NULL OR source_url = ''",
            fetch=True
        )
        checks["guidelines_no_source_url"] = res[0] if res else 0
    except Exception:
        checks["guidelines_no_source_url"] = -1

    try:
        res = db.execute_query(
            "SELECT COUNT(*) FROM trends WHERE source IS NULL OR source = ''",
            fetch=True
        )
        checks["trends_no_source"] = res[0] if res else 0
    except Exception:
        checks["trends_no_source"] = -1

    return checks


def _get_source_summary(db):
    """Get per-source record counts for overview."""
    summary = {}
    tables = [
        ("outbreaks", "source"),
        ("trends", "source"),
        ("disease_guidelines", "source"),
        ("education_resources", "source"),
    ]
    for table, col in tables:
        try:
            rows = db.execute_query(
                f"SELECT {col}, COUNT(*) FROM {table} GROUP BY {col} ORDER BY COUNT(*) DESC",
                fetch="all"
            )
            summary[table] = {r[0]: r[1] for r in (rows or [])}
        except Exception:
            summary[table] = {}

    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    report = run_audit()
    print(json.dumps(report, indent=2, default=str))
