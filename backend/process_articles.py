import json
from pathlib import Path
from datetime import datetime, timezone

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"

COUNTRY_KEYWORDS = {
    "DE": ["germany", "german", "berlin", "bundeswehr"],
    "FR": ["france", "french", "paris"],
    "IT": ["italy", "italian", "rome"],
    "ES": ["spain", "spanish", "madrid"],
}

EU_KEYWORDS = [
    "european union", "eu commission", "eu council",
    "eu parliament", "brussels"
]

EU_COUNTRIES = [
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU",
    "IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"
]

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def detect_countries(text: str):
    text_l = text.lower()
    detected = set()

    for iso, keywords in COUNTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                detected.add(iso)
                break

    for kw in EU_KEYWORDS:
        if kw in text_l:
            return ["EU"], EU_COUNTRIES.copy()

    return list(detected), list(detected)

def process():
    analyzer = SentimentIntensityAnalyzer()
    processed = 0

    for path in ARTICLES_DIR.rglob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            article = json.load(f)

        if article.get("processed_at"):
            continue

        text = f"{article['title']} {article['summary']}".strip()
        if len(text) < 80:
            # low-value article → skip storing sentiment/countries
            continue

        detected, scored = detect_countries(text)

        if not detected:
            # cannot attribute → ignore article
            continue

        vs = analyzer.polarity_scores(text)

        article["countries_detected"] = detected
        article["countries_scored"] = scored
        article["sentiment"] = {
            "compound": vs["compound"],
            "positive": vs["pos"],
            "neutral": vs["neu"],
            "negative": vs["neg"]
        }
        article["processed_at"] = utc_now()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

        processed += 1

    print(f"Processed {processed} articles")

if __name__ == "__main__":
    process()
