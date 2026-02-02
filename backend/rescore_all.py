import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
CACHE_DIR = BASE_DIR / "data" / "cache" / "llm_sentiment"


RESET_FIELDS = [
    "sentiment_by_country",
    "sentiment_error",
    "llm_version",
    "llm_perspective",
    "llm_attempted_at",
    "processed_at",
]


def reset_articles() -> int:
    reset = 0

    for path in ARTICLES_DIR.rglob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            article = json.load(f)

        for field in RESET_FIELDS:
            article.pop(field, None)

        article["countries_detected"] = []
        article["countries_scored"] = []

        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

        reset += 1

    return reset


def clear_cache() -> int:
    deleted = 0
    if not CACHE_DIR.exists():
        return deleted

    for path in CACHE_DIR.rglob("*.json"):
        path.unlink()
        deleted += 1

    return deleted


def main():
    reset = reset_articles()
    deleted = clear_cache()
    print(f"Reset {reset} articles for full rescore.")
    print(f"Cleared {deleted} cached sentiment entries.")


if __name__ == "__main__":
    main()
