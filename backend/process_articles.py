import json
import re
from pathlib import Path
from datetime import datetime, timezone
from llm_sentiment import get_cached_sentiment, score_entity_sentiment_batch

import os

# Hard ceiling (Gemini requests/day)
DAILY_REQUEST_LIMIT = int(os.environ.get("GEMINI_DAILY_REQUEST_LIMIT", "18"))

# Keep headroom for retries / incidental calls
REQUEST_HEADROOM = int(os.environ.get("GEMINI_REQUEST_HEADROOM", "2"))

# Your batch size (same value used in llm_sentiment.py)
BATCH_MAX_ITEMS = int(os.environ.get("GEMINI_BATCH_MAX_ITEMS", "12"))

# Derived safe budget per run
MAX_REQUESTS_PER_RUN = max(1, DAILY_REQUEST_LIMIT - REQUEST_HEADROOM)
MAX_ITEMS_PER_RUN = MAX_REQUESTS_PER_RUN * BATCH_MAX_ITEMS


BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "data" / "articles"
LLM_VERSION = "v3-eu"  # bump this when you change prompt/logic
MIN_TEXT_LEN = 80

PROMO_PATTERNS = [
    r"\bpromoted content\b",
    r"\bsponsored\b",
    r"\badvertorial\b",
]

EU_MEMBERS = [
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU",
    "IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"
]

EU_PATTERNS = [
    r"\beuropean union\b",
    r"\beuropean commission\b",
    r"\beu commission\b",
    r"\beuropean council\b",
    r"\beu council\b",
    r"\beuropean parliament\b",
    r"\beu parliament\b",
]

COUNTRY_SYNONYMS = {
  "GL": ["greenland", "kalaallit nunaat"],
  "IS": ["iceland", "icelandic", "reykjavik"],
  "MA": ["morocco", "moroccan", "rabat", "casablanca"],
  "TN": ["tunisia", "tunisian", "tunis", "sfax"],
  "DZ": ["algeria", "algerian", "algiers"],
  "BY": ["belarus", "belarusian", "minsk"],
  "JO": ["jordan", "jordanian", "amman"],
  "KZ": ["kazakhstan", "kazakh", "astana", "nur-sultan", "almaty"],
  "NO": ["norway", "norwegian", "oslo"],
  "UA": ["ukraine", "ukrainian", "kyiv", "kiev", "kharkiv", "odesa", "odessa", "dnipro", "donbas"],
  "IL": ["israel", "israeli", "jerusalem", "tel aviv", "gaza", "west bank"],
  "SA": ["saudi arabia", "saudi", "riyadh", "jeddah", "neom"],
  "IQ": ["iraq", "iraqi", "baghdad", "erbil", "basra"],
  "AZ": ["azerbaijan", "azerbaijani", "baku", "nagorno-karabakh", "karabakh"],
  "IR": ["iran", "iranian", "tehran", "islamic republic of iran"],
  "GE": ["georgia", "georgian", "tbilisi"],
  "SY": ["syria", "syrian", "damascus", "aleppo"],
  "TR": ["turkey", "turkish", "ankara", "istanbul"],
  "AM": ["armenia", "armenian", "yerevan", "erevan", "nagorno-karabakh", "karabakh"],
  "CY": ["cyprus", "cypriot", "nicosia"],
  "CH": ["switzerland", "swiss", "bern", "geneva", "zurich"],
  "MD": ["moldova", "moldovan", "chisinau", "chișinău", "transnistria"],
  "AL": ["albania", "albanian", "tirana"],
  "LB": ["lebanon", "lebanese", "beirut"],
  "AD": ["andorra", "andorran"],
  "MC": ["monaco", "monegasque"],
  "LI": ["liechtenstein", "liechtensteiner"],
  "BA": ["bosnia and herzegovina", "bosnia", "herzegovina", "bosnian", "sarajevo"],
  "MK": ["north macedonia", "macedonia", "macedonian", "skopje"],
  "HR": ["croatia", "croatian", "zagreb"],
  "PT": ["portugal", "portuguese", "lisbon", "lisboa"],
  "ES": ["spain", "spanish", "madrid", "barcelona"],
  "BE": ["belgium", "belgian", "brussels", "bruxelles"],
  "IT": ["italy", "italian", "rome", "milano", "milan"],
  "PL": ["poland", "polish", "warsaw", "warszawa"],
  "GR": ["greece", "greek", "athens", "athina"],
  "FI": ["finland", "finnish", "helsinki"],
  "DE": ["germany", "german", "berlin", "bundeswehr", "bundestag"],
  "SE": ["sweden", "swedish", "stockholm"],
  "IE": ["ireland", "irish", "dublin"],
  "GB": [
    "united kingdom", "uk", "u.k", "great britain", "britain", "british",
    "england", "scotland", "wales", "northern ireland", "london", "westminster"
  ],
  "AT": ["austria", "austrian", "vienna", "wien"],
  "CZ": ["czechia", "czech republic", "czech", "prague", "praha"],
  "SK": ["slovakia", "slovak", "bratislava"],
  "HU": ["hungary", "hungarian", "budapest"],
  "LT": ["lithuania", "lithuanian", "vilnius"],
  "LV": ["latvia", "latvian", "riga"],
  "RO": ["romania", "romanian", "bucharest", "bucharesti", "bucuresti", "bucurești"],
  "BG": ["bulgaria", "bulgarian", "sofia"],
  "EE": ["estonia", "estonian", "tallinn"],
  "SM": ["san marino"],
  "LU": ["luxembourg", "luxembourger"],
  "FR": ["france", "french", "paris"],
  "NL": ["netherlands", "the netherlands", "dutch", "amsterdam", "the hague", "den haag"],
  "SI": ["slovenia", "slovenian", "ljubljana"],
  "DK": ["denmark", "danish", "copenhagen", "københavn"],
  "RU": ["russia", "russian federation", "russian", "moscow", "kremlin"],
  "MT": ["malta", "maltese", "valletta"],
  "ME": ["montenegro", "montenegrin", "podgorica"],
  "RS": ["serbia", "serbian", "belgrade", "beograd"],
}

def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def compile_country_patterns():
    """
    Compile per-country regex patterns.
    We use word boundaries where reasonable, and we special-case 'uk' / 'u.k'.
    """
    compiled = {}

    for iso, syns in COUNTRY_SYNONYMS.items():
        pats = []
        for s in syns:
            s = s.strip().lower()
            if not s:
                continue

            # special handling for very short tokens (uk, u.k)
            if s in {"uk", "u.k"}:
                # match UK / U.K. / U.K
                pats.append(r"(?<![a-z])u\.?k\.?(?![a-z])")
                continue

            # Escape regex but allow spaces; then add word-ish boundaries
            esc = re.escape(s)
            # Replace escaped spaces with \s+ to be flexible
            esc = esc.replace(r"\ ", r"\s+")
            pats.append(rf"(?<![a-z]){esc}(?![a-z])")

        if pats:
            compiled[iso] = re.compile("|".join(pats), flags=re.IGNORECASE)

    return compiled

EU_RE = re.compile("|".join(EU_PATTERNS), flags=re.IGNORECASE)
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), flags=re.IGNORECASE)
COUNTRY_RES = compile_country_patterns()

def detect(text: str):
    t = text or ""
    detected = set()

    # EU-wide tag
    eu_wide = bool(EU_RE.search(t))
    if eu_wide:
        detected.add("EU")

    # Country mentions
    for iso, rx in COUNTRY_RES.items():
        if rx.search(t):
            detected.add(iso)

    # Expand scoring:
    # - score all detected countries (your requirement #1)
    # - if EU-wide, also add EU members (even if not explicitly mentioned)
    scored = set([c for c in detected if c != "EU"])  # don't score the EU tag itself
    if eu_wide:
        scored.update(EU_MEMBERS)

    return eu_wide, sorted(detected), sorted(scored)

def process_articles():
    processed = 0
    skipped = 0
    too_short = 0
    no_country = 0
    promo_filtered = 0

    # We will:
    # 1) scan articles, build a list of items needing LLM scoring
    # 2) call Gemini in batches (score_entity_sentiment_batch)
    # 3) write back updated JSON files

    items = []          # batch items for LLM: {id, text, targets}
    item_paths = {}     # id -> Path (for writing results)
    per_item_meta = {}  # id -> dict with keys: scored (full list), detected (explicit), etc.

    for path in ARTICLES_DIR.rglob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            article = json.load(f)

        # Skip only if already processed successfully
        already_ok = (
            article.get("processed_at") is not None
            and not article.get("sentiment_error")
            and article.get("llm_version") == LLM_VERSION
            and isinstance(article.get("sentiment_by_country"), dict)
        )
        
        if already_ok:
            skipped += 1
            continue

        title = (article.get("title") or "").strip()
        summary = (
            article.get("summary_full")
            or article.get("summary")
            or article.get("summary_public")
            or ""
        ).strip()

        text = f"{title}\n{summary}".strip()

        if len(text) < MIN_TEXT_LEN:
            too_short += 1
            continue

        if PROMO_RE.search(text):
            promo_filtered += 1
            continue

        eu_wide, detected, scored = detect(text)

        if not detected and not eu_wide:
            no_country += 1
            continue

        # Persist detection results regardless of whether LLM runs
        article["countries_detected"] = detected
        article["countries_scored"] = scored

        # EU optimization:
        # Call LLM ONLY for explicitly detected countries (excluding the "EU" tag).
        # EU-expanded members will be treated as neutral unless explicitly mentioned.
        llm_targets = [c for c in detected if c != "EU"]

        # Write updated detection immediately (so you don't lose detection results on failures)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)

        # If there are explicit targets, queue for LLM scoring; otherwise mark processed neutral
        if not llm_targets:
            # No explicit countries mentioned; don't call LLM, but mark as processed under current logic.
            article["sentiment_by_country"] = {}
            article["llm_version"] = LLM_VERSION
            article["llm_perspective"] = "EU"
            article.pop("sentiment", None)
            article.pop("sentiment_error", None)
            article["processed_at"] = utc_now_iso()
            article["llm_attempted_at"] = article["processed_at"]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(article, f, indent=2, ensure_ascii=False)
            processed += 1
        
        else:
            cached = get_cached_sentiment(text, llm_targets)
            if cached is not None:
                article["sentiment_by_country"] = cached
                article["llm_version"] = LLM_VERSION
                article["llm_perspective"] = "EU"
                article.pop("sentiment", None)
                article.pop("sentiment_error", None)
                article["processed_at"] = utc_now_iso()
                article["llm_attempted_at"] = article["processed_at"]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(article, f, indent=2, ensure_ascii=False)
                processed += 1
            elif len(items) < MAX_ITEMS_PER_RUN:
                aid = article.get("id") or str(path)
                items.append({"id": aid, "text": text, "targets": llm_targets})
                item_paths[aid] = path
                per_item_meta[aid] = {"scored": scored, "detected": detected}
            else:
                # Cap hit: leave unprocessed so it will be picked up next run
                pass

    if items:
        est_requests = (len(items) + BATCH_MAX_ITEMS - 1) // BATCH_MAX_ITEMS
        print(f"LLM queue: {len(items)} items ~ {est_requests} requests (cap {MAX_REQUESTS_PER_RUN})")
    else:
        print("LLM queue: 0 items (no Gemini calls)")

    
    # Batch call to LLM for all queued items
    if items:
        try:
            results = score_entity_sentiment_batch(items)
        except Exception as e:
            for it in items:
                aid = it["id"]
                path = item_paths[aid]
                with open(path, "r", encoding="utf-8") as f:
                    article = json.load(f)

                article.pop("sentiment_by_country", None)
                article["sentiment_error"] = f"LLM batch failed: {str(e)[:480]}"
                article["llm_attempted_at"] = utc_now_iso()
                article.pop("processed_at", None)

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(article, f, indent=2, ensure_ascii=False)

            # ✅ critical: stop here so we don't overwrite the error
            return



        # Apply per-item results
        for it in items:
            aid = it["id"]
            path = item_paths[aid]
        
            with open(path, "r", encoding="utf-8") as f:
                article = json.load(f)
        
            sent_map = results.get(aid)
            is_ok = (
            isinstance(sent_map, dict)
            and bool(sent_map)
            and "sentiment_error" not in sent_map  # ✅ don't treat error payload as success
            )
                
            if is_ok:
                # ✅ Success
                article["sentiment_by_country"] = sent_map
                article["llm_version"] = LLM_VERSION
                article["llm_perspective"] = "EU"
                article.pop("sentiment", None)
                article.pop("sentiment_error", None)
        
                article["processed_at"] = utc_now_iso()
                article["llm_attempted_at"] = article["processed_at"]
                processed += 1
            else:
                # ❌ Missing/empty result => retry later
                article.pop("sentiment_by_country", None)  # or {}
                article["sentiment_error"] = "No batch result returned for this item"
                article["llm_attempted_at"] = utc_now_iso()
                article.pop("processed_at", None)          # keep retryable
                # processed += 0  (optional; it's not actually processed)
        
            with open(path, "w", encoding="utf-8") as f:
                json.dump(article, f, indent=2, ensure_ascii=False)

    print(
        f"Processed: {processed} | Skipped: {skipped} | "
        f"Too short: {too_short} | Promo filtered: {promo_filtered} | No country: {no_country}"
    )


if __name__ == "__main__":
    process_articles()
