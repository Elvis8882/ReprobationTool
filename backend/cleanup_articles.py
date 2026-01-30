import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
FEEDS_FILE = BASE_DIR / "data" / "feeds.yaml"

# Delete stored articles older than this (6 months)
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


def load_allowed_sources():
    if not FEEDS_FILE.exists():
        return None  # no feed file => don't filter sources
    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    feeds = data.get("feeds") or []
    allowed = {str(x.get("source")).strip() for x in feeds if x.get("source")}
    return allowed or None


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    allowed_sources = load_allowed_sources()

    deleted_old = 0
    deleted_source = 0
    deleted_corrupt = 0
    kept = 0

    for p in ARTICLES_DIR.rglob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                a = json.load(f)

            published = parse_dt(a.get("published_at"))
            src = (a.get("source") or "").strip()

            # Rule A: delete if too old (published_at missing => keep; you can flip if you prefer strict)
            if published and published < cutoff:
                p.unlink()
                deleted_old += 1
                continue

            # Rule B: delete if source no longer in feeds.yaml
            if allowed_sources is not None and src and src not in allowed_sources:
                p.unlink()
                deleted_source += 1
                continue

            kept += 1

        except Exception:
            # corrupt JSON -> delete
            p.unlink(missing_ok=True)
            deleted_corrupt += 1

    print(
        f"Cleanup cutoff={cutoff.isoformat()}\n"
        f"Deleted: old={deleted_old}, removed_source={deleted_source}, corrupt={deleted_corrupt}\n"
        f"Kept: {kept}"
    )


if __name__ == "__main__":
    main()
