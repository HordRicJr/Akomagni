"""ML-backed intent router (local inference) with heuristic fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from akomagni.flow.intent import RouteDecision, classify_message

_AGENT_SKILL_MAP: dict[str, tuple[str, str]] = {
    "bmad-agent-dev": ("bmad-agent-dev", "bmad-build"),
    "bmad-agent-analyst": ("bmad-agent-analyst", "bmad-brainstorming"),
    "bmad-agent-architect": ("bmad-agent-architect", "bmad-architecture"),
    "bmad-agent-pm": ("bmad-agent-pm", "bmad-prd"),
    "bmad-agent-ux-designer": ("bmad-agent-ux-designer", "bmad-ux"),
    "bmad-tea": ("bmad-tea", "bmad-testarch-automate"),
    "gds-agent-game-designer": ("gds-agent-game-designer", "gds-gdd"),
    "gds-agent-game-dev": ("gds-agent-game-dev", "gds-quick-dev"),
    "bmad-cis-agent-storyteller": ("bmad-cis-agent-storyteller", "bmad-cis-storytelling"),
    "akomagni": ("akomagni", "chat"),
}

_CLASSIFY_PROMPT = """You classify user messages for Akomagni Flow.
Reply with ONLY valid JSON: {{"agent_id": "<id>", "confidence": 0.0-1.0, "reason": "<short>"}}
Valid agent_id values: {agents}
Message: {message}
"""


def _parse_ml_response(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "agent_id" not in data:
        return None
    return data


def _decision_from_ml(data: dict[str, Any], message: str) -> RouteDecision | None:
    agent_id = str(data.get("agent_id", "")).strip()
    if agent_id not in _AGENT_SKILL_MAP:
        return None
    skill_agent, skill = _AGENT_SKILL_MAP[agent_id]
    confidence = float(data.get("confidence", 0.75))
    confidence = max(0.0, min(1.0, confidence))
    reason = str(data.get("reason", "ML router classification"))
    from akomagni.flow.intent import _badge

    return RouteDecision(
        agent_id=skill_agent,
        skill=skill,
        confidence=confidence,
        badge=_badge(skill_agent, skill.split("-")[-1].title()),
        hint=f"ML router: {reason}",
    )


def classify_via_ml(
    message: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
    greenfield: bool = False,
) -> RouteDecision | None:
    """Classify using local inference API; returns None when unavailable."""
    try:
        from akomagni.inference.client import InferenceClientError, chat_completion, check_health
    except ImportError:
        return None

    status = check_health(host=host, port=port)
    if not status.online:
        return None

    agents = ", ".join(sorted(_AGENT_SKILL_MAP))
    prompt = _CLASSIFY_PROMPT.format(agents=agents, message=message.strip())
    try:
        raw = chat_completion(
            prompt,
            host=host,
            port=port,
            model=model,
            system="You are a routing classifier. Output JSON only.",
        )
    except InferenceClientError:
        return None

    data = _parse_ml_response(raw)
    if not data:
        return None
    decision = _decision_from_ml(data, message)
    if decision and greenfield and decision.skill != "bmad-brainstorming":
        return classify_message(message, greenfield=True)
    return decision


def classify_with_router(
    message: str,
    *,
    mode: str = "auto",
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
    greenfield: bool = False,
) -> RouteDecision:
    """Route via ML, heuristic, or auto (ML when inference online)."""
    normalized = (mode or "auto").strip().lower()
    if normalized == "heuristic":
        return classify_message(message, greenfield=greenfield)

    ml_decision: RouteDecision | None = None
    if normalized in {"ml", "auto"}:
        ml_decision = classify_via_ml(
            message,
            host=host,
            port=port,
            model=model,
            greenfield=greenfield,
        )
    if ml_decision is not None:
        return ml_decision
    return classify_message(message, greenfield=greenfield)
