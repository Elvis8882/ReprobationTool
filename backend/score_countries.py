import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REQUIRE_LLM_VERSION = "v3-eu"
BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
COUNTRIES_DIR = BASE_DIR / "countries"
EU_EXPANSION_WEIGHT = 0.15 
NEGATIVE_POINT_IMPACT = 1.0
POSITIVE_POINT_IMPACT = 0.5
MIXED_NEGATIVE_POINT_IMPACT = 0.12
MIXED_POSITIVE_POINT_IMPACT = 0.06

ALL_COUNTRIES = [
    "GL","IS","MA","TN","DZ","BY","JO","KZ","NO","UA","IL","SA","IQ","AZ","IR","GE","SY","TR","AM","CY",
    "CH","MD","AL","LB","AD","MC","LI","BA","MK","HR","PT","ES","BE","IT","PL","GR","FI","DE","SE","IE",
    "GB","AT","CZ","SK","HU","LT","LV","RO","BG","EE","SM","LU","FR","NL","SI","DK","RU","MT","ME","RS"
]

WINDOW_DAYS = 90
LATEST_PER_COUNTRY = 20
PROPORTIONAL_SAMPLE_THRESHOLD = 20
SMALL_SAMPLE_NEGATIVE_SCALE = 45.0
MIN_CONFIDENCE_WEIGHT = 0.10
MAX_CONFIDENCE_WEIGHT = 1.0


def parse_dt(s: str):
    if not s:
        return None
    try:
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


def parse_confidence(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def confidence_weight(confidence):
    """Map confidence (0..1) to a minimum non-zero weighting factor."""
    if confidence is None:
        return MAX_CONFIDENCE_WEIGHT

    confidence = clamp(confidence, 0.0, 1.0)
    return MIN_CONFIDENCE_WEIGHT + ((MAX_CONFIDENCE_WEIGHT - MIN_CONFIDENCE_WEIGHT) * confidence)

def compute_score(pos_impact: float, neg_impact: float, pos_count: int, neg_count: int) -> int:
    signal_count = pos_count + neg_count
    if signal_count <= 0:
        return 100

    if signal_count < PROPORTIONAL_SAMPLE_THRESHOLD:
        pos_signal = pos_impact
        neg_signal = neg_impact
        total_signal = pos_signal + neg_signal
        if total_signal <= 0:
            return 100

        neg_ratio = neg_signal / total_signal
        score = 100.0 - (SMALL_SAMPLE_NEGATIVE_SCALE * neg_ratio)
        return int(round(clamp(score, 1, 100)))

    score = 100.0 - neg_impact + pos_impact
    return int(round(clamp(score, 1, 100)))


def iter_articles():
    if not ARTICLES_DIR.exists():
        return
    yield from ARTICLES_DIR.rglob("*.json")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def label_and_assessment(total: float, pos: float, neu: float, neg: float):
    if total <= 0:
        return "Not enough data", "No information available"

    neg_ratio = neg / total
    if neg_ratio >= 0.50:
        return "Negative", "High negative coverage"
    if neg_ratio >= 0.25:
        return "Caution", "Moderate negative coverage"
    return "No Commentary", "Mostly neutral/positive coverage"


def main():
    COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    cutoff = now - timedelta(days=WINDOW_DAYS)

    stats = {
      c: {
        "pos_w": 0.0, "neg_w": 0.0,               # weighted for score
        "pos_signal_n": 0, "neg_signal_n": 0,         # signal counts for score logic
        "pos_n": 0,   "neu_n": 0,   "neg_n": 0,     # raw integer for UI
        "latest": []
      } for c in ALL_COUNTRIES
    }


    considered = 0
    skipped_unprocessed = 0
    skipped_outside_window = 0
    skipped_no_targets = 0

    for path in iter_articles():
        a = load_json(path)

        published = parse_dt(a.get("published_at"))
        if not published:
            continue

        if published < cutoff:
            skipped_outside_window += 1
            continue

        targets = a.get("countries_scored") or []
        if not targets:
            skipped_no_targets += 1
            continue
        
        hit_any = False
        for c in targets:
            if c in stats:
                hit_any = True
                break
        
        if not hit_any:
            skipped_no_targets += 1
            continue

        if a.get("llm_version") != REQUIRE_LLM_VERSION:
            skipped_unprocessed += 1
            continue

        fallback_article = False
        if not a.get("processed_at") or a.get("sentiment_error"):
            fallback_article = True

        sent_map = a.get("sentiment_by_country")
        if not isinstance(sent_map, dict):
            sent_map = {}
            fallback_article = True


        # If an article has missing LLM output but targets were scored,
        # treat as neutral to keep aggregation moving.
        considered += 1
        
        base_card = {
            "id": a.get("id"),
            "title": a.get("title") or "",
            "summary": (a.get("summary_public") or a.get("summary") or ""),
            "url": a.get("url"),
            "source": a.get("source"),
            "published_at": a.get("published_at"),
        }


        detected = set(a.get("countries_detected") or [])
        eu_wide = "EU" in detected
        
        for c in targets:
            if c not in stats:
                continue
        
            # Weighting rule unchanged
            weight = 1.0
            if eu_wide and (c not in detected) and (c != "EU"):
                weight = EU_EXPANSION_WEIGHT
        
            # Per-country label from LLM output
            c_sent = sent_map.get(c) or {}
            label = (c_sent.get("label") or "neutral").lower().strip()
            used_fallback = fallback_article or not c_sent

            if label not in ("positive", "negative", "neutral", "mixed"):
                label = "neutral"
                used_fallback = True

            confidence = parse_confidence(c_sent.get("confidence"))
            sentiment_weight = weight * confidence_weight(confidence)
            include_in_ui = confidence != 0.0
        
            # Baseline model: start from 100, then subtract/add points
            # based on sentiment impacts. Mixed has smaller impacts
            # on both sides than pure positive/negative labels.
            if label == "positive":
                stats[c]["pos_w"] += sentiment_weight * POSITIVE_POINT_IMPACT
                stats[c]["pos_signal_n"] += 1
                if include_in_ui:
                    stats[c]["pos_n"] += 1
            elif label == "negative":
                stats[c]["neg_w"] += sentiment_weight * NEGATIVE_POINT_IMPACT
                stats[c]["neg_signal_n"] += 1
                if include_in_ui:
                    stats[c]["neg_n"] += 1
            elif label == "mixed":
                stats[c]["pos_w"] += sentiment_weight * MIXED_POSITIVE_POINT_IMPACT
                stats[c]["neg_w"] += sentiment_weight * MIXED_NEGATIVE_POINT_IMPACT
                if include_in_ui:
                    stats[c]["neu_n"] += 1
            else:
                if include_in_ui:
                    stats[c]["neu_n"] += 1
        
            if include_in_ui:
                # Country-specific card (so latest_articles sentiment is correct per country)
                card_c = dict(base_card)
                card_c["sentiment"] = label
                if label == "neutral" and used_fallback:
                    card_c["sentiment_fallback"] = True
                # Optional: keep model evidence/confidence for UI/debugging
                if "confidence" in c_sent:
                    card_c["confidence"] = c_sent.get("confidence")
                if "evidence" in c_sent:
                    card_c["evidence"] = c_sent.get("evidence")
                stats[c]["latest"].append(card_c)



    index = {}
    last_updated = iso_z(now)

    for c in ALL_COUNTRIES:
        pos_w = stats[c]["pos_w"]
        neg_w = stats[c]["neg_w"]
        
        pos_signal_n = stats[c]["pos_signal_n"]
        neg_signal_n = stats[c]["neg_signal_n"]

        pos_n = stats[c]["pos_n"]
        neu_n = stats[c]["neu_n"]
        neg_n = stats[c]["neg_n"]
        
        total_w = pos_w + neg_w
        total_n = pos_n + neu_n + neg_n
        
        score = compute_score(pos_w, neg_w, pos_signal_n, neg_signal_n)

        cpath = COUNTRIES_DIR / f"{c}.json"
        prev_score = None
        if cpath.exists():
            try:
                prev_score = int(load_json(cpath).get("score"))
            except Exception:
                prev_score = None

        trend = None
        if total_w > 0 and prev_score is not None:
            trend = score - prev_score

        score_label, assessment = label_and_assessment(
            total_n, pos_n, neu_n, neg_n
        )
        sources_count = len({x.get("id") for x in stats[c]["latest"] if x.get("id")})

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
            "country": c,
            "score": score,
            "score_label": score_label,
            "assessment": assessment,
            "trend": trend,  # int or null
            "sources": sources_count,
            "sentiment": {
                "positive": pos_n,
                "neutral": neu_n,
                "negative": neg_n
            },
            "latest_articles": latest,
            "window_days": WINDOW_DAYS,
            "last_updated": last_updated,
        }

        save_json(cpath, out)

        index[c] = {
            "score": score,
            "trend": trend,
            "sources": sources_count,
            "last_updated": last_updated,
        }

    save_json(
        COUNTRIES_DIR / "index.json",
        {"last_updated": last_updated, "window_days": WINDOW_DAYS, "countries": index},
    )

    print(
        f"Scoring window: last {WINDOW_DAYS} days | cutoff={iso_z(cutoff)}\n"
        f"Articles considered: {considered}\n"
        f"Skipped: unprocessed={skipped_unprocessed}, outside_window={skipped_outside_window}, no_targets={skipped_no_targets}\n"
        f"Wrote: {len(ALL_COUNTRIES)} country files + index.json to {COUNTRIES_DIR}"
    )


if __name__ == "__main__":
    main()
