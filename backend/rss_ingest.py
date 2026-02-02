import feedparser
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
FEEDS_FILE = BASE_DIR / "data" / "feeds.yaml"

PUBLIC_SNIPPET_LEN = 220
FULL_SUMMARY_CAP = 2000
MAX_AGE_DAYS = 180  # ~6 months


def make_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def parse_date(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def load_feeds():
    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["feeds"]


def strip_html(s: str) -> str:
    # minimal HTML tag remover (stdlib only)
    return re.sub(r"<[^>]+>", "", s or "").strip()


def make_summaries(entry) -> tuple[str, str]:
    raw = entry.get("summary") or entry.get("description") or ""
    full = strip_html(raw)
    full = full[:FULL_SUMMARY_CAP]

    if len(full) > PUBLIC_SNIPPET_LEN:
        public = full[:PUBLIC_SNIPPET_LEN].rstrip() + "…"
    else:
        public = full

    return full, public


def save_article(article: dict) -> bool:
    month = article["published_at"][:7]
    month_dir = ARTICLES_DIR / month
    month_dir.mkdir(parents=True, exist_ok=True)

    path = month_dir / f"{article['id']}.json"
    if path.exists():
        return False

    with open(path, "w", encoding="utf-8") as f:
        json.dump(article, f, indent=2, ensure_ascii=False)

    return True


def ingest():
    feeds = load_feeds()
    stored = 0

    for feed in feeds:
        print(f"Reading feed: {feed['url']}")
        parsed = feedparser.parse(
            feed["url"],
            request_headers={"User-Agent": "Mozilla/5.0 (compatible; MyRSSBot/1.0)"}
        )

        # HTTP error check
        if hasattr(parsed, "status") and parsed.status != 200:
            print(f"⚠️ Feed returned HTTP {parsed.status}, skipping")
            continue

        print(f"Found {len(parsed.entries)} entries")
        for entry in parsed.entries:
            if not entry.get("link"):
                continue

            published = parse_date(entry)
            if published < datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS):
                continue
            summary_full, summary_public = make_summaries(entry)

            article = {
                "id": make_id(entry.link),
                "title": (entry.get("title") or "").strip(),
                "summary_full": summary_full,
                "summary_public": summary_public,
                "url": entry.link,
                "published_at": published.isoformat(),
                "source": feed["source"],
                "language": feed["language"],
            
                "countries_detected": [],
                "countries_scored": [],
            
                # LLM pipeline fields
                "sentiment_by_country": None,
                "sentiment_error": None,
                "llm_version": None,
                "llm_perspective": None,
                "llm_attempted_at": None,
            
                # processing stamp (set by process_articles.py)
                "processed_at": None,
            }

            if save_article(article):
                stored += 1
                print(f"✅ Stored article: {article['title']}")
            else:
                print(f"ℹ️ Article already exists: {article['title']}")

    print(f"Stored {stored} new articles")


if __name__ == "__main__":
    ingest()
