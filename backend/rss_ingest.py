import feedparser
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
FEEDS_FILE = BASE_DIR / "data" / "feeds.yaml"


def make_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def parse_date(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def load_feeds():
    with open(FEEDS_FILE, "r") as f:
        return yaml.safe_load(f)["feeds"]


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
        parsed = feedparser.parse(feed["url"])

        for entry in parsed.entries:
            if not entry.get("link"):
                continue

            published = parse_date(entry)

            article = {
                "id": make_id(entry.link),
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "").strip()[:500],
                "url": entry.link,
                "published_at": published.isoformat(),
                "source": feed["source"],
                "language": feed["language"],
                "countries_detected": [],
                "countries_scored": [],
                "sentiment": {},
                "processed_at": None
            }

            if save_article(article):
                stored += 1

    print(f"Stored {stored} new articles")


if __name__ == "__main__":
    ingest()
