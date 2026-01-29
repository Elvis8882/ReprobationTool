import json
from pathlib import Path
from datetime import datetime, timezone

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"

# --- minimal country lexicon (v1) ---
COUNTRY_KEYWORDS = {
    "DE": ["germany", "german", "bundeswehr", "berlin"],
    "FR": ["france", "french", "paris"],
    "IT": ["italy", "italian", "rome"],
    "ES": ["spain", "spanish", "madrid"],
}

EU_KEYWORDS = [
    "european union",
    "eu commission",
    "eu council",
    "eu parliament",
    "brussels"
]

EU_COUNTRIES = [
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU",
    "IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"
]

MIN_TEXT_LEN = 80


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_countries(text: str):
    t = text.lower()
    detected = set()

    # EU first (highest priority)
    for kw in EU_KEYWORDS:
        if kw in t:
            return ["EU"], EU_COUNTRIES.copy()

    # Individual countries
    for iso, keywords in COUNTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                detected.add(iso)
                break

    return list(detected), list(detected)


def process_articles():
    analyzer = SentimentIntensityAnalyzer()
    processed = 0
    skipped = 0

    for path in ARTICLES_DIR.rglob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            article = json.load(f)

        # 1️⃣ Only unprocessed
        if article.get("processed_at") is not None:
            skipped += 1
            continue

        text = f"{article.get('title','')} {article.get('summary','')}".strip()

        # 2️⃣ Quality gate
        if len(text) < MIN_TEXT_LEN:
            continue

        detected, scored = detect_countries(text)

        # 3️⃣ Must be attributable
        if not detected:
            continue

        # 4️⃣ Sentiment
        vs = analyzer.polarity_scores(text)

        article["countries_detected"] = detected
        article["countries_scored"] = scored
        article["sentiment"] = {
            "compound": vs["compound"],
            "positive": vs["pos"],
            "neutral": vs["neu"],
            "negative": vs["neg"]
        }
        article["processed_at"] = utc_now_iso()

        # 5️⃣ Write back to SAME file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

        processed += 1

    print(f"Processed: {processed}, Skipped: {skipped}")


if __name__ == "__main__":
    process_articles()
