# 🧬 Data Scraping & Storage Pipeline: Under the Hood

This document explains the end-to-end journey of data in DEB's Health Navigator, from a raw HTML page on a health portal to a structured record in our database.

---

## 1. Initiation: The Parallel Engine
**File:** `src/scraper/main.py`

The process starts here. Instead of fetching data one by one (which is slow), we use a **ThreadPoolExecutor**.
*   **Concurrency:** We launch `MAX_THREADS` (default 5) simultaneously.
*   **The Job List:** We instantiate a list of scraper objects (`WHOScraper`, `CDCScraper`, `StateScraper`, etc.).
*   **Execution:** Each scraper runs in its own thread, maximizing network throughput without blocking the CPU.

## 2. Extraction & ETL Strategy
**File:** `src/scraper/base_scraper.py`

We follow a strict **Extract-Transform-Load (ETL)** approach *within* each thread. Data is processed item-by-item (streaming) rather than in large batches. This ensures speed, resilience, and memory efficiency.

### 🛡️ The Two-Tier Fetching Strategy
1.  **Tier 1: Fast HTTP (Requests)**
    *   First attempt uses Python's `requests` library.
    *   **Why?** Extremely fast (milliseconds) and lightweight.
    *   **Retries:** `HTTPAdapter` automatically retries 3 times on 500/503 errors.
    *   **SSL Handling:** Custom SSL context to support government sites with expired certificates.

2.  **Tier 2: Heavy Artillery (Playwright)**
    *   **Trigger:** If Tier 1 fails (e.g., 403 Forbidden, 404 Soft Error, or empty content).
    *   **What it does:** Launches a headless Chromium browser.
    *   **Why?** Renders JavaScript, handles dynamic content loads, and behaves exactly like a real user, bypassing simple anti-bot protections.

### ⚡ The Lazy Check (Bandwidth Optimization)
Before fetching any URL, the scraper asks the database:
> *"Do we already have data from `https://who.int/dengue`?"*
*   **Yes:** The thread skips this item immediately. **Zero bandwidth wasted on static pages.**
*   **No:** It proceeds to download and process.

> **Note on New Data vs. Updates:**
> *   **Dynamic Feeds:** We **always** scrape the main "News Feed" or "Outbreak List" pages to find *new* links.
> *   **Individual Reports:** Once we find a link (e.g., "Outbreak Report #123"), we check if we've scraped it before. If yes, we skip it (assuming historical reports don't change).
> *   **Disease Factsheets:** Currently, we assume basic facts (Symptoms, Transmission) change rarely, so we skip re-scraping them to save resources. In a future update, we could add a "Time-To-Live" (e.g., re-scrape every 30 days) to catch updates.

## 3. Transformation: Cleaning the Mess
**File:** `src/scraper/normalizer.py`

Raw data is heterogeneous and messy. We normalize it *before* it touches the database.

*   **Fuzzy Matching (The "Dengue" Problem):**
    *   Source A calls it "Dengue Fever". Source B calls it "Dengue Virus".
    *   **Algorithm:** We use `fuzzywuzzy.process.extractOne` to compare input against our master `TARGET_DISEASES` list.
    *   **Configuration:** The threshold is set to **80%** in `src/scraper/normalizer.py`.
        ```python
        # Code reference: src/scraper/normalizer.py
        match, score = process.extractOne(name, TARGET_DISEASES)
        if score > 80: # <--- This is the threshold
            return match
        ```
    *   **Why 80?** This value was chosen empirically. It's high enough to avoid false positives (e.g., "Malaria" vs "Filaria") but low enough to catch variations. If you need stricter matching, increase this to 90.
*   **Date Parsing:**
    *   Handles formats like `YYYY-MM-DD`, `DD Month YYYY`, `XX days ago`.
    *   Converts everything to standard Python `date` objects.
*   **Location Mapping:** Maps variations (e.g., "U.P.", "Uttar Pradesh state") to canonical names.

## 4. Storage: The Upsert Algorithm
**File:** `src/scraper/db.py`

We use an **Upsert (Update or Insert)** strategy to merge data from multiple sources into a single "Master Record".

### 🧠 The Smart Merge Logic
When saving data, we don't just blindly insert. We use PostgreSQL's `ON CONFLICT` clause.

**Scenario:**
1.  **Thread A (WHO Scraper):** Finds "Dengue" with Symptom data.
    *   *Database Action:* Creates new record for "Dengue".
2.  **Thread B (CDC Scraper):** Finds "Dengue" with Treatment data.
    *   *Database Action:* formatting **Updates** the existing "Dengue" record. It *merges* the new Treatment info while keeping the existing Symptoms.

**SQL Logic:**
```sql
INSERT INTO diseases (name, symptoms, treatment)
VALUES ('Dengue', 'Fever...', 'Hydration...')
ON CONFLICT (name) DO UPDATE SET
    treatment = EXCLUDED.treatment,  -- Update treatment if new data has it
    symptoms = COALESCE(diseases.symptoms, EXCLUDED.symptoms); -- Keep existing symptoms if new data is empty
```
*   **Result:** A single, rich record containing the best data from ALL sources. No duplicates.

### 🗄️ The Dual Database System

#### 1. Structured Data (PostgreSQL)
*   **Content:** Outbreaks, Statistics, Trends.
*   **Why:** Relational consistency, complex querying, and transactional integrity.

#### 2. Semantic Data (ChromaDB)
*   **Content:** Long-form Guidelines, Protocols, Research Papers.
*   **Process:**
    1.  **Chunking:** Split text into 500-word segments.
    2.  **Embedding:** `SentenceTransformer` converts chunks into vector arrays (floats).
    3.  **Storage:** vectors are stored in ChromaDB (PERSISTENT).

### 🔍 retrieval: The Hybrid Search Engine
**File:** `src/api/rag_logic.py`

When a user asks a question, we don't just look in one place. We use a **Hybrid Search** strategy to get the best of both worlds.

#### 1. Semantic Search (ChromaDB)
*   **What it finds:** Concepts and meanings.
*   **Example:** Query "pain in joints" -> matches "severe arthralgia" in the vector space.
*   **Action:** We convert the user's query into a vector and find the nearest neighbors in ChromaDB.

#### 2. Keyword Search (BM25)
*   **What it finds:** Exact words and specific medical terms.
*   **Example:** Query "Nipah Virus" -> matches exact instances of "Nipah" in the text.
*   **How it works:**
    *   **On Startup:** The application reads all `disease_guidelines` from PostgreSQL.
    *   **In-Memory Index:** It builds a temporary **BM25 Index** in RAM.
    *   **Query Time:** It quickly scans this index for exact keyword matches.
    *   *Note: We do not store the BM25 index on disk; it is rebuilt every time the backend restarts to ensure it includes the latest data.*

#### 3. Reciprocal Rank Fusion (RRF)
We combine the results using RRF:
*   We take the top 50 results from Chroma (Semantic).
*   We take the top 50 results from BM25 (Keyword).
*   **Fusion:** We merge them, giving higher scores to documents that appear in *both* lists.
*   **Result:** The top 5 final documents are sent to the LLM to generate the answer.

## 6. Other Data Tables & Collection Methods

Besides the core disease tables, we store data in a few other places using different strategies:

### 📍 On-Demand Collection (`connect_cache_*`)
*   **Tables:** `connect_cache_doctors`, `connect_cache_hospitals`, `connect_cache_pharmacies`
*   **Strategy:** **Lazy Loading / On-Demand Scraping**
    *   **Trigger:** When a user requests "Nearby Doctors".
    *   **Process:**
        1.  Check DB for valid cached data (expires in 7 days).
        2.  **If Missing:** API calls the **Overpass API (OpenStreetMap)** to fetch fresh data for that specific latitude/longitude.
        3.  **Storage:** The result is "Upserted" into the cache tables for future fast retrieval.
    *   **Rate Limits:** The public Overpass API has strict limits:
        *   **Max Requests:** ~2 requests per second per IP.
        *   **Connection Limit:** Max 2 slots (simultaneous connections) per IP.
        *   **Query Timeout:** Default is 180 seconds.
        *   *If exceeded, the API returns HTTP 429 ("Too Many Requests"). Our `maps.py` handles this by logging the error and falling back to whatever cache is available.*

### 📚 Static Resources (`education_resources`)
*   **Content:** Curated Videos, Blogs, and Government Schemes.
*   **Strategy:** **Seeded Data**.
    *   We currently use a "Golden Set" of high-quality resources defined in `src/db/seed.sql`.
    *   **Why?** Educational content requires strict medical accuracy. Automated scraping might pick up misinformation, so we stick to a curated list for now.
    *   **Data Flow:** `seed.sql` -> `PostgreSQL` -> `API (/api/v1/education)` -> `Frontend`.

### 🧠 Real-Time Intelligence (Summaries)
*   **Feature:** "Generate AI Summary" button on education cards.
*   **Strategy:** **On-Demand Generation (Real-Time)**.
    *   **Stored?** NO. Summaries are *not* pre-generated or stored in the database.
    *   **Process:**
        1.  User clicks "Summarize" (and optionally selects a language).
        2.  Frontend sends the resource content/metadata to `/api/v1/education/generate` with a `language` parameter (e.g., "Hindi", "Tamil").
        3.  Backend constructs a prompt for Groq LLM: *"Generate a concise summary... Language: {language}"*
        4.  LLM generates the summary **in that specific language** on the fly.
        5.  Result is sent back to the user instantly.
    *   **Why?** Saves storage space and allows for personalized/language-specific summaries in the future (e.g., "Summarize in Hindi") without storing N versions of every summary.

### 🌐 Multilingual Support (No Google Translate Needed!)
**File:** `src/api/rag_logic.py`

A key question is: *How do we chat in Hindi if our database is in English?*

1.  **Cross-Lingual Retrieval (The "Magic" Embedding)**
    *   We use a special embedding model: `l3cube-pune/indic-sentence-bert-nli`.
    *   **Capability:** It understands 12+ Indian languages.
    *   **Supported Languages:** **Hindi, Marathi, Kannada, Tamil, Telugu, Gujarati, Odia, Punjabi, Malayalam, Bengali, Assamese, and English.**
    *   **How it works:** It maps "Bukhar" (Hindi) and "Fever" (English) to the *same* vector space.
    *   **Result:** You search in Hindi -> We find the relevant English documents. **No translation API needed.**

    > **Important Distinction:**
    > *   The **Embedding Model** ensures we *find* the right data (Understanding).
    > *   The **LLM (Llama-3)** ensures we *write* the answer in your language (Speaking).
    > *   *Result:* If you ask in Hindi, you get a response in Hindi. If you ask in Tamil, you get Tamil.

2.  **Generative Translation (The Polyglot LLM)**
    *   Once we find the English documents, we feed them to the LLM (Llama-3).
    *   **Instruction:** We simply tell the LLM: *"Here is the medical context in English. Answer the user's question in Hindi."*
    *   **Result:** The LLM reads English, thinks, and writes the final response in fluent Hindi/Tamil/etc.
    *   **Benefit:** This is faster and more accurate than using Google Translate on the final output, as the LLM understands the nuance of the medical context.

### 📝 Metadata (`scraper_logs`)
*   **Content:** Logs of every scraper execution.
*   **Why:** Audit trail to monitor scraper health and data freshness.

## 7. Logging & Monitoring
*   Every scraper run is logged in the `scraper_logs` table.
*   Tracks: Start/End Time, Records Found vs. Inserted vs. Skipped.
*   Allows distinct debugging of which source provided what data.
