import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"

reset = 0

for path in ARTICLES_DIR.rglob("*.json"):
    with open(path, "r", encoding="utf-8") as f:
        a = json.load(f)

    # Only reset legacy / pre-EU logic
    if a.get("llm_version") != "v3-eu":
        a.pop("sentiment_by_country", None)
        a.pop("sentiment", None)          # old VADER
        a.pop("sentiment_error", None)
        a.pop("processed_at", None)
        a.pop("llm_version", None)
        a.pop("llm_perspective", None)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(a, f, indent=2, ensure_ascii=False)

        reset += 1

print(f"Reset {reset} articles for reprocessing")
