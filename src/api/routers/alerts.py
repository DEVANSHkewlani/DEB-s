from fastapi import APIRouter, HTTPException
from typing import List, Optional
import sys
import os

# Add parent directory to path to import scraper.db
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper.db import DatabaseManager
import threading

_refresh_lock = threading.Lock()
_refresh_in_progress = False

router = APIRouter()

@router.get("/outbreaks")
async def get_outbreaks(disease_id: Optional[int] = None):
    try:
        db = DatabaseManager()
        outbreaks = db.get_active_outbreaks(disease_id=disease_id)
        return outbreaks
    except Exception as e:
        print(f"Error fetching outbreaks: {e}")
        return []

@router.get("/trends")
async def get_trends(disease_id: Optional[int] = None):
    try:
        db = DatabaseManager()
        trends = db.get_health_trends(disease_id=disease_id)
        return trends
    except Exception as e:
        print(f"Error fetching trends: {e}")
        return []

@router.get("/bulletins")
async def get_bulletins(disease_id: Optional[int] = None):
    try:
        db = DatabaseManager()
        # Get recent bulletins, optionally filtered by disease, limit to 3 always as per requirement
        return db.get_recent_bulletins(disease_id=disease_id, limit=3)
    except Exception as e:
        print(f"Error fetching bulletins: {e}")
        return []

@router.get("/diseases")
async def get_diseases_with_data():
    """Get list of diseases that have outbreaks or trends data"""
    try:
        db = DatabaseManager()
        diseases = db.get_diseases_with_data()
        return diseases
    except Exception as e:
        print(f"Error fetching diseases: {e}")
        return []


@router.post("/refresh")
async def refresh_alerts_data(mode: str = "who"):
    """
    Trigger a background refresh from live sources (scrapers/API loaders).

    This endpoint is intentionally fire-and-forget so the UI can stay responsive:
    - Frontend calls this periodically
    - Frontend then re-fetches /outbreaks and /trends from DB
    """
    global _refresh_in_progress
    if _refresh_in_progress:
        return {"status": "already_running"}

    def _job():
        global _refresh_in_progress
        with _refresh_lock:
            _refresh_in_progress = True
            try:
                # Local import to avoid import cost on every request
                try:
                    from scraper.api_loaders import APIDataLoader
                except Exception:
                    from api_loaders import APIDataLoader
                APIDataLoader().run(mode=mode)
            except Exception as e:
                print(f"[ALERTS REFRESH] Failed: {e}")
            finally:
                _refresh_in_progress = False

    threading.Thread(target=_job, daemon=True).start()
    return {"status": "started", "mode": mode}
