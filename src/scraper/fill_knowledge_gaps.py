import os
from dotenv import load_dotenv

load_dotenv()
from db import DatabaseManager
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
You are a medical AI assistant.
Your task is to generate a concise, highly accurate "General Health Overview" and "First Aid" guide for the disease or health topic provided.
DO NOT provide conversational filler. Format your response strictly in Markdown.

Disease/Topic: {topic}
Original Query Context (if any): {query}

Use professional medical knowledge to describe:
1. What the disease/condition is.
2. Common symptoms.
3. First aid, prevention, and basic guidelines.
"""

def fill_knowledge_gaps():
    db = DatabaseManager()
    
    print("Checking for open knowledge gaps...")
    gaps = db.execute_query(
        "SELECT id, gap_type, query_text, related_disease FROM knowledge_gaps WHERE status = 'open'",
        fetch="all"
    )
    
    if not gaps:
        print("No open knowledge gaps found: all clear!")
        return
        
    print(f"Found {len(gaps)} open knowledge gap(s). Processing...")
    
    llm = ChatGroq(model_name=GROQ_MODEL, temperature=0, groq_api_key=os.getenv("GROQ_API_KEY"))
    prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
    chain = prompt | llm | StrOutputParser()
    
    for gap in gaps:
        gap_id, gap_type, query_text, related_disease = gap
        
        topic = related_disease if related_disease else query_text
        if not topic:
            # Cannot process without topic
            db.execute_query("UPDATE knowledge_gaps SET status = 'ignored' WHERE id = %s", (gap_id,))
            continue
            
        print(f"Generating content for gap ID {gap_id} (Topic: {topic})...")
        
        try:
            content = chain.invoke({"topic": topic, "query": query_text or "General inquiry"})
            
            # Save disease mapping
            topic_str = str(topic)[:100]
            disease_id = db.get_disease_id_by_name(topic_str)
            if not disease_id:
                disease_id = db.upsert_disease({
                    "name": topic_str,
                    "category": "Unknown",
                })
                
            # Upsert into disease_guidelines
            db.upsert_guideline({
                "disease_id": disease_id,
                "guideline_type": "generated_overview",
                "title": f"Health Overview for {topic}",
                "content": content,
                "source": "AI_Generated",
                "source_url": "N/A"
            })
            
            # Resolve gap
            db.execute_query(
                "UPDATE knowledge_gaps SET status = 'resolved', resolved_at = NOW(), resolution_source = 'LLM_Generation' WHERE id = %s", 
                (gap_id,)
            )
            print(f"Successfully resolved gap ID {gap_id}")
            
        except Exception as e:
            print(f"Error resolving gap ID {gap_id}: {e}")

if __name__ == "__main__":
    fill_knowledge_gaps()
