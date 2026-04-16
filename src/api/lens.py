import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
from groq import Groq

from scraper.config import (
    OPENFDA_BASE_URL,
    LENS_CHAT_MODEL,
    GROQ_API_KEY,
)
from scraper.db import DatabaseManager

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Dependencies ---
def get_db():
    db = DatabaseManager()
    yield db


# --- Models ---
class ChatRequest(BaseModel):
    message: str
    medicine_name: str
    medicine_context: Dict[str, Any]

class ChatResponse(BaseModel):
    reply: str


# --- Endpoints ---
@router.get("/lookup")
async def lookup_medicine(name: str, db: DatabaseManager = Depends(get_db)):
    """
    3-Tier Lookup Strategy:
    1. Local DB (via `medicine_names`)
    2. OpenFDA API
    3. AI Generation (Groq / Llama3)
    """
    name_lower = name.strip().lower()

    # TIER 1: Local Database — check medicine_names joined with medicines for stored data
    try:
        db_result = db.execute_query(
            """
            SELECT mn.id, mn.name, m.brand_name, m.manufacturer, m.dosage_form, m.strength, m.schedule
            FROM medicine_names mn
            LEFT JOIN medicines m ON m.generic_id = mn.id
            WHERE LOWER(mn.name) = %s OR LOWER(m.brand_name) = %s
            LIMIT 1
            """,
            (name_lower, name_lower),
            fetch=True
        )
        if db_result and db_result[4] and db_result[5]:  # has dosage_form and strength
            generic_id, generic_name, brand_name, manufacturer, dosage_form, strength, schedule = db_result
            logger.info(f"[TIER 1 HIT] Found '{name}' in local DB")
            return {
                "name": brand_name or generic_name,
                "generic_name": generic_name,
                "drug_class": None,
                "manufacturer": manufacturer,
                "schedule": schedule or "Rx",
                "available_forms": [dosage_form] if dosage_form else [],
                "uses": [],
                "mechanism": None,
                "contraindications": None,
                "dosage": {},
                "side_effects_common": [],
                "interactions": [],
                "storage": None,
                "source": "local",
                "confidence": "medium"
            }
    except Exception as e:
        logger.warning(f"DB lookup failed for {name}: {e}")

    # TIER 2: OpenFDA API
    try:
        async with httpx.AsyncClient() as client:
            fda_url = f"{OPENFDA_BASE_URL}?search=openfda.brand_name:\"{name_lower}\"+openfda.generic_name:\"{name_lower}\"&limit=1"
            res = await client.get(fda_url, timeout=5.0)
            
            if res.status_code == 200:
                fda_data = res.json()
                if fda_data.get("results") and len(fda_data["results"]) > 0:
                    result = fda_data["results"][0]
                    openfda_meta = result.get("openfda", {})
                    
                    generic_name = openfda_meta.get("generic_name", [None])[0]
                    brand_name = openfda_meta.get("brand_name", [name])[0]
                    manufacturer = openfda_meta.get("manufacturer_name", [None])[0]
                    route = openfda_meta.get("route", [])
                    pharm_class = openfda_meta.get("pharm_class_epc", [None])[0]
                    
                    data_mapped = {
                        "name": brand_name,
                        "generic_name": generic_name,
                        "drug_class": pharm_class,
                        "manufacturer": manufacturer,
                        "schedule": "Rx", # FDA defaults often to Rx unless OTC explicitly mentioned
                        "available_forms": route,
                        "uses": result.get("indications_and_usage", []),
                        "mechanism": result.get("clinical_pharmacology", [""])[0],
                        "contraindications": result.get("contraindications", [""])[0],
                        "dosage": {
                            "adult": result.get("dosage_and_administration", [""])[0],
                        },
                        "side_effects_common": result.get("adverse_reactions", [""])[0].split('.')[0:3], # rough extraction
                        "interactions": [], 
                        "storage": result.get("storage_and_handling", [""])[0],
                        "source": "openfda"
                    }
                    
                    # Store in DB asynchronously (fire-and-forget or handled later)
                    # For simplicity in this endpoint we're just returning it,
                    # robust implementation would write `data_mapped` to `medicines` table.
                    
                    return data_mapped
    except Exception as e:
        logger.warning(f"OpenFDA lookup failed for {name}: {e}")

    # Log knowledge gap if both DB and OpenFDA missed
    try:
        db.execute_query(
            "INSERT INTO knowledge_gaps (gap_type, query_text, related_disease, created_at) VALUES (%s, %s, %s, NOW())",
            ("medicine_not_found", name, name)
        )
    except Exception as e:
        logger.warning(f"Failed to log medicine_not_found gap for {name}: {e}")

    # TIER 3: AI Generation (Groq API Fallback)
    if not GROQ_API_KEY:
        raise HTTPException(status_code=404, detail="Medicine not found and AI fallback disabled.")

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = f"""
        Provide detailed pharmacological information for the medicine/drug named '{name}'.
        Respond strictly in JSON format matching this structure perfectly. Use 'N/A' or empty arrays if data is unavailable.
        {{
          "name": "<Brand name or input>",
          "generic_name": "<Generic formula>",
          "drug_class": "<Class (e.g. Analgesic)>",
          "manufacturer": "<Notable manufacturer>",
          "schedule": "<OTC / Rx / H / X>",
          "pregnancy_category": "<A/B/C/D/X>",
          "controlled": false,
          "approval_status": "active",
          "available_forms": ["<Form 1>"],
          "indian_brand_names": ["<Alt Brand>"],
          "alternatives": ["<Alt Generic>"],
          "uses": ["<Use 1>"],
          "mechanism": "<Short description>",
          "contraindications": "<When not to use>",
          "disease_interactions": ["<Disease>"],
          "dosage": {{ "adult": "", "children": "", "elderly": "", "renal": "", "hepatic": "" }},
          "dosage_max_daily": "",
          "dosage_notes": [""],
          "side_effects_common": [""],
          "side_effects_uncommon": [""],
          "side_effects_rare": [""],
          "se_emergency": [""],
          "se_driving": "",
          "se_long_term": "",
          "interactions": [ {{ "drug": "", "severity": "high|moderate|low", "effect": "", "action": "" }} ],
          "food_interactions": [ {{ "item": "", "effect": "", "action": "" }} ],
          "lab_interactions": [""],
          "storage": "",
          "shelf_life": "",
          "source": "rag",
          "confidence": "low"
        }}
        """

        completion = client.chat.completions.create(
            model=LENS_CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a pharmaceutical database answering in strict JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        if completion.choices[0].message.content:
            data_ai = json.loads(completion.choices[0].message.content)
            data_ai["source"] = "rag"
            data_ai["confidence"] = "low"
            return data_ai
        # To avoid lookup loops later, we could cache this to DB, 
        # but for safety AI-driven responses might skip DB cache or use a low TTL.

    except Exception as e:
        logger.error(f"Groq AI Lookup Error: {e}")
        raise HTTPException(status_code=503, detail="Medicine lookup failed (AI Service Unavailable).")


@router.post("/chat", response_model=ChatResponse)
async def medicine_chat(req: ChatRequest):
    """
    Contextual chat about a specific medicine, using the looked-up data as RAG context.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not configured")

    try:
        client = Groq(api_key=GROQ_API_KEY)

        # Build context from the medicine dictionary
        ctx_str = json.dumps(req.medicine_context, indent=2)

        sys_prompt = (
            f"You are a helpful, professional AI pharmacist assistant embedded in the 'Medicine Lens' feature. "
            f"A user has scanned the medicine '{req.medicine_name}'. "
            f"Here is the database profile for this medicine:\n{ctx_str}\n\n"
            f"Answer the user's questions concerning this medicine accurately based on the context. "
            f"If the context doesn't have the answer, state that, but you can rely on your general training "
            f"if it's a common pharmaceutical fact. Always advise consulting a doctor for critical decisions. "
            f"Keep your answers brief and readable. Use markdown padding for readability. Do NOT write full essays."
        )

        completion = client.chat.completions.create(
            model=LENS_CHAT_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": req.message}
            ],
            temperature=0.3,
            max_tokens=500
        )

        reply = completion.choices[0].message.content
        return ChatResponse(reply=reply)

    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate chat reply")
