# backend/llm_sentiment.py
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


# ---- Config ----
MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "10"))
INITIAL_BACKOFF_S = float(os.environ.get("GEMINI_INITIAL_BACKOFF_S", "2.0"))
MAX_BACKOFF_S = float(os.environ.get("GEMINI_MAX_BACKOFF_S", "60"))

# Batch sizing: we cap total chars per request to avoid huge prompts
BATCH_MAX_ITEMS = int(os.environ.get("GEMINI_BATCH_MAX_ITEMS", "12"))
BATCH_MAX_CHARS = int(os.environ.get("GEMINI_BATCH_MAX_CHARS", "18000"))

# Cache version (bump if you change prompt/schema)
CACHE_VERSION = os.environ.get("LLM_SENTIMENT_CACHE_VERSION", "v2")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip()
if not GEMINI_MODEL.startswith("models/"):
    GEMINI_MODEL = f"models/{GEMINI_MODEL}"

def _endpoint() -> str:
    if not GEMINI_MODEL:
        raise RuntimeError("Missing GEMINI_MODEL environment variable (expected like 'models/...').")
    # Use v1 endpoint and include full models/... path
    return f"https://generativelanguage.googleapis.com/v1beta/{GEMINI_MODEL}:generateContent"

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "cache" / "llm_sentiment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(text: str, iso_targets: List[str]) -> str:
    h = hashlib.sha256()
    h.update(CACHE_VERSION.encode("utf-8"))
    h.update(b"\n")
    h.update(GEMINI_MODEL.encode("utf-8"))
    h.update(b"\n")
    h.update((",".join([c.upper() for c in iso_targets])).encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _cache_get(text: str, iso_targets: List[str]) -> Dict[str, Any] | None:
    key = _cache_key(text, iso_targets)
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _cache_set(text: str, iso_targets: List[str], value: Dict[str, Any]) -> None:
    key = _cache_key(text, iso_targets)
    path = CACHE_DIR / f"{key}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
    except Exception:
        pass


def _post_gemini(payload: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable")

    url = _endpoint()
    params = {"key": api_key}
    headers = {"Content-Type": "application/json"}

    last_err: Exception | None = None
    backoff = INITIAL_BACKOFF_S

    for _attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(url, params=params, headers=headers, json=payload, timeout=90)

            if r.status_code == 200:
                return r.json()

            if r.status_code in (429, 500, 502, 503, 504):
                retry_after = r.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_s = float(retry_after)
                    except Exception:
                        sleep_s = backoff
                else:
                    sleep_s = backoff

                # jitter
                sleep_s *= (0.7 + random.random() * 0.6)
                sleep_s = min(sleep_s, MAX_BACKOFF_S)

                last_err = RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
                time.sleep(sleep_s)
                backoff = min(backoff * 2, MAX_BACKOFF_S)
                continue

            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:2000]}")

        except requests.RequestException as e:
            last_err = e
            sleep_s = min(backoff * (0.7 + random.random() * 0.6), MAX_BACKOFF_S)
            time.sleep(sleep_s)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    raise RuntimeError(f"Gemini request failed after retries: {last_err}")


def _extract_text(resp: dict) -> str:
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response structure: {str(resp)[:800]}")


def _loads_json_strict(s: str) -> dict:
    # Allow rare ```json wrappers
    cleaned = s.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return json.loads(cleaned)


def _normalize_sentiment_map(out: Any, iso_targets: List[str]) -> Dict[str, Any]:
    """
    Enforce:
      {ISO2: {label, confidence, evidence}}
    Ensure every iso_target exists (default neutral).
    """
    allowed = set([c.upper() for c in iso_targets])
    final: Dict[str, Any] = {}

    if isinstance(out, dict):
        items = out.items()
    else:
        items = []

    for iso_key, v in items:
        if not isinstance(iso_key, str):
            continue
        iso = iso_key.strip().upper()
        if iso not in allowed:
            continue
        if not isinstance(v, dict):
            continue

        label = str(v.get("label", "neutral")).lower().strip()
        if label not in {"positive", "negative", "neutral", "mixed"}:
            label = "neutral"

        conf = v.get("confidence", 0.5)
        try:
            conf = float(conf)
        except Exception:
            conf = 0.5
        conf = max(0.0, min(1.0, conf))

        ev = str(v.get("evidence", "")).strip()
        if len(ev) > 140:
            ev = ev[:140]

        final[iso] = {"label": label, "confidence": conf, "evidence": ev}

    for iso in allowed:
        final.setdefault(iso, {"label": "neutral", "confidence": 0.0, "evidence": ""})

    return final


def score_entity_sentiment(text: str, iso_targets: List[str]) -> Dict[str, Any]:
    # Single-item convenience wrapper
    cached = _cache_get(text, iso_targets)
    if cached is not None:
        return cached

    items = [{"id": "single", "text": text, "targets": iso_targets}]
    results = score_entity_sentiment_batch(items)
    out = results.get("single", {c.upper(): {"label": "neutral", "confidence": 0.0, "evidence": ""} for c in iso_targets})

    _cache_set(text, iso_targets, out)
    return out


def _make_batches(items: List[dict]) -> List[List[dict]]:
    batches: List[List[dict]] = []
    cur: List[dict] = []
    cur_chars = 0

    for it in items:
        t = it.get("text") or ""
        # rough char cost: text + targets + overhead
        it_cost = len(t) + 100 + 4 * len(it.get("targets") or [])
        if cur and (len(cur) >= BATCH_MAX_ITEMS or (cur_chars + it_cost) > BATCH_MAX_CHARS):
            batches.append(cur)
            cur = []
            cur_chars = 0
        cur.append(it)
        cur_chars += it_cost

    if cur:
        batches.append(cur)

    return batches


def score_entity_sentiment_batch(items: List[dict]) -> Dict[str, Dict[str, Any]]:
    """
    items: [{id, text, targets}]
    returns dict: {id -> sentiment_by_country}
    Uses per-item cache; only calls Gemini for uncached items.
    """
    # First resolve cache hits
    out: Dict[str, Dict[str, Any]] = {}
    pending: List[dict] = []

    for it in items:
        aid = str(it.get("id"))
        text = str(it.get("text") or "")
        targets = [str(x).upper() for x in (it.get("targets") or [])]

        if not targets:
            out[aid] = {}
            continue

        cached = _cache_get(text, targets)
        if cached is not None:
            out[aid] = cached
        else:
            pending.append({"id": aid, "text": text, "targets": targets})

    if not pending:
        return out

    # Batch the pending calls
    for batch in _make_batches(pending):
        # Build compact input
        input_items = []
        for it in batch:
            input_items.append({
                "id": it["id"],
                "targets": it["targets"],
                "text": it["text"],
            })

        schema_hint = {
            "results": [
                {
                    "id": "string",
                    "sentiment_by_country": {
                        "ISO2": {"label": "positive|negative|neutral|mixed", "confidence": 0.0, "evidence": "string"}
                    }
                }
            ]
        }

        prompt = (
            "You are scoring COUNTRY-TARGETED sentiment in geopolitical/news text.\n"
            "Return ONLY valid JSON. No markdown. No extra text.\n\n"
            "For each item, score ONLY the ISO2 codes in 'targets' (uppercase keys).\n"
            "Do not add extra countries.\n\n"
            "Labels: positive | negative | neutral | mixed\n"
            "- positive: helping/constructive/stabilizing/successful\n"
            "- negative: obstructing/harmful/destabilizing/criticized/failing\n"
            "- neutral: mentioned without clear judgment\n"
            "- mixed: both positive and negative signals\n\n"
            "Evidence: short phrase (<= 12 words) copied from the text.\n"
            "Confidence: number 0..1.\n\n"
            f"INPUT:\n{json.dumps({'items': input_items}, ensure_ascii=False)}\n\n"
            f"Output JSON with this exact shape:\n{json.dumps(schema_hint)}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
        }

        resp = _post_gemini(payload)
        model_text = _extract_text(resp)
        obj = _loads_json_strict(model_text)

        results = obj.get("results", [])
        if not isinstance(results, list):
            raise RuntimeError("Invalid batch response: 'results' is not a list")

        # index results by id
        rmap: Dict[str, Any] = {}
        for r in results:
            if not isinstance(r, dict):
                continue
            rid = r.get("id")
            if isinstance(rid, str):
                rmap[rid] = r.get("sentiment_by_country")

        # Write outputs + cache; default neutrals for missing ids
        for it in batch:
            aid = it["id"]
            targets = it["targets"]
            text = it["text"]

            sent_map_raw = rmap.get(aid, {})
            normalized = _normalize_sentiment_map(sent_map_raw, targets)
            out[aid] = normalized
            _cache_set(text, targets, normalized)

        # small throttle between batch requests (helps 429)
        time.sleep(float(os.environ.get("GEMINI_THROTTLE_S", "0.6")))

    return out
