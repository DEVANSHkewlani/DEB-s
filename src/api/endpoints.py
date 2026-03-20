from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from api.rag_logic import perform_rag_query

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "new"
    region: Optional[str] = None
    language: Optional[str] = "English"

class ChatResponse(BaseModel):
    response: str
    sources: List[dict]
    intent: dict
    parsed_query: Optional[dict] = None
    is_knowledge_gap: bool = False

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Unified RAG endpoint for health queries.
    Detects intent, retrieves relevant data, and generates a context-aware response.
    """
    try:
        result = await perform_rag_query(
            query=request.message,
            session_id=request.session_id,
            region_hint=request.region,
            language=request.language
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Streaming RAG endpoint.
    Returns: Text stream of JSON events.
    """
    from fastapi.responses import StreamingResponse
    from api.rag_logic import stream_rag_query
    
    return StreamingResponse(
        stream_rag_query(
            query=request.message,
            session_id=request.session_id,
            region_hint=request.region,
            language=request.language
        ),
        media_type="text/event-stream"
    )

@router.get("/chat/sessions")
async def get_sessions(limit: int = 5):
    """Get recent chat sessions"""
    from scraper.db import DatabaseManager
    db = DatabaseManager()
    sessions = db.get_chat_sessions(limit)
    return {"sessions": sessions}

@router.get("/chat/sessions/{session_id}")
async def get_session_history(session_id: str):
    """Get message history for a specific session"""
    from scraper.db import DatabaseManager
    db = DatabaseManager()
    messages = db.get_chat_messages(session_id)
    return {"messages": messages}

@router.patch("/chat/sessions/{session_id}")
async def update_session(session_id: str, request: dict):
    """Update session title"""
    title = request.get("title")
    if title:
        from scraper.db import DatabaseManager
        db = DatabaseManager()
        db.update_session_title(session_id, title)
        return {"status": "success", "title": title}
    raise HTTPException(status_code=400, detail="Title required")

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "DEB's Health Assistant"}
