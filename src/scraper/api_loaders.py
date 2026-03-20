"""
APIDataLoader
-------------
This module is referenced by `scraper/main.py` and `scraper/enrich_diseases.py`.

Historically, it was intended to pull from pure APIs (WHO GHO, CDC APIs, etc.).
In this codebase, we already have a mixture of:
- direct API scrapers (OpenFDA, RxNav)
- HTML scrapers (WHO/CDC/MedlinePlus/Mayo/NHS/Cleveland/MoHFW/NCDC/ICMR, etc.)

To keep the architecture consistent and avoid breaking the scheduler, this loader
acts as a thin router that runs the right collector(s) based on `mode`.
"""

from datetime import datetime


class APIDataLoader:
    def __init__(self):
        self.started_at = None

    def run(self, mode: str = "all"):
        """
        Run one or more collectors.

        Supported modes (used by `scraper/main.py` registry):
        - all
        - who
        - cdc
        - medline
        - medicines
        - rare
        """
        self.started_at = datetime.now()
        mode = (mode or "all").lower().strip()

        runners = []

        # Import lazily so the loader can be imported even if optional deps are missing.
        def _safe_import(module_path: str, cls_name: str):
            import importlib
            try:
                mod = importlib.import_module(module_path)
                return getattr(mod, cls_name)
            except Exception:
                return None

        # Core/global health sources
        WHOScraper = _safe_import("scrapers.who_scraper", "WHOScraper")
        CDCScraper = _safe_import("scrapers.cdc_scraper", "CDCScraper")

        # Indian sources
        MoHFWScraper = _safe_import("scrapers.mohfw_scraper", "MoHFWScraper")
        NCDCScraper = _safe_import("scrapers.ncdc_scraper", "NCDCScraper")
        ICMRScraper = _safe_import("scrapers.icmr_scraper", "ICMRScraper")
        NHMScraper = _safe_import("scrapers.nhm_scraper", "NHMScraper")
        IDSPScraper = _safe_import("scrapers.idsp_scraper", "IDSPScraper")
        PIBScraper = _safe_import("scrapers.pib_scraper", "PIBScraper")

        # Guidelines & broad condition coverage
        MedlineScraper = _safe_import("scrapers.medline_scraper", "MedlineScraper")
        MayoClinicScraper = _safe_import("scrapers.mayo_scraper", "MayoClinicScraper")
        NHSScraper = _safe_import("scrapers.nhs_scraper", "NHSScraper")
        ClevelandClinicScraper = _safe_import("scrapers.cleveland_scraper", "ClevelandClinicScraper")

        # Medicines
        OpenFDAScraper = _safe_import("scrapers.openfda_scraper", "OpenFDAScraper")
        RxNavScraper = _safe_import("scrapers.rxnav_scraper", "RxNavScraper")
        DrugsScraper = _safe_import("scrapers.drugs_scraper", "DrugsScraper")

        # Rare/genetic
        RareDiseasesScraper = _safe_import("scrapers.rare_diseases_scraper", "RareDiseasesScraper")

        if mode in ("all", "who"):
            for cls in (WHOScraper,):
                if cls:
                    runners.append(cls)

        if mode in ("all", "cdc"):
            for cls in (CDCScraper,):
                if cls:
                    runners.append(cls)

        if mode in ("all", "india"):
            for cls in (MoHFWScraper, NCDCScraper, ICMRScraper, NHMScraper, IDSPScraper, PIBScraper):
                if cls:
                    runners.append(cls)

        if mode in ("all", "medline", "guidelines"):
            for cls in (MedlineScraper, MayoClinicScraper, NHSScraper, ClevelandClinicScraper):
                if cls:
                    runners.append(cls)

        if mode in ("all", "medicines"):
            for cls in (OpenFDAScraper, RxNavScraper, DrugsScraper):
                if cls:
                    runners.append(cls)

        if mode in ("all", "rare"):
            for cls in (RareDiseasesScraper,):
                if cls:
                    runners.append(cls)

        # De-dup while preserving order
        seen = set()
        uniq = []
        for cls in runners:
            key = f"{cls.__module__}.{cls.__name__}"
            if key not in seen:
                seen.add(key)
                uniq.append(cls)

        for cls in uniq:
            scraper = cls()
            scraper.run()


# ── Thin wrappers for scheduler registry ─────────────────────────────────────
# `scraper/main.py` instantiates scrapers without args and calls `.run()`.
# These wrappers allow the registry to run distinct "modes" without changing
# the orchestrator.

class WHOOutbreaksLoader(APIDataLoader):
    def run(self):  # type: ignore[override]
        super().run(mode="who")


class WHOGHOLoader(APIDataLoader):
    def run(self):  # type: ignore[override]
        # We don't currently have a dedicated GHO-only collector; reuse WHO.
        super().run(mode="who")


class MedlinePlusLoader(APIDataLoader):
    def run(self):  # type: ignore[override]
        super().run(mode="medline")


class NIHICDLoader(APIDataLoader):
    def run(self):  # type: ignore[override]
        # Placeholder hook for future ICD/terminology importers.
        super().run(mode="all")


class CDCAPILoader(APIDataLoader):
    def run(self):  # type: ignore[override]
        super().run(mode="cdc")

