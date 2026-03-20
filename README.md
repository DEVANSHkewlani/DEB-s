# DEB's Health Navigator

DEB's Health Navigator is a state-of-the-art health information ecosystem that merges real-time global disease surveillance, interactive medical mapping, and advanced AI-powered medicine analysis to provide accurate, context-aware health guidance.

---

## 🚀 Key Features

### 🔍 **AI Medicine Lens** (NEW)
*   **Live OCR Scanning:** Point your camera at any medicine packaging to extract the brand or generic name instantly using **Tesseract.js**.
*   **3-Tier Intelligent Lookup:**
    1.  **Local DB:** Searches for verified Indian drug records (CDSCO based).
    2.  **Global API:** Fallback to **OpenFDA** for international drug profiles.
    3.  **AI RAG:** Final fallback to **Groq Llama-3** for detailed pharmacological synthesis.
*   **Contextual AI Pharmacist:** Ask follow-up questions about dosage, side effects, and pregnancy safety for the scanned medicine.

### 🗺️ **Interactive Health Maps & Emergency Connect**
*   **Proximity Search:** Locate the nearest **Hospitals, Pharmacies, and Doctors** using **OpenStreetMap (OSM)** and **Leaflet**.
*   **One-Tap Emergency:** A specialized mode that identifies the closest medical facility and provides immediate **AI-generated first aid protocols** tailored to the suspected condition.
*   **Offline-Ready Protocols:** Critical first-aid instructions available for emergency situations.

### 🤖 **AI Health Assistant (RAG Chatbot)**
*   **Domain-Specific Intelligence:** Answers health queries using a **Retrieval-Augmented Generation (RAG)** pipeline.
*   **Hybrid Search:** Combines vector embeddings (**SentenceTransformers**) with keyword search (**BM25**) for maximum accuracy.
*   **Verified Sources:** Prioritizes data from **WHO, CDC, and ICMR** guidelines.

### 📡 **Global Disease Surveillance**
*   **Real-time Tracking:** Parallel scraping engine monitors **WHO, CDC, ECDC, MoHFW, ICMR, and NCDC**.
*   **Hyper-Local Alerts:** Geofenced outbreak notifications at the State and District level in India.
*   **Historical Trends:** Visualizes disease growth rates using multi-year data from the **NVBDCP**.

### 🧩 **Knowledge Gap System**
*   **System Self-Correction:** Identifies when users ask questions the system cannot answer, flagging "Knowledge Gaps" for automated or manual data replenishment.
*   **Dynamic Scrapers:** Background workers that fetch missing medicine or disease info to fill gaps in real-time.

---

## 🛠️ Tech Stack

*   **Backend:** Python 3.9+, FastAPI, Uvicorn
*   **Database:**
    *   **PostgreSQL:** Relational data (diseases, outbreaks, drugs, trends).
    *   **ChromaDB:** Vector store for medical guidelines.
*   **AI/ML:**
    *   **Groq (Llama-3):** Core LLM for RAG and Medicine Lens.
    *   **SentenceTransformers:** Text embeddings (`all-MiniLM-L6-v2`).
    *   **Tesseract.js:** In-browser OCR for Medicine Lens.
*   **Data Pipeline:**
    *   **Apis:** OpenFDA, NIH Clinical Tables, WHO GHO OData, MedlinePlus WS.
    *   **Scrapers:** Requests, Playwright (for JS-heavy portals), BeautifulSoup4.
*   **Frontend:**
    *   **UI:** HTML5, Vanilla JavaScript, Tailwind CSS.
    *   **Maps:** Leaflet.js, CartoDB Dark Matter.

---

## 📂 Project Structure

```bash
├── public/                 # Frontend Assets & Pages
│   ├── pages/
│   │   ├── lens.html       # AI Medicine Lens interface
│   │   ├── maps.html       # Interactive health mapping
│   │   └── ...
│   └── assets/js/
│       ├── chatbot.js      # RAG Chatbot logic
│       ├── maps.js         # Leaflet & OSM integration
│       └── ...
├── src/
│   ├── api/                # FastAPI Endpoints
│   │   ├── routers/        # Feature-specific routes (alerts, lens, gaps)
│   │   └── rag_logic.py    # Core RAG / AI Pipeline
│   ├── scraper/            # Data Collection
│   │   ├── scrapers/       # Source-specific scrapers (WHO, CDC, etc.)
│   │   ├── normalizer.py   # Data standardization logic
│   │   └── fill_knowledge_gaps.py # Automated info replenishment
│   ├── ml/                 # Data Loaders & ML utilities
│   │   └── data_loaders/   # NVBDCP, CDSCO, and National Health loaders
│   └── main.py             # App Entry Point
├── api_loaders.py          # Unified API data ingestion script
└── .env                    # Environment config
```

---

## ⚡ Setup & Installation

### 1. Prerequisites
*   Python 3.9+
*   PostgreSQL
*   Groq API Key ([Get one here](https://console.groq.com/))

### 2. Environment Setup
Create a `.env` file:
```env
DB_NAME=deb_health_db
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
GROQ_API_KEY=your_groq_api_key
```

### 3. Install
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Running the App
**Start Backend:**
```bash
python src/main.py
```
**Start Scrapers (Optional):**
```bash
python src/scraper/main.py
```
**Sync Global Data (Initial Run):**
```bash
python api_loaders.py --all
```

---

## 🧠 Data Sovereignty & Accuracy
All medical information is referenced back to its original source (**WHO, CDSCO, OpenFDA**). The **Medicine Lens** explicitly labels AI-generated content and prompts users to verify with professionals, ensuring transparent and safe guidance.
