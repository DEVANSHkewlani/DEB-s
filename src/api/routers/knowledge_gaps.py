"""
Knowledge Gaps API Router
Exposes endpoints to list, filter, and manage knowledge gaps for the admin/debug view.
"""
from fastapi import APIRouter, Query
from typing import Optional
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper.db import DatabaseManager

router = APIRouter()


@router.get("")
async def get_knowledge_gaps(
    status: Optional[str] = Query(None, description="Filter by status: open, resolved"),
    gap_type: Optional[str] = Query(None, description="Filter by gap type"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """
    Return a paginated list of knowledge gaps.
    """
    db = DatabaseManager()
    query = """
        SELECT id, gap_type, query_text, related_disease, location,
               latitude, longitude, occurrence_count, status,
               resolved_at, resolution_source, created_at, updated_at
        FROM knowledge_gaps
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND status = %s"
        params.append(status)
    if gap_type:
        query += " AND gap_type = %s"
        params.append(gap_type)

    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = db.execute_query(query, params, fetch="all") or []

    gaps = []
    for r in rows:
        gaps.append({
            "id": r[0],
            "gap_type": r[1],
            "query_text": r[2],
            "related_disease": r[3],
            "location": r[4],
            "latitude": float(r[5]) if r[5] else None,
            "longitude": float(r[6]) if r[6] else None,
            "occurrence_count": r[7],
            "status": r[8],
            "resolved_at": r[9].isoformat() if r[9] else None,
            "resolution_source": r[10],
            "created_at": r[11].isoformat() if r[11] else None,
            "updated_at": r[12].isoformat() if r[12] else None,
        })

    # Total count
    count_q = "SELECT COUNT(*) FROM knowledge_gaps WHERE 1=1"
    count_params = []
    if status:
        count_q += " AND status = %s"
        count_params.append(status)
    if gap_type:
        count_q += " AND gap_type = %s"
        count_params.append(gap_type)
    total_row = db.execute_query(count_q, count_params if count_params else None, fetch=True)
    total = total_row[0] if total_row else 0

    return {"total": total, "items": gaps}


@router.get("/summary")
async def get_knowledge_gaps_summary():
    """
    Returns aggregate counts grouped by gap_type and status.
    """
    db = DatabaseManager()
    rows = db.execute_query(
        "SELECT gap_type, status, COUNT(*) FROM knowledge_gaps GROUP BY gap_type, status ORDER BY COUNT(*) DESC",
        fetch="all"
    ) or []
    return [{"gap_type": r[0], "status": r[1], "count": r[2]} for r in rows]


@router.patch("/{gap_id}/resolve")
async def resolve_knowledge_gap(gap_id: int, source: Optional[str] = None):
    """
    Mark a knowledge gap as resolved.
    """
    db = DatabaseManager()
    db.execute_query(
        """
        UPDATE knowledge_gaps
        SET status = 'resolved', resolved_at = NOW(), resolution_source = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (source or "manual", gap_id)
    )
    return {"status": "resolved", "id": gap_id}
