import os
from dotenv import load_dotenv

load_dotenv()
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import numpy as np
from scraper.db import DatabaseManager
import json
from typing import Optional
from duckduckgo_search import DDGS

class IntentOutput(BaseModel):
    intent_type: str
    disease_name: Optional[str] = None
    region: Optional[str] = None
    is_followup: bool = False


class ParsedQuery(BaseModel):
    """Lightweight query parsing for structured downstream behavior."""
    intent_type: str
    disease_name: Optional[str] = None
    region: Optional[str] = None
    question: str
    is_followup: bool = False

# Configuration
GROQ_MODEL = "llama-3.3-70b-versatile"
EMBEDDING_MODEL_NAME = "l3cube-pune/indic-sentence-bert-nli"
CHROMA_PATH = "./chroma_db"
RRF_K = 60

# Lazy loaders
_embed_model = None
_chroma_client = None
_bm25 = None
_doc_map = None
_llm = None
_intent_llm = None

def get_llm():
    global _llm, _intent_llm
    if _llm is None:
        api_key = os.getenv("GROQ_API_KEY", "dummy_key")
        _llm = ChatGroq(model_name=GROQ_MODEL, temperature=0, groq_api_key=api_key)
        _intent_llm = _llm.with_structured_output(IntentOutput)
    return _llm, _intent_llm

# Chat History Storage (DB-based now)
MAX_HISTORY_LEN = 10


def get_embedding_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embed_model



def get_chroma_collection():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Get or create collection
    return _chroma_client.get_or_create_collection(
        name="health_guidelines",
        metadata={"hnsw:space": "cosine"}
    )
    
def get_bm25_index():
    global _bm25, _doc_map
    if _bm25 is None:
        from rank_bm25 import BM25Okapi
        db = DatabaseManager()
        docs = db.execute_query("SELECT id, title, content FROM unified_search_index", fetch="all")
        if not docs:
            _doc_map = {}
            # Initialize with empty but valid structure to avoid errors
            _bm25 = BM25Okapi([["empty"]])
            _bm25.doc_ids = ["0"]
            return _bm25, _doc_map
            
        _doc_map = {str(d[0]): {"title": d[1], "content": d[2]} for d in docs}
        tokenized_corpus = [f"{str(d[1])} {str(d[2])}".lower().split() for d in docs if d[1] and d[2]]
        if not tokenized_corpus:
            tokenized_corpus = [["empty"]]
            _bm25 = BM25Okapi(tokenized_corpus)
            _bm25.doc_ids = ["0"]
        else:
            _bm25 = BM25Okapi(tokenized_corpus)
            _bm25.doc_ids = [str(d[0]) for d in docs if d[1] and d[2]]
    return _bm25, _doc_map



SYSTEM_PROMPT = """
You are DEB's Health Assistant, a professional yet approachable AI dedicated to health information.
Your goal is to be helpful, answering specific health questions based on the retrieved context provided, while also being conversational when appropriate.

INSTRUCTIONS:
1.  **Context Priority**:
    - The `Context` section below contains **Retrieved Documents** (medical facts) and **Previous Chat History**.
    - **ALWAYS** check the **Retrieved Documents** first. If they contain the answer to the user's latest question, integrate that information naturally.

2.  **Conversational & Personalized**:
    - **Address the user directly** (e.g., "You may want to...", "If you are feeling...").
    - **Avoid repetitive citations**. Do NOT start sentences with "According to [Source]...", "The retrieved documents say...", or "Based on the text...".
    - Instead, synthesize the information into a coherent, direct answer. (e.g., instead of "According to CDC, wash hands", say "You should wash your hands frequently").
    - If the user asks a question, answer it directly.

3.  **Medical Queries**:
    - Answer based strictly on the provided Context if available.
    - If the context is empty but the question is general knowledge *and* related to health, answer using your internal knowledge with a safety disclaimer.

4.  **Safety**:
    - NEVER diagnose or prescribe.
    - If asked for medical advice ("Should I take this?"), say: "I cannot provide medical advice. Please consult a doctor."

5.  **Output Style**:
    - **No Links Default**: **NEVER output URLs or links** in your text response unless the user EXPLICITLY asks for them (e.g., "Give me the link").
    - **If Asked**: If the user asks for links, you MAY provide the URLs found in the `Context`.
    - **Tone**: Empathetic, clear, and reassuring.
    - **Structured Output Required**: Respond using these sections (even if some are brief):
        1) Summary
        2) Key points
        3) What you can do now
        4) When to seek urgent care
        5) Sources used (names only, no URLs unless user asked)

TONE: Professional, empathetic, concise, and safe.
LANGUAGE: Respond in {language}.

CONTEXT:
{context}

Question: {question}
"""
INTENT_PROMPT = """
You are an intent classification system.

Classify the user query and extract:

- intent_type (Medical_Query, Chitchat, Clarification, Outbreak_News)
- disease_name (if mentioned)
- region (if mentioned)
- is_followup (true if follow-up question)

If disease is unclear, choose the most likely single disease.
Do not return multiple options.




Query: {query}
History: {history}
"""

def reciprocal_rank_fusion(keyword_results: List[str], vector_results: List[str], k: int = RRF_K) -> Dict[str, float]:
    scores = {}
    for rank, doc_id in enumerate(keyword_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc_id in enumerate(vector_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return scores

async def get_rag_context(query: str, session_id: str, region_hint: str = None) -> Dict[str, Any]:
    """Shared logic for retrieval and context construction"""
    db = DatabaseManager()
    db_history = db.get_chat_messages(session_id) if session_id and session_id != "new" else []
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in db_history[-3:]])

    # 1. Intent Analysis

    try:
        _, intent_llm_model = get_llm()
        intent = await intent_llm_model.ainvoke(
            INTENT_PROMPT + f"\n\nQuery: {query}\nHistory: {history_str}"
        )
    except Exception as e:
        print("Intent detection failed:", e)
        intent = IntentOutput(
            intent_type="Medical_Query",
            disease_name=None,
            region=None,
            is_followup=False
        )

    intent_type = intent.intent_type
    disease_name = intent.disease_name
    parsed = ParsedQuery(
        intent_type=intent_type,
        disease_name=disease_name,
        region=intent.region or region_hint,
        question=query,
        is_followup=bool(intent.is_followup),
    ).model_dump()

    
    # Handle Chitchat immediately
    if intent_type == "Chitchat":
        return {
            "context_docs": [],
            "sources": [],
            "intent": intent,
            "disease_name": None,
            "skip_rag": True,
            "parsed_query": parsed,
            "is_knowledge_gap": False,
        }

    # Handle Clarification / Follow-up (Rewrite Query)
    working_query = query
    if intent_type == "Clarification" or intent.is_followup:
        # Simple rewrite logic: combine last bot response with current query if needed
        # For now, relying on intent extraction of 'disease_name' from history is usually enough.
        # But we can make the search query more specific if disease_name was found.
        if disease_name:
             working_query = f"{disease_name} {query}"

    context_docs = []
    sources = []
    
    # 2. Retrieval
    coll = get_chroma_collection()
    embed_model = get_embedding_model()
    # Use working_query for search
    query_vec = embed_model.encode(working_query).tolist()

    v_ids = []
    try:
        v_results = coll.query(query_embeddings=[query_vec], n_results=50)
        if isinstance(v_results, dict) and isinstance(v_results.get("ids"), list) and v_results["ids"]:
            v_ids = v_results["ids"][0] or []
    except Exception:
        v_ids = []
    
    bm25, doc_map = get_bm25_index()
    # Use working_query for search
    tokenized_query = working_query.lower().split()
    kw_scores = bm25.get_scores(tokenized_query)
    top_n = np.argsort(kw_scores)[::-1][:50]
    kw_ids = [bm25.doc_ids[i] for i in top_n]
    
    rrf_scores = reciprocal_rank_fusion(kw_ids, v_ids)
    sorted_rrf_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:5] # Just take top 5
    
    db = DatabaseManager()
    if sorted_rrf_ids:
        placeholders = ",".join(["%s"] * len(sorted_rrf_ids))
        docs_query = f"SELECT id, title, content, source, source_url FROM unified_search_index WHERE id IN ({placeholders})"
        db_docs = db.execute_query(docs_query, [str(i) for i in sorted_rrf_ids], fetch="all")
        
        if db_docs:
            doc_lookup = {str(d[0]): {"title": d[1], "content": d[2], "source": d[3], "url": d[4]} for d in db_docs}
        else:
            doc_lookup = {}
        
        for doc_id in sorted_rrf_ids:
            if doc_id in doc_lookup:
                doc = doc_lookup[doc_id]
                title = doc.get("title") or "Untitled"
                source = doc.get("source") or "Unknown"
                content = (doc.get("content") or "")
                url = doc.get("url")
                context_docs.append(f"Source: {source} ({title})\n{content[:800]}")
                sources.append({"title": title, "source": source, "url": url})

    is_gap = False
    if not context_docs and intent_type in ["Medical_Query", "Outbreak_News", "Clarification"]:
        is_gap = True
    elif disease_name and context_docs:
        # Check if disease_name (or any part of it) appears in context
        disease_found_in_docs = any(disease_name.lower() in doc.lower() for doc in context_docs)
        if not disease_found_in_docs and intent_type in ["Medical_Query", "Outbreak_News"]:
            is_gap = True

    # TIER 2: Live fallback only when local retrieval is insufficient.
    used_fallback = False
    fallback_added_context = False
    if is_gap:
        print(f"[FALLBACK] No sufficient local context for '{working_query}'. Searching web...")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(working_query, max_results=3))
                used_fallback = True
                if results:
                    web_context = "\n".join([f"Web Snippet: {r.get('title','')}\n{r.get('body','')}" for r in results])
                    context_docs.append(f"REAL-TIME SEARCH SNIPPETS:\n{web_context}")
                    fallback_added_context = True
                    print(f"[FALLBACK] Found {len(results)} web results for {working_query}.")
        except Exception as e:
            used_fallback = True
            print(f"Fallback search failed: {e}")

    # Decide if we truly have enough context to answer.
    # Rule:
    # - If a disease was extracted, we require that term to appear in the retrieved context (DB or fallback snippets).
    # - Otherwise, we require that fallback added some context when local retrieval was insufficient.
    combined_text = " ".join([str(x) for x in context_docs]).lower()
    disease_term = (str(disease_name).strip().lower() if disease_name else "")
    disease_term_present = bool(disease_term and disease_term in combined_text)

    is_knowledge_gap = False
    if is_gap:
        if disease_term:
            # Even if fallback returned snippets, if they don't mention the disease, treat as a gap.
            is_knowledge_gap = not disease_term_present
        else:
            is_knowledge_gap = not fallback_added_context

    if is_knowledge_gap:
        try:
            loc = (intent.region or region_hint) or "unknown"
            db.log_knowledge_gap(
                gap_type="chatbot_unanswered",
                query_text=query,
                related_disease=str(disease_name) if disease_name else None,
                location=loc,
            )
            print(f"[KNOWLEDGE GAP] Logged gap for query: {query}")
        except Exception as e:
            print(f"Error logging knowledge gap: {e}")

    # 3. Outbreak Data
    region = intent.region or region_hint
    if region and disease_name:
         outbreaks = db.execute_query(
             "SELECT district, reported_date, cases_reported FROM outbreaks WHERE state ILIKE %s AND disease_id = (SELECT id FROM diseases WHERE name ILIKE %s LIMIT 1) ORDER BY reported_date DESC LIMIT 3",
             (f"%{region}%", f"%{disease_name}%"), fetch="all"
         )
         if outbreaks:
             out_str = "\n".join([f"- {o[1]}: {o[2]} cases in {o[0]}" for o in outbreaks])
             context_docs.append(f"Recent Outbreak Data:\n{out_str}")
             
    return {
        "context_docs": context_docs,
        "sources": sources,
        "intent": intent,
        "disease_name": disease_name,
        "skip_rag": False,
        "parsed_query": parsed,
        "is_knowledge_gap": is_knowledge_gap
    }

async def perform_rag_query(query: str, session_id: str, region_hint: str = None, language: str = "English") -> Dict[str, Any]:
    """Legacy non-streaming endpoint implementation"""
    db = DatabaseManager()
    
    # Initialize session if needed
    import uuid
    def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    if not session_id or session_id == "new" or not is_valid_uuid(session_id):
        session_id = db.create_chat_session("New Chat")
        
    data = await get_rag_context(query, session_id, region_hint)
    context_docs = data["context_docs"]
    sources = data["sources"]
    intent = data["intent"]
    skip_rag = data.get("skip_rag", False)
    parsed_query = data.get("parsed_query")
    is_knowledge_gap = bool(data.get("is_knowledge_gap", False))
    
    final_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
    llm_model, _ = get_llm()
    chain = final_prompt | llm_model | StrOutputParser()
    
    # Prepare history context for the LLM
    db_history = db.get_chat_messages(session_id)
    history_str = "\n".join([f"User: {msg['content']}" if msg['role'] == "user" else f"Assistant: {msg['content']}" 
                             for msg in db_history[-5:]])
    
    combined_context = f"RETRIEVED DOCUMENTS:\n" + "\n---\n".join(context_docs) + f"\n\nPREVIOUS CHAT HISTORY:\n{history_str}"

    if not skip_rag:
         combined_context += "\n\nSYSTEM INSTRUCTION: The user has asked a specific health question. You MUST answer it using the Retrieved Documents above. Do NOT offer generic help, just answer the question."

    if is_knowledge_gap:
        # Hard rule: if DB + live fallback couldn't provide relevant context, don't hallucinate.
        response = (
            "## Summary\n"
            "I don’t know the answer to this yet based on our database and live sources.\n\n"
            "## Key points\n"
            "- I couldn’t find enough reliable context to answer confidently.\n"
            "- I’ve logged this as a knowledge gap so it can be added to the system.\n\n"
            "## What you can do now\n"
            "- Re-check the spelling of the condition/medicine name, or share symptoms + location + timeframe.\n"
            "- If this is urgent or severe, please consult a clinician immediately.\n\n"
            "## When to seek urgent care\n"
            "- Trouble breathing, chest pain, severe allergic reaction, confusion, fainting, seizures, or rapidly worsening symptoms.\n\n"
            "## Sources used\n"
            "- None (insufficient reliable context)"
        )
        sources = []
    else:
        try:
            response = await chain.ainvoke({"context": combined_context, "question": query, "language": language})
        except Exception as e:
            print(f"Error during LLM generation: {e}")
            response = "I am currently experiencing high traffic or an API error. Please try again later. (Error: API Unavailable)"
    
    # Update History in DB
    db.add_chat_message(session_id, "user", query)
    db.add_chat_message(session_id, "assistant", response)

    return {
        "response": response,
        "sources": sources,
        "intent": intent.model_dump(),
        "parsed_query": parsed_query,
        "is_knowledge_gap": is_knowledge_gap
    }

async def stream_rag_query(query: str, session_id: str, region_hint: str = None, language: str = "English"):
    """Streaming endpoint implementation"""
    print(f"DEBUG: stream_rag_query received session_id: {session_id}")
    db = DatabaseManager()
    
    # Session Handling
    import uuid
    def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    if not session_id or session_id == "new" or session_id == "default" or not is_valid_uuid(session_id):
        # Generate initial title (placeholder, will update after intent)
        session_id = db.create_chat_session("New Chat")
        yield json.dumps({"type": "session_init", "session_id": session_id}) + "\n"
        
    # Load History from DB
    db_history = db.get_chat_messages(session_id)
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in db_history[-3:]])
    

    try:
        _, intent_llm_model = get_llm()
        intent = await intent_llm_model.ainvoke(
            INTENT_PROMPT + f"\n\nQuery: {query}\nHistory: {history_str}"
        )
    except Exception as e:
        print("Intent detection failed:", e)
        intent = IntentOutput(
        intent_type="Medical_Query",
        disease_name=None,
        region=None,
        is_followup=False
    )

    
    intent_type = intent.intent_type
    disease_name = intent.disease_name
    
    context_docs = []
    sources = []
    skip_rag = False
    
    if intent_type == "Chitchat":
        skip_rag = True
        yield json.dumps({"type": "status", "content": "Thinking..."}) + "\n"
        
    else:
        yield json.dumps({"type": "status", "content": "Searching medical database..."}) + "\n"
        
        # Retrieval logic 
        working_query = query
        if intent_type == "Clarification" or intent.is_followup:
             if disease_name:
                  working_query = f"{disease_name} {query}"

        coll = get_chroma_collection()
        embed_model = get_embedding_model()
        query_vec = embed_model.encode(working_query).tolist()

        v_ids = []
        try:
            v_results = coll.query(query_embeddings=[query_vec], n_results=50)
            if isinstance(v_results, dict) and isinstance(v_results.get("ids"), list) and v_results["ids"]:
                v_ids = v_results["ids"][0] or []
        except Exception:
            v_ids = []
        
        bm25, doc_map = get_bm25_index()
        tokenized_query = working_query.lower().split()
        kw_scores = bm25.get_scores(tokenized_query)
        top_n = np.argsort(kw_scores)[::-1][:50]
        kw_ids = [bm25.doc_ids[i] for i in top_n]
        
        rrf_scores = reciprocal_rank_fusion(kw_ids, v_ids)
        sorted_rrf_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:5]
        
        db = DatabaseManager()
        if sorted_rrf_ids:
            placeholders = ",".join(["%s"] * len(sorted_rrf_ids))
            docs_query = f"SELECT id, title, content, source, source_url FROM unified_search_index WHERE id IN ({placeholders})"
            db_docs = db.execute_query(docs_query, [str(i) for i in sorted_rrf_ids], fetch="all")
            doc_lookup = {str(d[0]): {"title": d[1], "content": d[2], "source": d[3], "url": d[4]} for d in db_docs}
            
            for doc_id in sorted_rrf_ids:
                if doc_id in doc_lookup:
                    doc = doc_lookup[doc_id]
                    title = doc.get("title") or "Untitled"
                    source = doc.get("source") or "Unknown"
                    content = (doc.get("content") or "")
                    url = doc.get("url")
                    context_docs.append(f"Source: {source} ({title})\nURL: {url}\n{content[:800]}")
                    sources.append({"title": title, "source": source, "url": url})

        # Log knowledge gap if medical query and:
        # 1. No documents found AT ALL
        # 2. Disease mentioned in intent was NOT found in any retrieved docs
        is_gap = False
        if not context_docs and intent_type in ["Medical_Query", "Outbreak_News", "Clarification"]:
            is_gap = True
        elif disease_name and context_docs:
            # Check if disease_name (or any part of it) appears in context
            disease_found_in_docs = any(disease_name.lower() in doc.lower() for doc in context_docs)
            if not disease_found_in_docs and intent_type in ["Medical_Query", "Outbreak_News"]:
                is_gap = True
                
        if is_gap:
            # TIER 4: Real-time API Fallback (DuckDuckGo)
            yield json.dumps({"type": "status", "content": "Searching global medical web..."}) + "\n"
            print(f"[FALLBACK] No local context for '{working_query}'. Searching web...")
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(working_query, max_results=3))
                    if results:
                        web_context = "\n".join([f"Web Source: {r['href']}\n{r['body']}" for r in results])
                        context_docs.append(f"REAL-TIME SEARCH RESULTS:\n{web_context}")
                        print(f"[FALLBACK] Found {len(results)} web results for {working_query}.")
            except Exception as e:
                print(f"Fallback search failed: {e}")

        if is_gap:
            try:
                db.execute_query(
                    "INSERT INTO knowledge_gaps (gap_type, query_text, related_disease, created_at) VALUES (%s, %s, %s, NOW())",
                    ("chatbot_unanswered", query, disease_name)
                )
                print(f"[KNOWLEDGE GAP] Logged gap for query: {query}")
            except Exception as e:
                print(f"Error logging knowledge gap: {e}")

        # Outbreak Data
        region = intent.region or region_hint
        if region and disease_name:
             outbreaks = db.execute_query(
                 "SELECT district, reported_date, cases_reported FROM outbreaks WHERE state ILIKE %s AND disease_id = (SELECT id FROM diseases WHERE name ILIKE %s LIMIT 1) ORDER BY reported_date DESC LIMIT 3",
                 (f"%{region}%", f"%{disease_name}%"), fetch="all"
             )
             if outbreaks:
                 out_str = "\n".join([f"- {o[1]}: {o[2]} cases in {o[0]}" for o in outbreaks])
                 context_docs.append(f"Recent Outbreak Data:\n{out_str}")

    # Generation
    yield json.dumps({"type": "status", "content": "Generating response..."}) + "\n"
    
    final_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
    llm_model, _ = get_llm()
    chain = final_prompt | llm_model | StrOutputParser()
    
    full_history_str = "\n".join([f"User: {msg['content']}" if msg['role'] == "user" else f"Assistant: {msg['content']}" 
                             for msg in db_history[-5:]])
    combined_context = f"RETRIEVED DOCUMENTS:\n" + "\n---\n".join(context_docs) + f"\n\nPREVIOUS CHAT HISTORY:\n{full_history_str}"

    if not skip_rag:
         combined_context += "\n\nSYSTEM INSTRUCTION: The user has asked a specific health question. You MUST answer it using the Retrieved Documents above. Do NOT offer generic help, just answer the question."

    full_response = ""
    try:
        async for chunk in chain.astream({"context": combined_context, "question": query, "language": language}):
            if chunk:
                full_response += chunk
                yield json.dumps({"type": "token", "content": chunk}) + "\n"
    except Exception as e:
        print(f"Error during LLM generation: {e}")
        error_msg = "\nI am currently experiencing high traffic or an API error. Please try again later."
        full_response += error_msg
        yield json.dumps({"type": "token", "content": error_msg}) + "\n"

    # Update History in DB
    db.add_chat_message(session_id, "user", query)
    db.add_chat_message(session_id, "assistant", full_response)
    
    # Context-aware naming for new sessions (if title is still 'New Chat')
    # Or just rename on first message always if it's a new session
    # Let's check if we should rename
    if len(db_history) == 0: # This was the first exchange
        try:
             # Simple title generation
             title_prompt = f"Generate a short (3-5 words) title for this health chat based on the query: '{query}'. Do not use quotes."
             llm_model, _ = get_llm()
             title = await llm_model.ainvoke(title_prompt)
             new_title = title.content.strip().replace('"', '')
             db.update_session_title(session_id, new_title)
             yield json.dumps({"type": "session_rename", "title": new_title}) + "\n"
        except Exception as e:
             print(f"Title generation failed: {e}")

    yield json.dumps({
        "type": "end",
        "sources": sources,
        "intent": intent.model_dump()
    }) + "\n"

    

