"""Akomagni Flow orchestrator — route messages to BMAD agents & skills."""

from __future__ import annotations

from pathlib import Path

from akomagni.flow.gates import apply_workflow_gates
from akomagni.flow.intent import RouteDecision
from akomagni.flow.state import load_state, workflow_dir

# Skills that must not be overridden by the greenfield brainstorm gate.
_GREENFIELD_OK = frozenset(
    {
        "bmad-brainstorming",
        "gds-brainstorm-game",
        "image-pipeline",
    }
)

# Clear intents that must not be forced into brainstorm on a fresh project.
_EXPLICIT_SKILLS = frozenset(
    {
        "bmad-build",
        "bmad-prd",
        "bmad-ux",
        "bmad-architecture",
        "bmad-testarch-automate",
        "bmad-cis-storytelling",
        "bmad-cis-innovation-strategy",
        "bmad-cis-problem-solving",
        "presentation-deck",
        "gds-quick-dev",
        "gds-gdd",
        "image-pipeline",
    }
)


def _brainstorm_already_done(project_root: Path | None = None) -> bool:
    discover = project_root is not None
    state = load_state(project_root, discover=discover)
    gates = state.get("gates") or {}
    if gates.get("brainstorm") == "complete":
        return True
    brainstorm_dir = workflow_dir(project_root, discover=discover) / "brainstorm"
    return brainstorm_dir.exists() and any(brainstorm_dir.glob("**/.memlog.md"))


def _brainstorm_in_progress(project_root: Path | None = None) -> bool:
    discover = project_root is not None
    state = load_state(project_root, discover=discover)
    return (state.get("gates") or {}).get("brainstorm") == "in_progress"


def _is_fresh_project(project_root: Path | None = None) -> bool:
    """True when this project has not started a BMAD flow yet (first prompts)."""
    if _brainstorm_already_done(project_root):
        return False
    discover = project_root is not None
    state = load_state(project_root, discover=discover)
    gates = state.get("gates") or {}
    if gates.get("brainstorm") in {"complete", "in_progress"}:
        return False
    completed = state.get("completed") or []
    return len(completed) == 0


def _has_explicit_non_greenfield_intent(message: str) -> bool:
    """True when the message already maps to a concrete skill (dev, PRD, …)."""
    from akomagni.flow.intent import classify_message

    decision = classify_message(message, greenfield=False)
    return decision.skill in _EXPLICIT_SKILLS and decision.confidence >= 0.75


def _is_greenfield(message: str, project_root: Path | None = None) -> bool:
    """Greenfield = brainstorm gate still open for this project.

    Fresh projects default to brainstorm, unless the user already asks for a
    concrete skill (implement, PRD, UX, tests, …).
    """
    if _brainstorm_already_done(project_root):
        return False

    if _has_explicit_non_greenfield_intent(message):
        return False

    if _is_fresh_project(project_root):
        return True

    lowered = message.lower()
    signals = (
        "idée",
        "idee",
        "créer",
        "creer",
        "create",
        "build a",
        "build an",
        "make a",
        "make an",
        "nouveau",
        "nouvelle",
        "new project",
        "new app",
        "pivot",
        "comment faire",
        "how do i",
        "how can i",
        "i want",
        "je veux",
        "j'aimerais",
        "j aimerais",
        "aide-moi",
        "aide moi",
        "help me",
        "une app",
        "an app",
        "a app",
        "un projet",
        "a project",
        "brainstorm",
        "idéation",
        "ideation",
    )
    return any(s in lowered for s in signals)


def route_message(message: str, project_root: Path | None = None) -> RouteDecision:
    """Classify user message and return agent + skill decision.

    While brainstorm is ``in_progress`` on the project, weak follow-ups
    (short answers, \"je valide\", \"commence\") stay on brainstorm.
    """
    from akomagni.flow.intent import classify_message as _cls

    greenfield = _is_greenfield(message, project_root=project_root)
    from akomagni.core.config import load_config

    cfg = load_config()
    router_cfg = cfg.get("router", {})
    inf = cfg.get("inference", {})
    host = str(inf.get("host", "127.0.0.1"))
    port = int(inf.get("port", 8787))
    model = router_cfg.get("model") if router_cfg.get("model") != "router" else None

    from akomagni.flow.ml_router import classify_with_router

    mode = str(router_cfg.get("mode", "auto"))
    decision = classify_with_router(
        message,
        mode=mode,
        host=host,
        port=port,
        model=model,
        greenfield=greenfield,
    )
    if greenfield and decision.skill not in _GREENFIELD_OK:
        forced = _cls(message, greenfield=True)
        if forced.greenfield:
            decision = forced
    # Sticky brainstorm across turns until the gate is complete.
    if (
        _brainstorm_in_progress(project_root)
        and decision.skill not in _GREENFIELD_OK
        and (decision.skill == "chat" or decision.confidence < 0.8)
    ):
        decision = _cls(message, greenfield=True)
    return apply_workflow_gates(decision, project_root=project_root)
