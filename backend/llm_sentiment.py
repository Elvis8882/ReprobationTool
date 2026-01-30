# backend/llm_sentiment.py
import json
import os
import time
from typing import Dict, List, Any
import hashlib
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "cache" / "llm_sentiment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_VERSION = "v1"  # bump if you change prompt/schema
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Pick a lightweight model. You can change this later.
# Common choices: "gemini-1.5-flash" or newer equivalents.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()

GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# Basic backoff settings for Actions environments
MAX_RETRIES = 5
INITIAL_BACKOFF_S = 1.5


def _post_gemini(payload: dict) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable")

    params = {"key": GEMINI_API_KEY}
    headers = {"Content-Type": "application/json"}

    last_err = None
    backoff = INITIAL_BACKOFF_S

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(GEMINI_ENDPOINT, params=params, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                return r.json()

            # 429 / 503: rate limiting / transient
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
                time.sleep(backoff)
                backoff *= 2
                continue

            # other errors: hard fail
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text}")

        except requests.RequestException as e:
            last_err = e
            time.sleep(backoff)
            backoff *= 2

    raise RuntimeError(f"Gemini request failed after retries: {last_err}")


def score_entity_sentiment(text: str, iso_targets: List[str]) -> Dict[str, Any]:
    """
    Returns:
      { "FR": {"label":"positive","confidence":0.8,"evidence":"..."}, ... }

    Labels: positive | negative | neutral | mixed
    """
    # Keep prompt short + explicit. We pass the ISO target list to reduce hallucination.
    targets_csv = ", ".join(iso_targets)

    # Cache key based on model + text + targets + prompt version
    h = hashlib.sha256()
    h.update(CACHE_VERSION.encode("utf-8"))
    h.update(b"\n")
    h.update(GEMINI_MODEL.encode("utf-8"))
    h.update(b"\n")
    h.update((",".join(iso_targets)).encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8", errors="ignore"))
    cache_path = CACHE_DIR / f"{h.hexdigest()}.json"
    
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, dict):
                return cached
        except Exception:
            pass

    schema_hint = {
        "sentiment_by_country": {
            "ISO2": {"label": "positive|negative|neutral|mixed", "confidence": 0.0, "evidence": "string"}
        }
    }

    prompt = (
        "You are scoring country-targeted sentiment in geopolitical/news text.\n"
        "Task: For EACH ISO2 country code in TARGETS, determine how the text portrays that country.\n"
        "Return ONLY JSON.\n\n"
        "Definitions:\n"
        "- positive: portrayed as helping, constructive, stabilizing, successful, etc.\n"
        "- negative: portrayed as obstructing, harmful, destabilizing, criticized, failing, etc.\n"
        "- neutral: merely mentioned with no clear valence.\n"
        "- mixed: both positive and negative signals present.\n\n"
        "Rules:\n"
        "- Score ONLY the provided TARGETS.\n"
        "- Do NOT infer facts not in the text.\n"
        "- Evidence must be a short phrase (<= 12 words) copied from the text.\n"
        "- Confidence must be 0..1.\n\n"
        f"TARGETS: {targets_csv}\n\n"
        f"TEXT:\n{text}\n\n"
        f"Output JSON with this shape:\n{json.dumps(schema_hint)}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # Lower temperature for consistency
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
    }

    data = _post_gemini(payload)

    # Extract the model text
    try:
        model_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response structure: {str(data)[:500]}")

    # Parse JSON strictly
    try:
        obj = json.loads(model_text)
    except json.JSONDecodeError:
        # Sometimes models wrap JSON in markdown; attempt a minimal cleanup.
        cleaned = model_text.strip()
        cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
        obj = json.loads(cleaned)

    out = obj.get("sentiment_by_country", {})
    if not isinstance(out, dict):
        raise RuntimeError("Invalid sentiment_by_country format from model")

    # Enforce only targets + normalize
    final: Dict[str, Any] = {}
    allowed = set(iso_targets)
    for iso, v in out.items():
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
        if len(ev) > 120:
            ev = ev[:120]
        final[iso] = {"label": label, "confidence": conf, "evidence": ev}

    # Ensure every target gets a value (default neutral)
    for iso in iso_targets:
        final.setdefault(iso, {"label": "neutral", "confidence": 0.0, "evidence": ""})

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False)
    except Exception:
        pass

    return final
