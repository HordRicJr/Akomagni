"""Akomagni Flow orchestrator — route messages to BMAD agents & skills."""

from __future__ import annotations

from pathlib import Path

import yaml

from akomagni.flow.intent import RouteDecision, classify_message


def _project_workflow_dir() -> Path:
    return Path.cwd() / ".akomagni" / "workflow"


def _load_workflow_state() -> dict:
    path = _project_workflow_dir() / "state.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _is_greenfield(message: str) -> bool:
    state = _load_workflow_state()
    gates = state.get("gates") or {}
    if gates.get("brainstorm") == "complete":
        return False
    brainstorm_dir = _project_workflow_dir() / "brainstorm"
    if brainstorm_dir.exists() and any(brainstorm_dir.glob("**/.memlog.md")):
        return False
    lowered = message.lower()
    signals = (
        "idée",
        "créer",
        "nouveau",
        "pivot",
        "comment faire",
        "je veux",
        "une app",
        "un projet",
    )
    return any(s in lowered for s in signals)


def route_message(message: str) -> RouteDecision:
    """Classify user message and return agent + skill decision."""
    greenfield = _is_greenfield(message)
    decision = classify_message(message, greenfield=greenfield)
    if (
        greenfield
        and decision.skill != "bmad-brainstorming"
        and decision.skill != "gds-brainstorm-game"
    ):
        # Force brainstorm gate for greenfield unless already on game brainstorm path
        from akomagni.flow.intent import classify_message as _cls

        forced = _cls(message, greenfield=True)
        if forced.greenfield:
            return forced
    return decision
