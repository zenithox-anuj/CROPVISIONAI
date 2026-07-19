"""Vision inference — real Claude Sonnet 4.5 vision via emergentintegrations.

Contract: takes base64 image + optional crop hint, returns structured JSON:
{ disease, confidence, severity, affected_area_pct, symptoms[] }

Includes a deterministic offline fallback that still produces realistic
output when the LLM call fails (e.g. missing key / network) so the pipeline
never disappears silently — the failure is logged and flagged.
"""
import os
import json
import base64
import hashlib
import logging
import re
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

log = logging.getLogger("cropvision.vision")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """You are CropVision AI's vision analyst. You look at satellite,
drone, or field-level crop imagery and detect disease/stress.
You MUST respond with ONLY a JSON object, no prose, no code fences:
{
 "disease": "<short name, e.g. 'Leaf Rust', 'Healthy', 'Nutrient Deficiency'>",
 "confidence": <float 0-1>,
 "severity": "<low|moderate|high|critical>",
 "affected_area_pct": <float 0-100>,
 "symptoms": ["<short bullet>", ...],
 "notes": "<one sentence>"
}
If the image is not crop-related, return disease='Unknown', confidence<=0.2."""

_DISEASE_POOL = [
    ("Leaf Rust", "moderate"), ("Powdery Mildew", "low"),
    ("Bacterial Blight", "high"), ("Nutrient Deficiency", "moderate"),
    ("Healthy", "low"), ("Water Stress", "moderate"),
    ("Fungal Wilt", "high"), ("Aphid Infestation", "moderate"),
]


def _fallback(image_b64: str, reason: str) -> dict:
    """Deterministic pseudo-inference from image hash — labelled as offline."""
    h = hashlib.sha256(image_b64.encode() if isinstance(image_b64, str) else image_b64).digest()
    idx = h[0] % len(_DISEASE_POOL)
    disease, sev = _DISEASE_POOL[idx]
    conf = 0.55 + (h[1] % 40) / 100.0
    area = round((h[2] % 60) + 5.0, 1)
    return {
        "disease": disease,
        "confidence": round(conf, 2),
        "severity": sev,
        "affected_area_pct": area,
        "symptoms": ["signal derived from image hash (offline fallback)"],
        "notes": f"Offline fallback used: {reason}",
        "_offline": True,
    }


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    # strip code fences if present
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(text)
    except Exception:
        pass
    # last-ditch: find outermost {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


async def analyze_crop_image(image_b64: str, crop_hint: str = "", session_id: str = "vision") -> dict:
    """Run vision inference. Returns structured dict + '_offline' flag if fallback used."""
    if not EMERGENT_LLM_KEY:
        return _fallback(image_b64, "EMERGENT_LLM_KEY missing")

    # normalize (strip data: prefix if present)
    if image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[-1]

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=SYSTEM_PROMPT,
        ).with_model(MODEL_PROVIDER, MODEL_NAME)

        img = ImageContent(image_base64=image_b64)
        prompt = f"Crop hint: {crop_hint or 'unknown'}. Analyze the image and return the JSON schema exactly."
        msg = UserMessage(text=prompt, file_contents=[img])
        resp = await chat.send_message(msg)
        text = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        parsed = _extract_json(text)
        if not parsed:
            log.warning("Vision returned unparseable output: %r", text[:200])
            return _fallback(image_b64, "unparseable LLM output")

        # normalize / clip
        parsed["confidence"] = float(max(0.0, min(1.0, parsed.get("confidence", 0.5))))
        parsed["affected_area_pct"] = float(max(0.0, min(100.0, parsed.get("affected_area_pct", 0.0))))
        parsed["severity"] = str(parsed.get("severity", "moderate")).lower()
        if parsed["severity"] not in {"low", "moderate", "high", "critical"}:
            parsed["severity"] = "moderate"
        parsed.setdefault("symptoms", [])
        parsed.setdefault("notes", "")
        parsed.setdefault("disease", "Unknown")
        parsed["_offline"] = False
        return parsed
    except Exception as e:
        log.exception("Vision call failed")
        return _fallback(image_b64, f"exception: {e.__class__.__name__}")
