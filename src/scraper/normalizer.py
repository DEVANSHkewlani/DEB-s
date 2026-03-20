import re
from datetime import datetime, date
from typing import Optional, Union
from fuzzywuzzy import process
from config import TARGET_DISEASES

# ── Extended Disease Aliases ──────────────────────────────────────────────────
# Checked BEFORE fuzzy matching for O(1) lookup.
DISEASE_ALIASES = {
    'dengue': [
        'dengue fever', 'dengue hemorrhagic fever', 'dengue haemorrhagic fever',
        'DHF', 'dengue virus', 'DF', 'DSS', 'dengue shock syndrome',
        'severe dengue', 'DENV',
    ],
    'malaria': [
        'p. falciparum', 'p. vivax', 'plasmodium', 'API',
        'falciparum malaria', 'vivax malaria', 'p.f.', 'p.v.',
        'plasmodium falciparum', 'plasmodium vivax', 'malarial fever',
    ],
    'cholera': [
        'acute watery diarrhoea', 'acute watery diarrhea', 'AWD',
        'el tor', 'vibrio cholerae', 'V. cholerae',
    ],
    'japanese encephalitis': [
        'JE', 'Japanese B encephalitis', 'viral encephalitis',
        'acute encephalitis syndrome', 'AES',
    ],
    'kala-azar': [
        'visceral leishmaniasis', 'VL', 'kala azar', 'kalazar',
        'leishmaniasis', 'leishmania', 'PKDL',
        'post kala azar dermal leishmaniasis',
    ],
    'leptospirosis': [
        "Weil's disease", 'Weil disease', 'leptospira', 'rat fever',
        'mud fever', "swineherd's disease",
    ],
    'typhoid': [
        'enteric fever', 'typhoid fever', 'salmonella typhi',
        'S. Typhi', 'S. typhi', 'paratyphoid',
    ],
    'chikungunya': ['CHIK', 'chikv', 'chikungunya virus', 'CHIKV'],
    'nipah': [
        'NiV', 'nipah virus infection', 'nipah virus', 'Nipah virus disease',
    ],
    'hepatitis': [
        'viral hepatitis', 'hepatitis virus', 'jaundice',
    ],
    'COVID-19': [
        'covid', 'coronavirus', 'SARS-CoV-2', 'corona virus',
        'novel coronavirus', 'covid-19', 'COVID', 'covid19',
    ],
    'tuberculosis': [
        'TB', 'pulmonary tuberculosis', 'Mycobacterium tuberculosis',
        'MDR-TB', 'XDR-TB', 'multi drug resistant TB',
    ],
    'influenza': [
        'flu', 'H1N1', 'H3N2', 'H5N1', 'avian influenza', 'bird flu',
        'swine flu', 'seasonal flu', 'influenza A', 'influenza B',
        'ILI', 'influenza like illness', 'SARI',
        'severe acute respiratory infection',
    ],
    'measles': ['rubeola', 'morbilli'],
    'meningitis': [
        'meningococcal meningitis', 'meningococcal disease',
        'N. meningitidis', 'bacterial meningitis',
    ],
    'rabies': ['rabies virus', 'hydrophobia', 'animal bite'],
    'plague': ['bubonic plague', 'pneumonic plague', 'Yersinia pestis'],
    'anthrax': ['Bacillus anthracis', 'cutaneous anthrax', 'inhalation anthrax'],
    'pneumonia': [
        'acute respiratory infection', 'ARI', 'lower respiratory infection',
        'community acquired pneumonia',
    ],
    'polio': [
        'poliomyelitis', 'acute flaccid paralysis', 'AFP',
        'poliovirus',
    ],
    'HIV/AIDS': ['HIV', 'AIDS', 'human immunodeficiency virus'],
    'mpox': ['monkeypox', 'monkey pox', 'MPXV'],
    'zika': ['Zika virus', 'ZIKV', 'zika fever'],
}

# Build reverse lookup: alias → canonical name
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in DISEASE_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical


# ── State Name Aliases ────────────────────────────────────────────────────────
CANONICAL_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

STATE_ALIASES = {
    'andhra pradesh': ['AP', 'Andhra', 'A.P.'],
    'arunachal pradesh': ['Arunachal', 'AR'],
    'assam': ['AS'],
    'bihar': ['BH', 'BR'],
    'chhattisgarh': ['CG', 'Chattisgarh', 'Chhatisgarh'],
    'goa': ['GA'],
    'gujarat': ['GJ'],
    'haryana': ['HR'],
    'himachal pradesh': ['HP', 'Himachal'],
    'jharkhand': ['JH'],
    'karnataka': ['KA', 'Karanataka'],
    'kerala': ['KL'],
    'madhya pradesh': ['MP', 'M.P.'],
    'maharashtra': ['MH'],
    'manipur': ['MN'],
    'meghalaya': ['ML'],
    'mizoram': ['MZ'],
    'nagaland': ['NL'],
    'odisha': ['OD', 'Orissa', 'OR'],
    'punjab': ['PB'],
    'rajasthan': ['RJ'],
    'sikkim': ['SK'],
    'tamil nadu': ['TN', 'Tamilnadu', 'Tamil-Nadu'],
    'telangana': ['TS', 'TG'],
    'tripura': ['TR'],
    'uttar pradesh': ['UP', 'U.P.'],
    'uttarakhand': ['UK', 'UA', 'Uttaranchal'],
    'west bengal': ['WB'],
    'andaman and nicobar islands': ['AN', 'A&N', 'Andaman', 'Andaman & Nicobar'],
    'chandigarh': ['CH'],
    'dadra and nagar haveli and daman and diu': ['DN', 'DD', 'DNH', 'Daman', 'Diu'],
    'delhi': ['NCT', 'NCT of Delhi', 'New Delhi', 'DL'],
    'jammu and kashmir': ['J&K', 'J & K', 'JK', 'Jammu & Kashmir'],
    'ladakh': ['LA'],
    'lakshadweep': ['LD'],
    'puducherry': ['PY', 'Pondicherry'],
}

# Build reverse lookup: alias → canonical state name (title-cased)
_STATE_ALIAS_TO_CANONICAL = {}
for canonical_lower, aliases in STATE_ALIASES.items():
    canonical_title = next(
        (s for s in CANONICAL_STATES if s.lower() == canonical_lower),
        canonical_lower.title()
    )
    for alias in aliases:
        _STATE_ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical_title


# ── Severity Thresholds ──────────────────────────────────────────────────────
_SEVERITY_THRESHOLDS = {
    # (min_cases, min_deaths) → severity
    'critical': (1000, 50),
    'severe':   (500,  10),
    'moderate': (100,   1),
    'low':      (0,     0),
}


class DataNormalizer:
    """Normalizes disease names, state names, dates, and extracts metadata."""

    # ── Disease Name Normalization ────────────────────────────────────────────

    @staticmethod
    def normalize_disease_name(name: str) -> Optional[str]:
        if not name:
            return None

        name = name.strip()

        # 1. Direct match against TARGET_DISEASES (case-sensitive)
        if name in TARGET_DISEASES:
            return name

        # 2. Alias lookup (case-insensitive, O(1))
        key = name.lower().strip()
        if key in _ALIAS_TO_CANONICAL:
            canonical = _ALIAS_TO_CANONICAL[key]
            # Map back to TARGET_DISEASES casing
            for td in TARGET_DISEASES:
                if td.lower() == canonical.lower():
                    return td
            return canonical  # fallback

        # 3. Case-insensitive direct match
        for td in TARGET_DISEASES:
            if td.lower() == key:
                return td

        # 4. Fuzzy match (expensive — last resort)
        match, score = process.extractOne(name, TARGET_DISEASES)
        if score > 80:
            return match

        return name  # Return original if no good match

    # ── Text Cleaning ────────────────────────────────────────────────────────

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ── Date Normalization ───────────────────────────────────────────────────

    @staticmethod
    def normalize_date(date_str: str) -> date:
        """
        Parse various date formats into a date object.
        Supports: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY,
                  DD Mon YYYY, Month DD YYYY, Week XX YYYY/YYYY, Month YYYY.
        Falls back to today's date if unparseable.
        """
        if not date_str:
            return datetime.now().date()

        date_str = date_str.strip()

        # ISO week format: "Week 20, 2024" or "W20 2024"
        week_match = re.match(r'[Ww](?:eek)?\s*(\d{1,2})[,\s]+(\d{4})', date_str)
        if week_match:
            week_num = int(week_match.group(1))
            year = int(week_match.group(2))
            try:
                return datetime.strptime(f'{year}-W{week_num:02d}-1', '%G-W%V-%u').date()
            except (ValueError, OverflowError):
                pass

        # "Month YYYY" format → first of that month
        month_year = re.match(r'([A-Za-z]+)\s+(\d{4})', date_str)
        if month_year:
            try:
                return datetime.strptime(f"1 {month_year.group(1)} {month_year.group(2)}", "%d %B %Y").date()
            except ValueError:
                try:
                    return datetime.strptime(f"1 {month_year.group(1)} {month_year.group(2)}", "%d %b %Y").date()
                except ValueError:
                    pass

        # Standard formats
        formats = [
            "%Y-%m-%d",        # 2024-01-15
            "%d-%m-%Y",        # 15-01-2024
            "%d/%m/%Y",        # 15/01/2024
            "%d.%m.%Y",        # 15.01.2024
            "%d %b %Y",        # 15 Jan 2024
            "%d %B %Y",        # 15 January 2024
            "%B %d, %Y",       # January 15, 2024
            "%b %d, %Y",       # Jan 15, 2024
            "%Y/%m/%d",        # 2024/01/15
            "%m/%d/%Y",        # 01/15/2024  (US format — try after DD/MM)
            "%d-%b-%Y",        # 15-Jan-2024
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return datetime.now().date()

    # ── Severity Extraction ──────────────────────────────────────────────────

    @staticmethod
    def extract_severity(text: str) -> str:
        """Extract severity level from descriptive text."""
        text = text.lower()
        if any(w in text for w in ['critical', 'epidemic', 'emergency', 'pandemic']):
            return 'critical'
        if any(w in text for w in ['severe', 'high', 'serious', 'alarming']):
            return 'severe'
        if any(w in text for w in ['moderate', 'medium', 'rising', 'increasing']):
            return 'moderate'
        if any(w in text for w in ['low', 'mild', 'contained', 'declining']):
            return 'low'
        return 'moderate'

    @staticmethod
    def compute_severity(cases: int = 0, deaths: int = 0) -> str:
        """Compute severity from case/death counts using thresholds."""
        cases = cases or 0
        deaths = deaths or 0
        if cases >= 1000 or deaths >= 50:
            return 'critical'
        if cases >= 500 or deaths >= 10:
            return 'severe'
        if cases >= 100 or deaths >= 1:
            return 'moderate'
        return 'low'

    # ── State Name Normalization ─────────────────────────────────────────────

    @staticmethod
    def normalize_state(state_name: str) -> Optional[str]:
        """
        Normalize Indian state/UT name.
        Checks aliases first (O(1)), then fuzzy match.
        """
        if not state_name:
            return None

        state_name = state_name.strip()
        key = state_name.lower().strip()

        # 1. Alias lookup (includes abbreviations like TN, AP, UP)
        if key in _STATE_ALIAS_TO_CANONICAL:
            return _STATE_ALIAS_TO_CANONICAL[key]

        # 2. Direct match (case-insensitive)
        for s in CANONICAL_STATES:
            if s.lower() == key:
                return s

        # 3. Fuzzy match
        match, score = process.extractOne(state_name, CANONICAL_STATES)
        if score > 70:
            return match

        return state_name

    # ── Metadata Extraction Helpers ──────────────────────────────────────────

    @staticmethod
    def extract_incubation_period(text: str) -> Optional[str]:
        if not isinstance(text, str) or not text:
            return None
        patterns = [
            r'(\d+\s*(?:to|-)\s*\d+\s*(?:days|weeks|months|hours))',
            r'(\d+\s*(?:days|weeks|months|hours))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def extract_mortality_rate(text: str) -> Optional[float]:
        if not isinstance(text, str) or not text:
            return None
        pattern = r'(\d+(?:\.\d+)?)\s*%'
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    def extract_case_numbers(text: str) -> dict:
        """
        Extract case and death counts from free text.
        Returns {'cases': int|None, 'deaths': int|None}.
        """
        result = {'cases': None, 'deaths': None}
        if not text:
            return result

        # Cases patterns
        cases_patterns = [
            r'(\d[\d,]*)\s*(?:cases?\s*(?:reported|confirmed|detected|found))',
            r'(?:total|reported|confirmed)\s*(?:of\s*)?(\d[\d,]*)\s*cases?',
            r'(\d[\d,]*)\s*(?:new\s*)?cases?',
        ]
        for pat in cases_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result['cases'] = int(m.group(1).replace(',', ''))
                break

        # Deaths patterns
        deaths_patterns = [
            r'(\d[\d,]*)\s*(?:deaths?|fatalities|died)',
            r'(?:deaths?|fatalities)\s*(?:of\s*)?(\d[\d,]*)',
        ]
        for pat in deaths_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result['deaths'] = int(m.group(1).replace(',', ''))
                break

        return result
