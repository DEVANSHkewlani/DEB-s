import time
import logging
import requests
import urllib3
import hashlib
from datetime import datetime, date
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

try:
    from scraper.config import RATE_LIMIT_DELAY, USER_AGENT
    from scraper.db import DatabaseManager
    from scraper.normalizer import DataNormalizer
    from scraper.pdf_parser import PDFParser
except ImportError:
    from config import RATE_LIMIT_DELAY, USER_AGENT
    from db import DatabaseManager
    from normalizer import DataNormalizer
    from pdf_parser import PDFParser

# Suppress InsecureRequestWarning for government sites with SSL issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BaseScraper:
    """
    Base class for all DEB's Health Navigator scrapers.

    Provides:
    - HTTP session with retries + Playwright fallback
    - ETag / Last-Modified change detection  (fetch_with_cache)
    - Transactional run wrapper              (run_with_transaction)
    - PDF download & extraction helpers
    - Medical text chunking for ChromaDB
    - Structured logging to scraper_logs
    """

    def __init__(self, source_name):
        self.source_name = source_name
        self.db = DatabaseManager()
        self.normalizer = DataNormalizer()
        self.logger = logging.getLogger(f"scraper.{source_name}")
        self.headers = {"User-Agent": USER_AGENT}
        self._playwright_ready = True

        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # ── Duplicate check (legacy) ─────────────────────────────────────────────

    def is_already_scraped(self, url, table="source_urls"):
        return self.db.is_url_scraped(url, table)

    # ── Change Detection ─────────────────────────────────────────────────────

    def fetch_with_cache(self, url, force=False):
        """
        Fetch *url* with ETag / Last-Modified caching.

        Returns (response_text, changed: bool).
        Returns (None, False) if the server returned 304 Not Modified.
        On error returns (None, False).
        """
        headers = dict(self.headers)

        if not force:
            cached = self.db.get_url_cache(url)
            if cached:
                if cached.get("etag"):
                    headers["If-None-Match"] = cached["etag"]
                if cached.get("last_modified"):
                    headers["If-Modified-Since"] = cached["last_modified"]

        try:
            time.sleep(RATE_LIMIT_DELAY)
            resp = self.session.get(url, headers=headers, timeout=30, verify=False)

            if resp.status_code == 304:
                self.logger.debug("304 Not Modified: %s", url)
                return None, False

            resp.raise_for_status()

            # Cross-source de-dup: if the normalized content is identical to something
            # we've already ingested from any URL/source, skip processing it again.
            try:
                text = resp.text or ""
                normalized = " ".join(text.split())
                if normalized:
                    h = hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()
                    if self.db.is_content_fingerprint_seen(h):
                        # Still update URL cache so we don't keep refetching aggressively.
                        self.db.update_url_cache(
                            url,
                            resp.headers.get("ETag"),
                            resp.headers.get("Last-Modified"),
                        )
                        return None, False
                    self.db.remember_content_fingerprint(h, source=self.source_name, sample_url=url)
            except Exception:
                # De-dup should never break scraping.
                pass

            # Update cache
            self.db.update_url_cache(
                url,
                resp.headers.get("ETag"),
                resp.headers.get("Last-Modified"),
            )
            return resp.text, True

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404):
                self.logger.info("HTTP %s for %s — trying Playwright", e.response.status_code, url)
                html = self._fetch_with_playwright(url)
                if html:
                    self.db.update_url_cache(url, None, None)
                    return html, True
            self.logger.warning("HTTP error fetching %s: %s", url, e)
            return None, False
        except Exception as e:
            self.logger.warning("Error fetching %s: %s", url, e)
            return None, False

    # ── HTML Fetching ────────────────────────────────────────────────────────

    def fetch_html(self, url, use_playwright=False):
        """Fetch raw HTML from *url*. Falls back to Playwright on error."""
        if use_playwright:
            return self._fetch_with_playwright(url)

        try:
            time.sleep(RATE_LIMIT_DELAY)
            response = self.session.get(url, headers=self.headers, timeout=30, verify=False)
            response.raise_for_status()

            if "404 - Page Not Found" in response.text or "The page you are looking for" in response.text:
                self.logger.info("Content 404 at %s — falling back to Playwright", url)
                return self._fetch_with_playwright(url)

            return response.text
        except Exception as e:
            self.logger.info("Error fetching %s: %s — falling back to Playwright", url, e)
            return self._fetch_with_playwright(url)

    def _fetch_with_playwright(self, url):
        """Render *url* in a headless Chromium browser."""
        if not self._playwright_ready:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    ignore_https_errors=True,
                )
                page = context.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            msg = str(e)
            # Common local setup issue: Playwright installed but browsers not downloaded.
            if ("playwright install" in msg.lower()) or ("executable doesn't exist" in msg.lower()):
                self._playwright_ready = False
                self.logger.warning(
                    "Playwright browsers not installed. Run `playwright install chromium` "
                    "and re-run the scraper. Disabling Playwright for this run."
                )
            self.logger.warning("Playwright error for %s: %s", url, e)
            return None

    def parse_html(self, html):
        if not html:
            return None
        return BeautifulSoup(html, "lxml")

    # ── PDF Helpers ──────────────────────────────────────────────────────────

    def extract_pdf_from_url(self, pdf_url):
        """
        Download a PDF from *pdf_url* and return extracted text.
        Uses the session with retry configuration.
        """
        try:
            time.sleep(RATE_LIMIT_DELAY)
            resp = self.session.get(pdf_url, timeout=60, verify=False)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                if "pdf" in content_type or pdf_url.lower().endswith(".pdf"):
                    return PDFParser.extract_text_from_bytes(resp.content)
        except Exception as e:
            self.logger.warning("PDF extraction failed for %s: %s", pdf_url, e)
        return None

    def extract_pdf_tables_from_url(self, pdf_url):
        """
        Download a PDF from *pdf_url* and return extracted tables.
        Each table is a list of rows (list of strings).
        """
        try:
            time.sleep(RATE_LIMIT_DELAY)
            resp = self.session.get(pdf_url, timeout=60, verify=False)
            if resp.status_code == 200:
                return PDFParser.extract_tables_from_bytes(resp.content)
        except Exception as e:
            self.logger.warning("PDF table extraction failed for %s: %s", pdf_url, e)
        return []

    # ── Medical Text Chunking for ChromaDB ───────────────────────────────────

    @staticmethod
    def chunk_medical_text(text, source_url, disease, content_type, source_name):
        """
        Split *text* into overlapping chunks on paragraph boundaries.

        Returns a list of dicts:
            [{'text': str, 'metadata': {...}}, ...]
        """
        if not text or len(text.strip()) < 50:
            return []

        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if not paragraphs:
            # Fall back to splitting on single newlines
            paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > 600 and current_chunk:
                chunks.append({
                    "text": " ".join(current_chunk),
                    "metadata": {
                        "source": source_name,
                        "disease": disease or "general",
                        "content_type": content_type or "general",
                        "url": source_url,
                        "scraped_date": date.today().isoformat(),
                    },
                })
                # Overlap: keep last paragraph
                current_chunk = [current_chunk[-1]]
                current_len = len(current_chunk[0])

            current_chunk.append(para)
            current_len += len(para)

        # Flush remaining
        if current_chunk:
            chunks.append({
                "text": " ".join(current_chunk),
                "metadata": {
                    "source": source_name,
                    "disease": disease or "general",
                    "content_type": content_type or "general",
                    "url": source_url,
                    "scraped_date": date.today().isoformat(),
                },
            })

        # Add chunk_index
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i

        return chunks

    # ── Section-based HTML Extraction ────────────────────────────────────────

    @staticmethod
    def extract_sections_from_soup(content_area):
        """
        Extract text grouped by <h2>/<h3> section headings.

        Returns a dict mapping header text (lowercased) → section text.
        Also includes 'full_text' key with the entire content.
        """
        if not content_area:
            return {}

        sections = {}
        headers = content_area.find_all(["h2", "h3"])
        for header in headers:
            header_text = header.get_text(strip=True).lower()
            section_content = []
            curr = header.find_next_sibling()
            while curr and curr.name not in ["h2", "h3"]:
                text = curr.get_text(strip=True)
                if text:
                    section_content.append(text)
                curr = curr.find_next_sibling()
            if section_content:
                sections[header_text] = "\n".join(section_content)

        sections["full_text"] = content_area.get_text(strip=True)
        return sections

    @staticmethod
    def map_section_to_content_type(header_text):
        """Map a section header to a standardised content_type string."""
        header_text = header_text.lower()
        mapping = [
            (["symptom", "sign"],                         "symptoms"),
            (["treatment", "therap", "treated", "manage"],"treatment"),
            (["prevent", "avoid", "vaccin"],              "prevention"),
            (["diagnos", "test"],                         "diagnosis"),
            (["cause", "transmiss", "spread", "how"],     "transmission"),
            (["risk", "complicat"],                       "risk_factors"),
            (["first aid", "what to do", "emergency",
              "when to see", "warning sign"],             "first_aid"),
            (["overview", "key fact", "about", "summary"],"overview"),
            (["incubation"],                              "incubation"),
            (["medication", "drug", "dosage"],            "medications"),
        ]
        for keywords, content_type in mapping:
            if any(kw in header_text for kw in keywords):
                return content_type
        return "general"

    # ── Transactional Run Wrapper ────────────────────────────────────────────

    def run_with_transaction(self):
        """
        Wraps the subclass's ``scrape()`` method in a single DB transaction.

        Subclasses should implement ``scrape()`` returning a list of dicts,
        and ``insert_record(cursor, record)`` returning True if inserted.

        All records commit together or roll back on failure.
        Logs the run to scraper_logs with full metrics.
        """
        conn = self.db.get_connection()
        start_time = datetime.now()
        records_found = 0
        records_inserted = 0
        records_skipped = 0
        records_failed = 0
        pdfs_processed = 0
        error_details = None

        try:
            results = self.scrape()  # subclass implements this
            cur = conn.cursor()

            for record in results:
                try:
                    records_found += 1
                    if record.get("_is_pdf"):
                        pdfs_processed += 1
                    inserted = self.insert_record(cur, record)
                    if inserted:
                        records_inserted += 1
                    else:
                        records_skipped += 1
                except Exception as e:
                    records_failed += 1
                    self.logger.warning("Failed to insert record: %s", e)

            conn.commit()
            self.logger.info(
                "Committed %d records (%d inserted, %d skipped, %d failed)",
                records_found, records_inserted, records_skipped, records_failed,
            )
        except Exception as e:
            conn.rollback()
            error_details = str(e)
            self.logger.error("Transaction rolled back: %s", e)
        finally:
            end_time = datetime.now()
            self.log_run(
                scrape_type="auto",
                status="success" if error_details is None else "error",
                found=records_found,
                inserted=records_inserted,
                updated=0,
                skipped=records_skipped,
                error=error_details,
                started_at=start_time,
                completed_at=end_time,
                records_failed=records_failed,
                pdfs_processed=pdfs_processed,
            )
            self.db.put_connection(conn)

    def scrape(self):
        """
        Override in subclass. Return a list of record dicts.
        Used by ``run_with_transaction()``.
        """
        raise NotImplementedError

    def insert_record(self, cursor, record):
        """
        Override in subclass. Insert a single record using *cursor*.
        Return True if inserted, False if skipped.
        Used by ``run_with_transaction()``.
        """
        raise NotImplementedError

    # ── Standard run() ───────────────────────────────────────────────────────

    def run(self):
        """To be implemented by subclasses (legacy entry point)."""
        raise NotImplementedError

    # ── Logging ──────────────────────────────────────────────────────────────

    def log_run(self, scrape_type, status, found=0, inserted=0, updated=0,
                skipped=0, error=None, started_at=None, completed_at=None,
                records_failed=0, pdfs_processed=0):
        log_data = {
            "source_name": self.source_name,
            "scrape_type": scrape_type,
            "status": status,
            "records_found": found,
            "records_inserted": inserted,
            "records_updated": updated,
            "records_skipped": skipped,
            "error_message": error,
            "started_at": started_at,
            "completed_at": completed_at,
        }
        # Include extended fields if the DB supports them
        if records_failed or pdfs_processed or (error and len(str(error)) > 200):
            log_data["records_failed"] = records_failed
            log_data["pdfs_processed"] = pdfs_processed
            if error:
                log_data["error_details"] = str(error)[:5000]
        self.db.log_scraper_run(log_data)
