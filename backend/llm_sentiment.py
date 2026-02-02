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
LOG_RAW_GEMINI = os.environ.get("LLM_SENTIMENT_LOG_RAW", "0").strip() == "1"

# Cache version (bump if you change prompt/schema)
CACHE_VERSION = os.environ.get("LLM_SENTIMENT_CACHE_VERSION", "v3-eu-1")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
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


def get_cached_sentiment(text: str, iso_targets: List[str]) -> Dict[str, Any] | None:
    cached = _cache_get(text, iso_targets)
    if cached is None:
        return None
    return _normalize_sentiment_map(cached, iso_targets)


def _call_gemini_batch(input_items: List[dict]) -> Dict[str, Any]:
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
        "You are scoring COUNTRY-TARGETED sentiment from the standpoint of the European Union (EU).\n"
        "Interpret events based on impact on EU interests: security, stability, rule of law, support for Ukraine, sanctions compliance.\n"
        "Return ONLY valid JSON. No markdown. No extra text.\n\n"

        "For each item, score ONLY the ISO2 codes in 'targets' using uppercase keys.\n"
        "Do not add extra countries.\n"
        "Note: GB = United Kingdom (UK). Mentions of UK/United Kingdom/Britain => GB.\n\n"

        "Labels: positive | negative | neutral | mixed\n"
        "- positive: portrayed as supporting EU interests/values.\n"
        "- negative: portrayed as harming EU interests/values.\n"
        "- neutral: mentioned without a clear EU-relevant implication.\n"
        "- mixed: both supportive and harmful EU-relevant signals.\n\n"

        "Key rule: Do NOT treat military or political 'success' as positive if it harms EU interests.\n"
        "Example: Russian military advances in Ukraine => negative for Russia (EU standpoint).\n"
        "If unsure, choose neutral with low confidence.\n\n"

        "Evidence: short phrase (<= 12 words) copied from the text.\n"
        "Confidence: number 0..1.\n\n"
        "You MUST return every input id exactly once in results.\n"
        "Example output:\n"
        "{\"results\":[{\"id\":\"example-1\",\"sentiment_by_country\":"
        "{\"DE\":{\"label\":\"neutral\",\"confidence\":0.2,\"evidence\":\"short quote\"}}}]}\n\n"

        f"INPUT:\n{json.dumps({'items': input_items}, ensure_ascii=False)}\n\n"
        f"Output JSON with this exact shape:\n{json.dumps(schema_hint)}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8000}, "responseMimeType": "application/json"
    }

    resp = _post_gemini(payload)
    model_text = _extract_text(resp)
    obj = _loads_json_strict(model_text)
    _validate_batch_response(obj)
    return obj


def _batch_hash(input_items: List[dict] | None) -> str:
    if not input_items:
        return "noinput"
    try:
        payload = json.dumps(input_items, ensure_ascii=False, sort_keys=True)
    except TypeError:
        payload = json.dumps(str(input_items), ensure_ascii=False, sort_keys=True)
    h = hashlib.sha256()
    h.update(payload.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:12]


def _log_raw_response(context: str, response_obj: Any, input_items: List[dict] | None = None) -> None:
    if not LOG_RAW_GEMINI:
        return
    raw_dir = CACHE_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    batch_hash = _batch_hash(input_items)
    path = raw_dir / f"{timestamp}_{batch_hash}_{context}.json"
    extracted_text = None
    try:
        extracted_text = _extract_text(response_obj)
    except Exception:
        extracted_text = None
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "context": context,
                    "timestamp": timestamp,
                    "batch_hash": batch_hash,
                    "input_ids": [item.get("id") for item in input_items or []],
                    "extracted_text": extracted_text,
                    "response": response_obj,
                },
                f,
                ensure_ascii=False,
            )
    except Exception:
        pass


def _error_payload(targets: List[str], code: str) -> Dict[str, Any]:
    neutral_map = {c: {"label": "neutral", "confidence": 0.0, "evidence": ""} for c in targets}
    neutral_map["sentiment_error"] = {"code": code}
    return neutral_map


def _make_retry_batches(pending: List[dict]) -> List[List[dict]]:
    retry_max_items = max(1, BATCH_MAX_ITEMS // 2)
    retry_max_chars = max(1000, BATCH_MAX_CHARS // 2)
    batches: List[List[dict]] = []
    cur: List[dict] = []
    cur_chars = 0

    for it in pending:
        tlen = len(it.get("text") or "")
        if cur and (len(cur) >= retry_max_items or (cur_chars + tlen) > retry_max_chars):
            batches.append(cur)
            cur = []
            cur_chars = 0

        cur.append(it)
        cur_chars += tlen

    if cur:
        batches.append(cur)

    return batches


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


def _summarize_response(obj: Any) -> Tuple[str, str]:
    if isinstance(obj, dict):
        keys = sorted([str(k) for k in obj.keys()])
        key_summary = f"keys={keys}"
    else:
        key_summary = "keys=[]"
    try:
        snippet = json.dumps(obj, ensure_ascii=False)[:400]
    except Exception:
        snippet = str(obj)[:400]
    return key_summary, snippet


def _looks_like_id_map(results: Any) -> bool:
    if not isinstance(results, dict) or not results:
        return False
    reserved = {"id", "sentiment_by_country", "sentiment", "results", "items", "data"}
    valid_keys = 0
    for key, value in results.items():
        if not isinstance(key, str) or not isinstance(value, (dict, list)):
            return False
        if key not in reserved:
            valid_keys += 1
    return valid_keys > 0


def _validate_batch_response(obj: Any) -> None:
    results = _unwrap_results_container(obj)
    if isinstance(results, list) and results:
        return
    if _looks_like_id_map(results):
        return
    key_summary, snippet = _summarize_response(obj)
    raise RuntimeError(
        "Invalid batch response structure: expected array of results or id->payload map; "
        f"{key_summary}; snippet={snippet}"
    )


def _normalize_sentiment_map(out: Any, iso_targets: List[str]) -> Dict[str, Any]:
    """
    Enforce:
      {ISO2: {label, confidence, evidence}}
    Ensure every iso_target exists (default neutral).
    Normalize common aliases (e.g. UK -> GB).
    """

    # --- Alias normalization ---
    ALIASES = {
        "UK": "GB",
        "U.K": "GB",
        "U.K.": "GB",
        "UNITED KINGDOM": "GB",
        "GREAT BRITAIN": "GB",
        "BRITAIN": "GB",
    }

    allowed = set(c.upper() for c in iso_targets)
    final: Dict[str, Any] = {}

    if isinstance(out, dict):
        items = out.items()
    else:
        items = []

    for iso_key, v in items:
        if not isinstance(iso_key, str):
            continue

        iso = iso_key.strip().upper()
        iso = ALIASES.get(iso, iso)  # 🔧 normalize aliases

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

        final[iso] = {
            "label": label,
            "confidence": conf,
            "evidence": ev,
        }

    # Ensure all targets exist (default neutral)
    for iso in allowed:
        final.setdefault(
            iso,
            {"label": "neutral", "confidence": 0.0, "evidence": ""},
        )

    return final


def _coerce_sentiment_payload(result: Any) -> Dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    if isinstance(result.get("sentiment_by_country"), dict):
        return result["sentiment_by_country"]
    if isinstance(result.get("sentiment"), dict):
        return result["sentiment"]

    iso_like = {}
    for key, value in result.items():
        if key == "id":
            continue
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        iso = key.strip().upper()
        if len(iso) not in (2, 3) or not iso.isalpha():
            continue
        iso_like[iso] = value

    return iso_like or None


def _unwrap_results_container(results: Any) -> Any:
    if isinstance(results, dict):
        for key in ("results", "items", "data"):
            if key in results:
                return results[key]
    return results


def _find_nested_sentiment_payload(result: Any) -> Dict[str, Any] | None:
    stack = [result]
    while stack:
        current = stack.pop()
        payload = _coerce_sentiment_payload(current)
        if payload is not None:
            return payload
        if isinstance(current, dict):
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for value in current:
                if isinstance(value, (dict, list)):
                    stack.append(value)
    return None


def _map_results_to_ids(results: Any, batch: List[dict]) -> Dict[str, Any]:
    rmap: Dict[str, Any] = {}

    results = _unwrap_results_container(results)

    if isinstance(results, dict):
        if _coerce_sentiment_payload(results) is not None or results.get("id"):
            payload = _coerce_sentiment_payload(results) or _find_nested_sentiment_payload(results)
            if payload is not None and len(batch) == 1:
                rid = str(batch[0]["id"]).strip()
                if rid:
                    rmap[rid] = payload
                    return rmap
        elif len(batch) == 1:
            payload = _find_nested_sentiment_payload(results)
            if payload is not None:
                rid = str(batch[0]["id"]).strip()
                if rid:
                    rmap[rid] = payload
                    return rmap

        for rid, payload in results.items():
            if rid is None:
                continue
            rid = str(rid).strip()
            if not rid:
                continue
            coerced = _coerce_sentiment_payload(payload)
            if coerced is None and isinstance(payload, (dict, list)):
                coerced = _find_nested_sentiment_payload(payload)
            rmap[rid] = coerced if coerced is not None else payload
        return rmap

    if not isinstance(results, list):
        return rmap

    all_have_ids = all(isinstance(r, dict) and r.get("id") for r in results)

    if all_have_ids:
        for r in results:
            rid = str(r.get("id")).strip()
            payload = _coerce_sentiment_payload(r)
            if rid and payload is not None:
                rmap[rid] = payload
        return rmap

    if len(results) == len(batch):
        for idx, r in enumerate(results):
            if not isinstance(r, dict):
                continue
            rid = r.get("id")
            if rid is None:
                rid = batch[idx]["id"]
            rid = str(rid).strip()
            payload = _coerce_sentiment_payload(r)
            if rid and payload is not None:
                rmap[rid] = payload

    return rmap



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


def _make_batches(pending: List[dict]) -> List[List[dict]]:
    batches: List[List[dict]] = []
    cur: List[dict] = []
    cur_chars = 0

    for it in pending:
        tlen = len(it.get("text") or "")
        # if single item is too large, still send it alone
        if cur and (len(cur) >= BATCH_MAX_ITEMS or (cur_chars + tlen) > BATCH_MAX_CHARS):
            batches.append(cur)
            cur = []
            cur_chars = 0

        cur.append(it)
        cur_chars += tlen

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
        input_items = [{"id": it["id"], "targets": it["targets"], "text": it["text"]} for it in batch]
    
        print(f"[llm] Sending batch: {len(batch)} items, total_chars={sum(len(x['text']) for x in batch)}")
        obj = _call_gemini_batch(input_items)
    
        results = obj.get("results", obj)
        rmap = _map_results_to_ids(results, batch)
        if not rmap:
            if LOG_RAW_GEMINI:
                print("[llm] No mappable IDs in initial batch response; logging raw payload.")
                _log_raw_response("initial_no_mappable", obj, input_items)
            raise RuntimeError("Invalid batch response: no mappable results")
    
        # Retry missing ids
        missing = [it for it in batch if it["id"] not in rmap]
        if missing:
            if LOG_RAW_GEMINI:
                print(f"[llm] Missing {len(missing)}/{len(batch)} ids in initial response; logging raw payload.")
                _log_raw_response("initial_missing_ids", obj, input_items)
            print(f"[llm] Missing {len(missing)}/{len(batch)} ids, retrying in smaller chunks...")
            retry_chunk_size = int(os.environ.get("GEMINI_RETRY_CHUNK_SIZE", "3"))
            retry_batches = _make_retry_batches(missing)

            for chunk in retry_batches:
                for i in range(0, len(chunk), retry_chunk_size):
                    subchunk = chunk[i:i + retry_chunk_size]
                    retry_input = [{"id": x["id"], "targets": x["targets"], "text": x["text"]} for x in subchunk]

                    time.sleep(float(os.environ.get("GEMINI_THROTTLE_S", "0.6")))
                    robj = _call_gemini_batch(retry_input)
                    _log_raw_response("retry_batch", robj, retry_input)

                    rresults = robj.get("results", [])
                    rmap.update(_map_results_to_ids(rresults, subchunk))
    
        # Final fallback: single-item calls for any remaining missing
        still_missing = [it for it in batch if it["id"] not in rmap]
        for it in still_missing:
            aid = it["id"]
            try:
                time.sleep(float(os.environ.get("GEMINI_THROTTLE_S", "0.6")))
                sobj = _call_gemini_batch(
                    [{"id": it["id"], "targets": it["targets"], "text": it["text"]}]
                )
                _log_raw_response(f"single_{aid}", sobj, [{"id": it["id"], "targets": it["targets"], "text": it["text"]}])
                sresults = sobj.get("results", [])
                rmap.update(_map_results_to_ids(sresults, [it]))
            except Exception:
                out[aid] = _error_payload(it["targets"], "gemini_single_failure")

        # Write outputs + cache (only cache if returned)
        for it in batch:
            aid = it["id"]
            targets = it["targets"]
            text = it["text"]

            if aid in rmap:
                sent_map_raw = rmap.get(aid, {})
                normalized = _normalize_sentiment_map(sent_map_raw, targets)
                out[aid] = normalized
                _cache_set(text, targets, normalized)
            else:
                out.setdefault(aid, _error_payload(targets, "gemini_missing_id"))
    
        time.sleep(float(os.environ.get("GEMINI_THROTTLE_S", "0.6")))


    return out
