import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
COUNTRIES_DIR = BASE_DIR / "countries"

# Your SVG country IDs (includes EU + non-EU). Keep in sync with the map.
ALL_COUNTRIES = [
    "GL","IS","MA","TN","DZ","BY","JO","KZ","NO","UA","IL","SA","IQ","AZ","IR","GE","SY","TR","AM","CY",
    "CH","MD","AL","LB","AD","MC","LI","BA","MK","HR","PT","ES","BE","IT","PL","GR","FI","DE","SE","IE",
    "GB","AT","CZ","SK","HU","LT","LV","RO","BG","EE","SM","LU","FR","NL","SI","DK","RU","MT","ME","RS"
]

# Rolling window for scoring
WINDOW_DAYS = 14

# How many article cards to keep per country for UI
LATEST_PER_COUNTRY = 12

def parse_dt(s: str):
    if not s:
        return None
    try:
        # examples: "2026-01-28T11:25:14+00:00" or "...Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)

def iso_z(dt: datetime):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def compute_score(pos: int, neu: int, neg: int) -> int:
    """
    Bounded 1–100 score, stable under unlimited article volume.
    Uses:
      - net sentiment: (pos - neg)/total in [-1, 1]
      - volume bonus: log1p(total) scaled
    """
    total = pos + neu + neg
    if total == 0:
        return 50

    net = (pos - neg) / total
    vol = math.log1p(total)

    score = 50 + (30 * net) + (8 * vol)
    return int(round(clamp(score, 1, 100)))

def sentiment_label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"

def iter_articles():
    if not ARTICLES_DIR.exists():
        return
    for p in ARTICLES_DIR.rglob("*.json"):
        yield p

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def main():
    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    cutoff = now - timedelta(days=WINDOW_DAYS)

    # Aggregation buckets
    stats = {
        c: {
            "pos": 0, "neu": 0, "neg": 0,
            "latest": []  # list of article cards
        } for c in ALL_COUNTRIES
    }

    considered = 0
    skipped_unprocessed = 0
    skipped_outside_window = 0
    skipped_no_targets = 0

    for path in iter_articles():
        a = load_json(path)

        # only processed
        if not a.get("processed_at"):
            skipped_unprocessed += 1
            continue

        published = parse_dt(a.get("published_at"))
        if not published:
            # if missing/invalid, ignore (keeps scoring deterministic)
            continue

        if published < cutoff:
            skipped_outside_window += 1
            continue

        targets = a.get("countries_scored") or []
        if not targets:
            skipped_no_targets += 1
            continue

        # sentiment
        s = a.get("sentiment") or {}
        compound = float(s.get("compound", 0.0))
        label = sentiment_label(compound)

        considered += 1

        # build a lightweight card for UI
        card = {
            "id": a.get("id"),
            "title": a.get("title") or "",
            "summary": (a.get("summary_public") or a.get("summary") or ""),
            "url": a.get("url"),
            "source": a.get("source"),
            "published_at": a.get("published_at"),
            "sentiment": label,
            "compound": compound,
        }


        for c in targets:
            if c not in stats:
                continue

            if label == "positive":
                stats[c]["pos"] += 1
            elif label == "negative":
                stats[c]["neg"] += 1
            else:
                stats[c]["neu"] += 1

            stats[c]["latest"].append(card)

    # Write outputs + compute trend vs previous run
    index = {}
    last_updated = iso_z(now)

    for c in ALL_COUNTRIES:
        pos, neu, neg = stats[c]["pos"], stats[c]["neu"], stats[c]["neg"]
        total = pos + neu + neg
        score = compute_score(pos, neu, neg)

        # trend vs previous score (delta)
        prev_score = None
        cpath = COUNTRIES_DIR / f"{c}.json"
        if cpath.exists():
            try:
                prev_score = int(load_json(cpath).get("score"))
            except Exception:
                prev_score = None

        trend = "+0" if prev_score is None else f"{score - prev_score:+d}"

        # latest articles sorted by published desc and capped
        latest_sorted = sorted(
            stats[c]["latest"],
            key=lambda x: (parse_dt(x.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True
        )
        
        seen = set()
        latest = []
        for it in latest_sorted:
            aid = it.get("id")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            latest.append(it)
            if len(latest) >= LATEST_PER_COUNTRY:
                break


        out = {
            "country": c,                 # keep ISO/SVG ID; UI can map to display name
            "score": score,               # 1–100
            "trend": trend,               # "+4", "-2"
            "sources": total,             # count within WINDOW_DAYS
            "sentiment": {
                "positive": pos,
                "neutral": neu,
                "negative": neg
            },
            "latest_articles": latest,    # for UI lists
            "window_days": WINDOW_DAYS,
            "last_updated": last_updated
        }

        save_json(cpath, out)

        index[c] = {
            "score": score,
            "trend": trend,
            "sources": total,
            "last_updated": last_updated
        }

    save_json(COUNTRIES_DIR / "index.json", {"last_updated": last_updated, "window_days": WINDOW_DAYS, "countries": index})

    print(
        f"Scoring window: last {WINDOW_DAYS} days | cutoff={iso_z(cutoff)}\n"
        f"Articles considered: {considered}\n"
        f"Skipped: unprocessed={skipped_unprocessed}, outside_window={skipped_outside_window}, no_targets={skipped_no_targets}\n"
        f"Wrote: {len(ALL_COUNTRIES)} country files + index.json to {COUNTRIES_DIR}"
    )

if __name__ == "__main__":
    main()
