import os
import chromadb
from scraper.db import DatabaseManager
from sentence_transformers import SentenceTransformer
import tqdm

def populate_vectors():
    # 1. Setup Models & DB
    print("Loading IndicSBERT model...")
    model = SentenceTransformer("l3cube-pune/indic-sentence-bert-nli")
    
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="health_guidelines", metadata={"hnsw:space": "cosine"})
    
    db = DatabaseManager()
    
    # 2. Fetch Guidelines
    print("Fetching guidelines from Postgres...")
    guidelines = db.execute_query("SELECT id, title, content FROM unified_search_index", fetch="all")
    
    if not guidelines:
        print("No guidelines found.")
        return

    ids = []
    docs = []
    embeddings = []
    metadatas = []
    
    print(f"Processing {len(guidelines)} documents...")
    batch_size = 32
    
    for i in tqdm.tqdm(range(0, len(guidelines), batch_size)):
        batch = guidelines[i:i+batch_size]
        batch_ids = [str(g[0]) for g in batch]
        batch_texts = [f"{g[1]}\n{g[2]}" for g in batch]
        batch_metas = [{"title": g[1]} for g in batch]
        
        # Generate embeddings
        batch_embeddings = model.encode(batch_texts).tolist()
        
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_texts,
            metadatas=batch_metas
        )

    print(f"Successfully populated ChromaDB with {len(guidelines)} vectors.")

if __name__ == "__main__":
    populate_vectors()
