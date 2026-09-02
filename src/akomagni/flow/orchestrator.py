"""Akomagni Flow orchestrator — route messages to BMAD agents & skills."""

from __future__ import annotations

from pathlib import Path

from akomagni.flow.gates import apply_workflow_gates
from akomagni.flow.intent import RouteDecision
from akomagni.flow.state import load_state, workflow_dir


def _is_greenfield(message: str) -> bool:
    state = load_state()
    gates = state.get("gates") or {}
    if gates.get("brainstorm") == "complete":
        return False
    brainstorm_dir = workflow_dir() / "brainstorm"
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


def route_message(message: str, project_root: Path | None = None) -> RouteDecision:
    """Classify user message and return agent + skill decision."""
    greenfield = _is_greenfield(message)
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
    if (
        greenfield
        and decision.skill != "bmad-brainstorming"
        and decision.skill != "gds-brainstorm-game"
    ):
        # Force brainstorm gate for greenfield unless already on game brainstorm path
        from akomagni.flow.intent import classify_message as _cls

        forced = _cls(message, greenfield=True)
        if forced.greenfield:
            decision = forced
    return apply_workflow_gates(decision, project_root=project_root)
