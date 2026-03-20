import os
import io
import logging
import requests
import pdfplumber
import tempfile

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF text and table extraction using pdfplumber."""

    # ── Download ─────────────────────────────────────────────────────────────

    @staticmethod
    def download_pdf(url, session=None, timeout=60):
        """
        Download a PDF from *url* and return the path to a temp file.
        If *session* is provided, uses it (benefits from retry config).
        Returns None on failure.
        """
        try:
            requester = session or requests
            response = requester.get(url, stream=True, timeout=timeout, verify=False)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.warning("Error downloading PDF from %s: %s", url, e)
            return None

    # ── Text Extraction ──────────────────────────────────────────────────────

    @staticmethod
    def extract_text(pdf_path):
        """
        Extract all text from a PDF file at *pdf_path*.
        The file is deleted after extraction.
        """
        if not pdf_path or not os.path.exists(pdf_path):
            return ""

        full_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text() or ""
                    full_text += "\n"
        except Exception as e:
            logger.warning("Error extracting text from PDF %s: %s", pdf_path, e)
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

        return full_text

    @staticmethod
    def extract_text_from_bytes(pdf_bytes):
        """
        Extract all text from raw PDF *bytes* (no temp file needed).
        """
        if not pdf_bytes:
            return ""

        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text() or ""
                    full_text += "\n"
        except Exception as e:
            logger.warning("Error extracting text from PDF bytes: %s", e)

        return full_text

    # ── Table Extraction ─────────────────────────────────────────────────────

    @staticmethod
    def extract_tables(pdf_path):
        """
        Extract all tables from a PDF file at *pdf_path*.
        Does NOT delete the file (caller may need it for text extraction too).
        """
        if not pdf_path or not os.path.exists(pdf_path):
            return []

        all_tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    all_tables.extend(tables)
        except Exception as e:
            logger.warning("Error extracting tables from PDF %s: %s", pdf_path, e)

        return all_tables

    @staticmethod
    def extract_tables_from_bytes(pdf_bytes):
        """
        Extract all tables from raw PDF *bytes*.
        """
        if not pdf_bytes:
            return []

        all_tables = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    all_tables.extend(tables)
        except Exception as e:
            logger.warning("Error extracting tables from PDF bytes: %s", e)

        return all_tables
