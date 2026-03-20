from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sys
import os

# Add parent directory to path to import scraper.db
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper.db import DatabaseManager

router = APIRouter()

class UserReport(BaseModel):
    reportType: str
    location: str
    onsetDate: Optional[str] = None
    severity: Optional[str] = "unknown"
    peopleAffected: Optional[str] = None
    details: str
    name: Optional[str] = None
    contact: Optional[str] = None
    consent: bool = False
    createdAt: Optional[str] = None

@router.post("/reports", status_code=201)
async def create_report(report: UserReport):
    try:
        db = DatabaseManager()
        
        # Map frontend camelCase to DB snake_case
        # Sanitize optional fields that might be empty strings
        people_affected = None
        if report.peopleAffected and str(report.peopleAffected).strip():
            try:
                people_affected = int(report.peopleAffected)
            except (ValueError, TypeError):
                people_affected = None

        onset_date = report.onsetDate if report.onsetDate and report.onsetDate.strip() else None

        db_data = {
            "report_type": report.reportType,
            "location": report.location,
            "onset_date": onset_date,
            "severity": report.severity,
            "people_affected": people_affected,
            "details": report.details,
            "reporter_name": report.name if report.name and report.name.strip() else None,
            "reporter_contact": report.contact if report.contact and report.contact.strip() else None,
            "consent": report.consent
        }
        
        report_id = db.insert_user_report(db_data)
        
        if report_id:
            return {"status": "success", "id": report_id, "message": "Report submitted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to insert report")
            
    except Exception as e:
        print(f"Error submitting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
