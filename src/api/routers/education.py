from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

# Add parent directory to path to import scraper.db and rag_logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scraper.db import DatabaseManager
from api.rag_logic import llm 
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

router = APIRouter()

class GenerateSummaryRequest(BaseModel):
    resourceId: Optional[str] = None
    content: Optional[str] = None # Fallback if ID not found or custom content
    language: Optional[str] = "English"
    type: str # video, blog, scheme

@router.get("/education")
async def get_resources(type: Optional[str] = None):
    try:
        db = DatabaseManager()
        resources = db.get_education_resources(filter_type=type)
        return resources
    except Exception as e:
        print(f"Error fetching resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/education/generate")
async def generate_summary(request: GenerateSummaryRequest):
    try:
        # If resource ID is provided, try to fetch content from DB (if we stored it)
        # For now, we'll assume the client might send content or we generate a generic summary based on metadata
        
        # PROMPT engineering for summary
        SUMMARY_PROMPT = """
        You are an expert health educator.
        Generate a concise, easy-to-understand summary for a {type} about health/disease.
        
        Language: {language}
        
        Content/Context:
        {content}
        
        Format:
        - Key Takeaways (bullet points)
        - Actionable Advice
        - Disclaimer: "Consult a doctor for professional advice."
        """
        
        db = DatabaseManager()
        content_to_summarize = request.content
        
        if request.resourceId and not content_to_summarize:
             # Try to fetch from DB if we had content stored, for now mock or fetch basic info
             # in a real scenario, we'd fetch the full text content of the blog/scheme
             pass

        if not content_to_summarize:
            content_to_summarize = "General health information based on available metadata."

        prompt = ChatPromptTemplate.from_template(SUMMARY_PROMPT)
        chain = prompt | llm | StrOutputParser()
        
        summary = chain.invoke({
            "type": request.type,
            "language": request.language,
            "content": content_to_summarize
        })
        
        return {"summary": summary}

    except Exception as e:
        print(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ReportRequest(BaseModel):
    topic: str
    rtype: str
    details: str
    contact: Optional[str] = None
    consent: bool

@router.post("/education/report_missing")
async def report_missing(request: ReportRequest):
    try:
        db = DatabaseManager()
        # Use log_knowledge_gap from db.py
        db.log_knowledge_gap(
            gap_type=f"missing_resource_{request.rtype}",
            query_text=request.topic,
            related_disease=request.topic, # Heuristic
            location=None,
            occurrence_count=1
        )
        return {"status": "success", "message": "Report submitted successfully"}
    except Exception as e:
        print(f"Error reporting missing resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))
