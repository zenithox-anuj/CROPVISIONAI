"""LangGraph-style multi-agent reasoning service.

State machine (nodes):
  diagnose_refine -> severity_score -> advisory_localize -> confidence_gate
                                                       \-> escalation_decide
Confidence gate loops back once (max_retries=1) if confidence < 0.6.

We build this as a stateful graph even without the langgraph package to
keep the graph inspectable, deterministic, and testable. Each node is a
pure async function that returns state deltas + a trace record.
"""
import os
import json
import logging
import re
from typing import Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field, asdict

from emergentintegrations.llm.chat import LlmChat, UserMessage

log = logging.getLogger("cropvision.langgraph")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"


@dataclass
class AgentState:
    field_meta: dict
    raw: dict  # vision output
    disease: str = ""
    severity: str = ""
    confidence: float = 0.0
    affected_area_pct: float = 0.0
    advisory_en: str = ""
    advisory_hi: str = ""
    escalate: bool = False
    escalation_reason: str = ""
    retries: int = 0
    max_retries: int = 1
    trace: list = field(default_factory=list)


def _record(state: AgentState, node: str, payload: dict) -> None:
    state.trace.append({"node": node, "payload": payload})


def _extract_json(text: str) -> Optional[dict]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.MULTILINE)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text or "")
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


async def _call(system: str, user: str, session_id: str) -> str:
    if not EMERGENT_LLM_KEY:
        return ""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system,
        ).with_model(MODEL_PROVIDER, MODEL_NAME)
        resp = await chat.send_message(UserMessage(text=user))
        return resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
    except Exception as e:
        log.exception("LangGraph LLM call failed")
        return ""


# --------------- Nodes ---------------
async def node_diagnose_refine(state: AgentState) -> None:
    """Refine the raw disease label into a canonical name."""
    raw = state.raw
    sys = ("You are a plant pathology agent. Given raw model output, produce a refined "
           "diagnosis. Output JSON only: "
           '{"disease": "...", "confidence": 0-1, "notes": "..."}')
    payload = {"raw": raw, "crop": state.field_meta.get("crop"), "region": state.field_meta.get("region")}
    text = await _call(sys, json.dumps(payload), f"diag-{state.field_meta.get('field_id','x')}")
    parsed = _extract_json(text) or {}
    state.disease = parsed.get("disease") or raw.get("disease", "Unknown")
    state.confidence = float(parsed.get("confidence") or raw.get("confidence", 0.5))
    state.affected_area_pct = float(raw.get("affected_area_pct", 0.0))
    _record(state, "diagnose_refine", {"disease": state.disease, "confidence": state.confidence, "llm_ok": bool(text)})


async def node_severity_score(state: AgentState) -> None:
    """Compute severity from disease + affected area + confidence."""
    area = state.affected_area_pct
    if state.disease.lower() == "healthy":
        sev = "low"
    elif area >= 50 or state.disease.lower() in {"bacterial blight", "fungal wilt"}:
        sev = "critical"
    elif area >= 25:
        sev = "high"
    elif area >= 10:
        sev = "moderate"
    else:
        sev = "low"
    state.severity = sev
    _record(state, "severity_score", {"severity": sev, "area_pct": area})


async def node_advisory_localize(state: AgentState) -> None:
    """Generate localized advisory in EN + HI."""
    sys = ("You are an agronomy advisor. Produce a concise, farmer-friendly advisory in "
           "English AND Hindi. Output JSON only: "
           '{"en":"...", "hi":"..."} — each 2-4 sentences, practical steps first.')
    payload = {
        "disease": state.disease,
        "severity": state.severity,
        "affected_area_pct": state.affected_area_pct,
        "crop": state.field_meta.get("crop"),
        "region": state.field_meta.get("region"),
    }
    text = await _call(sys, json.dumps(payload), f"adv-{state.field_meta.get('field_id','x')}")
    parsed = _extract_json(text) or {}
    state.advisory_en = parsed.get("en") or _default_advisory_en(state)
    state.advisory_hi = parsed.get("hi") or _default_advisory_hi(state)
    _record(state, "advisory_localize", {"llm_ok": bool(text)})


def _default_advisory_en(s: AgentState) -> str:
    if s.disease.lower() == "healthy":
        return f"Your {s.field_meta.get('crop','crop')} looks healthy. Continue routine monitoring and irrigation."
    return (f"Detected {s.disease} at {s.severity} severity ({s.affected_area_pct:.0f}% affected). "
            "Isolate affected rows, apply recommended fungicide/biocontrol, and re-scan in 5-7 days.")


def _default_advisory_hi(s: AgentState) -> str:
    if s.disease.lower() == "healthy":
        return "आपकी फसल स्वस्थ दिख रही है। नियमित निगरानी और सिंचाई जारी रखें।"
    return (f"{s.disease} का पता चला ({s.severity} स्तर, {s.affected_area_pct:.0f}% प्रभावित). "
            "प्रभावित क्षेत्र को अलग करें, अनुशंसित उपचार लगाएं, 5-7 दिनों में पुनः जांच करें।")


async def node_confidence_gate(state: AgentState) -> str:
    """Return next node name."""
    if state.confidence < 0.6 and state.retries < state.max_retries:
        state.retries += 1
        _record(state, "confidence_gate", {"decision": "retry", "confidence": state.confidence})
        return "diagnose_refine"
    _record(state, "confidence_gate", {"decision": "proceed", "confidence": state.confidence})
    return "escalation_decide"


async def node_escalation_decide(state: AgentState) -> None:
    esc = state.severity in {"high", "critical"} or state.confidence < 0.5
    state.escalate = esc
    if esc:
        state.escalation_reason = (
            f"severity={state.severity}, confidence={state.confidence:.2f}"
        )
    _record(state, "escalation_decide", {"escalate": esc, "reason": state.escalation_reason})


# --------------- Graph runner ---------------
async def run_reasoning(field_meta: dict, raw_vision: dict) -> AgentState:
    state = AgentState(field_meta=field_meta, raw=raw_vision)
    # linear pass with one gated retry
    while True:
        await node_diagnose_refine(state)
        await node_severity_score(state)
        await node_advisory_localize(state)
        nxt = await node_confidence_gate(state)
        if nxt == "escalation_decide":
            break
    await node_escalation_decide(state)
    return state


def state_to_dict(s: AgentState) -> dict:
    return asdict(s)
