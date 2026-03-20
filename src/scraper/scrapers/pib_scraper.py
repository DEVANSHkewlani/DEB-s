"""
PIB (Press Information Bureau) Scraper — Health Ministry RSS feed
PRIORITY: MEDIUM — Daily news scraping
"""
import logging
from datetime import datetime, date

try:
    import feedparser
except ImportError:
    feedparser = None

from base_scraper import BaseScraper
from config import PIB_RSS, HEALTH_KEYWORDS, TARGET_DISEASES

logger = logging.getLogger("scraper.pib")


class PIBScraper(BaseScraper):
    def __init__(self):
        super().__init__("PIB")

    def run(self):
        started_at = datetime.now()
        found = inserted = skipped = failed = 0
        error_msg = None

        if not feedparser:
            self.logger.error("feedparser not installed. Run: pip install feedparser")
            self.log_run("education,bulletins", "error", 0, 0, 0, 0,
                         error="feedparser not installed",
                         started_at=started_at, completed_at=datetime.now())
            return

        self.logger.info("Starting PIB RSS Feed Scraping...")

        try:
            feed = feedparser.parse(PIB_RSS)

            for entry in feed.entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")

                combined = (title + " " + summary).lower()

                # Filter for health relevance
                if not any(kw in combined for kw in HEALTH_KEYWORDS):
                    continue

                if self.is_already_scraped(link, table="education_resources"):
                    skipped += 1
                    continue

                found += 1

                # Determine disease mention
                matched_disease = None
                for disease in TARGET_DISEASES:
                    if disease.lower() in combined:
                        matched_disease = disease
                        break

                pub_date = date.today()
                if published:
                    try:
                        pub_date = self.normalizer.normalize_date(published)
                    except Exception:
                        pass

                try:
                    self.db.upsert_education_resource({
                        "title": title[:200],
                        "description": self.normalizer.clean_text(summary[:500]),
                        "content": self.normalizer.clean_text(summary[:5000]),
                        "source": "PIB",
                        "source_url": link,
                        "resource_type": "press_release",
                    })

                    # Also store in bulletin_texts for LangChain
                    self.db.upsert_bulletin_text({
                        "source": "PIB",
                        "disease_mentioned": matched_disease,
                        "raw_text": f"{title}\n\n{summary}"[:50000],
                        "published_date": pub_date,
                        "url": link,
                    })

                    inserted += 1

                except Exception as e:
                    failed += 1
                    self.logger.warning("PIB entry error: %s", e)

        except Exception as e:
            error_msg = str(e)
            self.logger.error("PIB scraper error: %s", e)

        completed_at = datetime.now()
        self.log_run("education,bulletins",
                     "success" if error_msg is None else "error",
                     found, inserted, 0, skipped,
                     error=error_msg, started_at=started_at, completed_at=completed_at,
                     records_failed=failed)
