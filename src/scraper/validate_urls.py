import requests
import sys
import os

# Add the parent directory to sys.path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WHO_SLUG_MAP, URLS, TARGET_DISEASES

def check_url(url, name):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            print(f"[OK] {name}: {url}")
            return True
        else:
            print(f"[FAIL {response.status_code}] {name}: {url}")
            return False
    except Exception as e:
        print(f"[ERROR] {name}: {url} - {e}")
        return False

def validate_who_urls():
    print("\n--- Validating WHO URLs ---")
    base_url = URLS['WHO_FACTSHEETS']
    
    # Check manual map
    for disease, slug in WHO_SLUG_MAP.items():
        if not slug:
            print(f"[SKIP] {disease}: No slug defined")
            continue
        url = f"{base_url}/detail/{slug}"
        check_url(url, disease)

    # Check unmapped diseases (auto-generated slugs)
    for disease in TARGET_DISEASES:
        if disease not in WHO_SLUG_MAP:
             slug = disease.lower().replace(" ", "-")
             url = f"{base_url}/detail/{slug}"
             check_url(url, f"{disease} (Auto)")

def validate_cdc_urls():
    print("\n--- Validating CDC URLs ---")
    for disease in TARGET_DISEASES:
        slug = disease.lower().replace(" ", "-")
        # Try the most common pattern
        url = f"https://www.cdc.gov/{slug}/index.html"
        check_url(url, disease)

if __name__ == "__main__":
    validate_who_urls()
    validate_cdc_urls()
