import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"

MAX_AGE_DAYS = 180

def parse_dt(s: str):
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    deleted = 0
    kept = 0

    for p in ARTICLES_DIR.rglob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                a = json.load(f)
            published = parse_dt(a.get("published_at"))
            if published and published < cutoff:
                p.unlink()
                deleted += 1
            else:
                kept += 1
        except Exception:
            # If corrupt, delete (or change to "skip" if you prefer)
            p.unlink(missing_ok=True)
            deleted += 1

    print(f"Cleanup complete. Deleted={deleted}, Kept={kept}, Cutoff={cutoff.isoformat()}")

if __name__ == "__main__":
    main()
