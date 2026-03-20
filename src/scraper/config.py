import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "deb_health_db"),
    "user": os.getenv("DB_USER", "devanshkewlani"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

# Medicine Lens configuration
OPENFDA_BASE_URL = os.getenv("OPENFDA_BASE_URL", "https://api.fda.gov/drug/label.json")
LENS_CHAT_MODEL = os.getenv("LENS_CHAT_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Scraper Settings
RATE_LIMIT_DELAY = 1
SELENIUM_DELAY = 5    
MAX_THREADS = 5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Comprehensive Health Topics
TARGET_DISEASES = [
    # Infectious Diseases
    "Dengue", "Malaria", "COVID-19", "Influenza", "Typhoid", "Cholera",
    "Tuberculosis", "Zika", "Chikungunya", "Nipah", "Mpox", "Measles",
    "Hepatitis", "HIV/AIDS", "Pneumonia", "Meningitis", "Leptospirosis",
    "Rabies", "Anthrax", "Brucellosis", "Japanese Encephalitis", "Kala-azar",
    "Yellow Fever", "Ebola", "Lassa Fever", "Smallpox", "Polio",
    
    # Seasonal & Environmental
    "Heatstroke", "Dehydration", "Sunburn", "Hay Fever", "Asthma", 
    "Common Cold", "Waterborne Diseases", "Frostbite",
    "Seasonal Affective Disorder", "Respiratory Allergies",
    
    # Old Age & Chronic
    "Arthritis", "Osteoporosis", "Alzheimer's", "Dementia", "Cataract",
    "Diabetes", "Hypertension", "Heart Disease", "Stroke", "Parkinson's",
    "Glaucoma", "Hearing Loss", "Macular Degeneration", "Urinary Incontinence",
    
    # Lifestyle & Metabolic
    "Obesity", "Thyroid", "Chronic Bronchitis", "Kidney Stones", 
    "Fatty Liver", "Acid Reflux", "Back Pain", "Insomnia", "Depression",
    "Anemia", "PCOS", "Uric Acid", "Cholesterol",
    
    # Emergency & First Aid
    "Snake Bite", "Burns", "Poisoning", "Fracture", "Electric Shock",
    "Choking", "Bleeding", "Heart Attack Symptoms", "Heat Exhaustion",
    "First Aid", "CPR", "Emergency Procedures"
    ,
    # Mental Health & Neurology
    "Anxiety", "Panic Attack", "Bipolar Disorder", "Schizophrenia", "ADHD", "Autism Spectrum Disorder",
    "Migraine", "Epilepsy", "Multiple Sclerosis", "Peripheral Neuropathy",
    # Skin & Allergy
    "Eczema", "Psoriasis", "Acne", "Urticaria (Hives)", "Food Allergy", "Drug Allergy",
    # Gastrointestinal
    "Irritable Bowel Syndrome (IBS)", "Crohn's Disease", "Ulcerative Colitis", "Celiac Disease",
    "Gallstones", "Pancreatitis", "Constipation", "Diarrhea",
    # Respiratory
    "COPD", "Bronchitis", "Sinusitis", "Pneumothorax",
    # Women’s & Reproductive Health
    "Endometriosis", "Menstrual Cramps", "Menopause", "Pregnancy", "Preeclampsia",
    "Urinary Tract Infection (UTI)",
    # Cancer (high-level topics)
    "Breast Cancer", "Lung Cancer", "Colorectal Cancer", "Prostate Cancer", "Cervical Cancer",
    # Musculoskeletal
    "Gout", "Sciatica", "Neck Pain", "Shoulder Pain",
    # Eye & ENT
    "Conjunctivitis", "Dry Eyes", "Ear Infection", "Tinnitus", "Vertigo",
    # Pediatrics
    "Chickenpox", "Hand Foot and Mouth Disease", "Whooping Cough", "Bronchiolitis",
    # Nutrition & Deficiencies
    "Vitamin D Deficiency", "Vitamin B12 Deficiency", "Malnutrition"
]

# WHO Specific Slug Mapping
WHO_SLUG_MAP = {
    # Chronic & Lifestyle
    "Alzheimer's": "dementia",
    "Anemia": "anaemia",
    "Heart Disease": "cardiovascular-diseases-(cvds)",
    "Back Pain": "low-back-pain",
    "Chronic Bronchitis": "chronic-obstructive-pulmonary-disease-(copd)",
    "Parkinson's": "parkinson-disease",
    "PCOS": "polycystic-ovary-syndrome",
    "Hearing Loss": "deafness-and-hearing-loss",
    "Diabetes": "diabetes",
    "Hypertension": "hypertension",
    "Obesity": "obesity-and-overweight",
    "Asthma": "asthma",
    "Cataract": "blindness-and-vision-loss",
    "Glaucoma": "blindness-and-vision-loss",
    "Macular Degeneration": "blindness-and-vision-loss",
    "Arthritis": "rheumatoid-arthritis",
    "Stroke": "stroke-cerebrovascular-accident",
    # Infectious
    "COVID-19": "coronavirus-disease-(covid-19)",
    "Nipah": "nipah-virus",
    "HIV/AIDS": "hiv-aids",
    "Kala-azar": "leishmaniasis",
    "Ebola": "ebola-virus-disease",
    "Mpox": "monkeypox",
    "Zika": "zika-virus",
    "Malaria": "malaria",
    "Dengue": "dengue-and-severe-dengue",
    "Tuberculosis": "tuberculosis",
    "Rabies": "rabies",
    "Polio": "poliomyelitis",
    "Cholera": "cholera",
    "Influenza": "influenza-(seasonal)",
    "Typhoid": "typhoid",
    "Chikungunya": "chikungunya",
    "Measles": "measles",
    "Hepatitis": "hepatitis",
    "Pneumonia": "pneumonia",
    "Meningitis": "meningitis",
    "Leptospirosis": "leptospirosis",
    "Anthrax": "anthrax",
    "Brucellosis": "brucellosis",
    "Japanese Encephalitis": "japanese-encephalitis",
    "Yellow Fever": "yellow-fever",
    "Lassa Fever": "lassa-fever",
    "Smallpox": "smallpox",
    "Snake Bite": "snakebite-envenoming",
    "Burns": "burns",
    "Poisoning": "poisoning-prevention"
}

CDC_SLUG_MAP = {
    # Chronic & Lifestyle
    "Alzheimer's": "alzheimers",
    "Anemia": "ncbddd/blooddisorders/anemia",
    "Arthritis": "arthritis",
    "Cholesterol": "cholesterol",
    "Chronic Bronchitis": "copd",
    "Glaucoma": "visionhealth/conditions/glaucoma.html",
    "Cataract": "visionhealth/conditions/cataract.html",
    "Macular Degeneration": "visionhealth/conditions/macular-degeneration.html",
    "Hearing Loss": "ncbddd/hearingloss",
    "Insomnia": "sleep",
    "Osteoporosis": "osteoporosis",
    "Parkinson's": "ncbddd/disabilities-health-care-focus/parkinsons.html",
    "Thyroid": "genomics/disease/thyroid.htm",
    "Diabetes": "diabetes",
    "Hypertension": "bloodpressure",
    "Obesity": "obesity",
    "Asthma": "asthma",
    "Heart Disease": "heartdisease",
    "PCOS": "women/reproductive-health/pcos",
    "Acid Reflux": "digestive-diseases",
    "Back Pain": "acute-pain/low-back-pain",
    "Kidney Stones": "kidneydisease",
    
    # Emergency & First Aid
    "Snake Bite": "niosh/topics/snakes",
    "Burns": "massthrauma/burns",
    "Poisoning": "safe-healthy-home/poisoning",
    "Fracture": "falls",
    "Electric Shock": "disasters/lightning",
    "Choking": "nutrition/infantandtoddlernutrition/foods-and-drinks/choking-hazards.html",
    "Bleeding": "stopthebleed",
    "Heart Attack Symptoms": "heartdisease/heart-attack",
    "Heat Exhaustion": "disasters/extremeheat/warning-signs.html",
    "First Aid": "disasters/index.html",
    "CPR": "heartdisease/cpr",
    "Emergency Procedures": "prepyourhealth"
}

# Website URLs (Updated with verified reliable URLs)
URLS = {
    "WHO_FACTSHEETS": "https://www.who.int/news-room/fact-sheets",
    "WHO_DON": "https://www.who.int/emergencies/disease-outbreak-news",
    "CDC_INDEX": "https://www.cdc.gov/diseases-conditions/index.html",
    "CDC_MMWR": "https://www.cdc.gov/mmwr/index.html",
    "ECDC_TOPICS": "https://www.ecdc.europa.eu/en/all-topics",
    "NCDC_ANNOUNCEMENTS": "https://ncdc.mohfw.gov.in/",
    "MOHFW": "https://www.mohfw.gov.in/?q=en", # English version
    "ICMR": "https://www.icmr.gov.in/",
    "NHM": "https://nhm.gov.in/",
    # New Sources
    "MEDLINE": "https://medlineplus.gov/healthtopics.html",
    "MAYO_CLINIC": "https://www.mayoclinic.org/diseases-conditions",
    "NHS": "https://www.nhs.uk/conditions/",
    "CLEVELAND_CLINIC": "https://my.clevelandclinic.org/health/diseases",
    "DRUGS_COM": "https://www.drugs.com/health-guide/",
    "DAILYMED": "https://dailymed.nlm.nih.gov/dailymed/",
    "ORPHANET": "https://www.orpha.net/en/disease",
    "GARD": "https://rarediseases.info.nih.gov/diseases",
    "STATE_SITES": {
        "Himachal Pradesh": "https://hphealth.nic.in",
        "Jammu & Kashmir": "https://www.jkhealth.org",
        "Punjab": "https://health.punjab.gov.in",
        "Haryana": "https://haryanahealth.nic.in",
        "Delhi": "https://health.delhi.gov.in",
        "Uttarakhand": "https://health.uk.gov.in",
        "Uttar Pradesh": "http://uphealth.up.nic.in",
        "Maharashtra": "https://phd.maharashtra.gov.in",
        "Rajasthan": "https://rajswasthya.nic.in",
        "Gujarat": "https://health.gujarat.gov.in",
        "Goa": "https://dhsgoa.gov.in",
        "Karnataka": "https://hfw.karnataka.gov.in",
        "Kerala": "https://dhs.kerala.gov.in",
        "Tamil Nadu": "https://tnhealth.tn.gov.in",
        "Andhra Pradesh": "https://hmfw.ap.gov.in",
        "Telangana": "https://health.telangana.gov.in",
        "West Bengal": "https://www.wbhealth.gov.in",
        "Odisha": "https://health.odisha.gov.in",
        "Bihar": "https://health.bihar.gov.in",
        "Jharkhand": "https://jrhms.jharkhand.gov.in",
        "Madhya Pradesh": "https://health.mp.gov.in",
        "Chhattisgarh": "https://cghealth.nic.in",
        "Assam": "https://nhm.assam.gov.in",
        "Meghalaya": "https://meghealth.gov.in",
        "Arunachal Pradesh": "https://health.arunachal.gov.in",
        "Manipur": "https://manipurhealthdirectorate.mn.gov.in",
        "Mizoram": "https://health.mizoram.gov.in",
        "Nagaland": "https://nagahealth.nagaland.gov.in",
        "Tripura": "https://health.tripura.gov.in"
    }
}

# ── IDSP (Integrated Disease Surveillance Programme) ──────────────────────
IDSP_URLS = {
    "WEEKLY_BULLETIN": "https://idsp.mohfw.gov.in/index4.php?lang=1&level=0&linkid=406&lid=3689",
    "EPIDEMIC_SURVEILLANCE": "https://idsp.mohfw.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3715",
    "STATE_REPORTS": "https://idsp.mohfw.gov.in/index4.php?lang=1&level=0&linkid=406&lid=3714",
    "BASE": "https://idsp.mohfw.gov.in",
}

# ── NVBDCP (National Vector Borne Disease Control Programme) ──────────────
NVBDCP_URLS = {
    "DENGUE": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3715",
    "MALARIA": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3713",
    "CHIKUNGUNYA": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3712",
    "KALA_AZAR": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3714",
    "JE": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3716",
    "FILARIA": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3711",
    "BASE": "https://nvbdcp.gov.in",
}

# ── MoHFW (Ministry of Health and Family Welfare) ─────────────────────────
MOHFW_URLS = {
    "PRESS_RELEASES": "https://mohfw.gov.in/media/press-release",
    "HEALTH_ADVISORIES": "https://mohfw.gov.in/media/health-advisory",
    "SITUATION_UPDATES": "https://mohfw.gov.in/disease-situation-update",
    "BASE": "https://mohfw.gov.in",
}

# ── WHO ───────────────────────────────────────────────────────────────────
WHO_DON_RSS = "https://www.who.int/rss-feeds/news-en.xml"

WHO_FACTSHEET_DISEASES = {
    "Dengue": "dengue-and-severe-dengue",
    "Malaria": "malaria",
    "Cholera": "cholera",
    "Tuberculosis": "tuberculosis",
    "Typhoid": "typhoid",
    "Japanese Encephalitis": "japanese-encephalitis",
    "Leptospirosis": "leptospirosis",
    "Nipah": "nipah-virus",
    "Kala-azar": "leishmaniasis",
    "Chikungunya": "chikungunya",
    "Hepatitis": "hepatitis-a",
    "Rabies": "rabies",
    "COVID-19": "coronavirus-disease-(covid-19)",
    "Influenza": "influenza-(seasonal)",
    "Plague": "plague",
    "Measles": "measles",
    "Meningitis": "meningococcal-meningitis",
    "Anthrax": "anthrax",
}

# ── CDC ───────────────────────────────────────────────────────────────────
CDC_TRAVELER_INDIA = "https://wwwnc.cdc.gov/travel/destinations/traveler/none/india"

# ── ICMR ──────────────────────────────────────────────────────────────────
ICMR_URLS = {
    "PUBLICATIONS": "https://main.icmr.nic.in/content/publications",
    "GUIDELINES": "https://icmr.gov.in/guidelines",
    "BASE": "https://icmr.gov.in",
}

# ── ECDC ──────────────────────────────────────────────────────────────────
ECDC_URLS = {
    "SURVEILLANCE": "https://www.ecdc.europa.eu/en/surveillance-and-disease-data",
    "THREATS": "https://www.ecdc.europa.eu/en/publications-data/communicable-disease-threats-report",
    "OUTBREAKS": "https://www.ecdc.europa.eu/en/news-events/events-and-outbreaks",
    "TOPICS": "https://www.ecdc.europa.eu/en/all-topics",
}

# ── NHM (National Health Mission) ─────────────────────────────────────────
NHM_URLS = {
    "GUIDELINES": "https://nhm.gov.in/index1.php?lang=1&level=1&sublinkid=150&lid=226",
    "DISEASE_PROGRAMS": "https://nhm.gov.in/index1.php?lang=1&level=0&sublinkid=8&lid=13",
    "REPORTS": "https://nhm.gov.in/index1.php?lang=1&level=1&sublinkid=1161&lid=649",
    "BASE": "https://nhm.gov.in",
}

# ── PIB (Press Information Bureau) ────────────────────────────────────────
PIB_RSS = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"

# ── Priority State Sites (12 high-value states for outbreak data) ─────────
STATE_PRIORITY_SITES = {
    "Kerala": {"url": "https://dhs.kerala.gov.in/disease-surveillance/", "type": "html_weekly"},
    "Maharashtra": {"url": "https://arogya.maharashtra.gov.in", "type": "pdf_monthly"},
    "Karnataka": {"url": "https://karunadu.karnataka.gov.in/hfw", "type": "html_weekly"},
    "Tamil Nadu": {"url": "https://health.tn.gov.in", "type": "html_table"},
    "Delhi": {"url": "https://health.delhigovt.nic.in", "type": "pdf_weekly"},
    "Uttar Pradesh": {"url": "https://uphealth.up.nic.in", "type": "irregular"},
    "West Bengal": {"url": "https://wbhealth.gov.in", "type": "pdf_monthly"},
    "Rajasthan": {"url": "https://rajswasthya.nic.in", "type": "quarterly"},
    "Gujarat": {"url": "https://gujhealth.gujarat.gov.in", "type": "html_weekly"},
    "Assam": {"url": "https://nhm.assam.gov.in", "type": "pdf_monthly"},
    "Odisha": {"url": "https://nrhmorissa.gov.in", "type": "malaria_focus"},
    "Bihar": {"url": "https://state.bihar.gov.in/health", "type": "kala_azar_focus"},
}

# ── Health Keywords (for filtering press releases / news) ─────────────────
HEALTH_KEYWORDS = [
    "outbreak", "cases", "deaths", "alert", "advisory", "epidemic", "pandemic",
    "dengue", "malaria", "cholera", "plague", "nipah", "encephalitis",
    "leptospirosis", "typhoid", "hepatitis", "H1N1", "H5N1", "chikungunya",
    "tuberculosis", "measles", "influenza", "rabies", "anthrax",
    "vaccination", "immunization", "disease", "infection", "surveillance",
]

ESSENTIAL_MEDICINES = [
    # Analgesics & Antipyretics
    "paracetamol", "acetaminophen", "ibuprofen", "diclofenac", "naproxen", "aspirin", "tramadol", "meloxicam", "celecoxib",
    # Antibiotics
    "amoxicillin", "azithromycin", "ceftriaxone", "ciprofloxacin", "levofloxacin", "doxycycline", "metronidazole", "cotrimoxazole",
    "gentamicin", "meropenem", "piperacillin", "vancomycin", "cefixime", "amoxicillin-clavulanate", "clarithromycin", "clindamycin",
    # Antimalarials
    "chloroquine", "artemether", "lumefantrine", "mefloquine", "primaquine", "quinine", "artesunate", "proguanil", "hydroxychloroquine",
    # Antivirals
    "oseltamivir", "zanamivir", "remdesivir", "molnupiravir", "nirmatrelvir", "acyclovir", "valacyclovir", "ritonavir", "lopinavir",
    "entecavir", "tenofovir", "sofosbuvir", "daclatasvir",
    # Antifungals
    "fluconazole", "itraconazole", "amphotericin B", "voriconazole", "caspofungin", "clotrimazole", "miconazole",
    # Tuberculosis (Anti-TB)
    "isoniazid", "rifampicin", "pyrazinamide", "ethambutol", "streptomycin", "bedaquiline", "delamanid", "linezolid",
    # Kala-azar / Leishmaniasis
    "miltefosine", "sodium stibogluconate", "liposomal amphotericin B", "paromomycin",
    # Cardiovascular & Antihypertensives
    "amlodipine", "losartan", "telmisartan", "enalapril", "ramipril", "metoprolol", "atenolol", "bisoprolol", "carvedilol",
    "atorvastatin", "rosuvastatin", "simvastatin", "clopidogrel", "ticagrelor", "heparin", "warfarin", "rivaroxaban", "apixaban",
    # Diabetes
    "metformin", "glimepiride", "gliclazide", "sitagliptin", "vildagliptin", "linagliptin", "dapagliflozin", "empagliflozin",
    "insulin glargine", "insulin aspart", "insulin human", "pioglitazone",
    # Respiratory & Asthma
    "salbutamol", "albuterol", "formoterol", "salmeterol", "budesonide", "fluticasone", "montelukast", "ipratropium", "tiotropium",
    "theophylline", "levocetirizine", "cetirizine", "fexofenadine",
    # Gastrointestinal
    "omeprazole", "pantoprazole", "rabeprazole", "esomeprazole", "ranitidine", "famotidine", "ondansetron", "domperidone",
    "metoclopramide", "loperamide", "bisacodyl", "lactulose", "hyoscine", "drotaverine", "oral rehydration salts",
    # Neurology & Psychiatry
    "levetiracetam", "valproate", "phenytoin", "carbamazepine", "lamotrigine", "escitalopram", "sertraline", "fluoxetine",
    "paroxetine", "venlafaxine", "duloxetine", "olanzapine", "risperidone", "quetiapine", "clonazepam", "lorazepam", "diazepam",
    "alprazolam", "donepezil", "memantine", "levodopa", "carbidopa",
    # Other Commonly Used
    "zinc sulfate", "vitamin c", "vitamin d3", "calcium carbonate", "iron polymaltose", "ferrous sulfate", "folic acid",
    "methotrexate", "sulfasalazine", "corticosteroids", "prednisolone", "dexamethasone", "hydrocortisone", "methylprednisolone",
    "thyroxine", "levothyroxine", "carbimazole", "allopurinol", "febuxostat", "colchicine",
    # Vaccines / Toxoids & Immunoglobulins
    "rabies vaccine", "rabies immunoglobulin", "JE vaccine", "measles vaccine", "BCG vaccine", "tetanus toxoid",
    "hepatitis B vaccine", "diphtheria toxoid", "polio vaccine", "rotavirus vaccine",
]

# API Loader Settings
API_CACHE_ENABLED = True  # Skip API call if DB already has data
API_TIMEOUT = 15          # seconds per request
API_RETRIES = 2
API_USER_AGENT = "DEBsHealthNavigator/1.0 (health research project)"

# WHO GHO Indicator Codes for key diseases
WHO_INDICATOR_MAP = {
    'Malaria': 'MALARIA_CASES_CONFIRMED',
    'Tuberculosis': 'MDG_0000000020',
    'HIV/AIDS': 'HIV_0000000001',
    'Dengue': 'DENGUE_CASES',
    'Cholera': 'CHOLERA_0000000001',
}
