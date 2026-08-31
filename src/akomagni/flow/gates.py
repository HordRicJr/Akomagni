"""Workflow gate enforcement from bmad-help.csv."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from akomagni.flow.help_catalog import HelpEntry, load_help_catalog
from akomagni.flow.intent import RouteDecision
from akomagni.flow.state import load_state

# Default agent mapping for gate redirects (skill id → agent id).
SKILL_AGENT_MAP: dict[str, str] = {
    "bmad-brainstorming": "bmad-agent-analyst",
    "bmad-product-brief": "bmad-agent-analyst",
    "bmad-prd": "bmad-agent-pm",
    "bmad-ux": "bmad-agent-ux-designer",
    "bmad-architecture": "bmad-agent-architect",
    "bmad-create-epics-and-stories": "bmad-agent-pm",
    "bmad-sprint-planning": "bmad-agent-pm",
    "bmad-build": "bmad-agent-dev",
    "bmad-code-review": "bmad-agent-dev",
    "gds-brainstorm-game": "gds-agent-game-designer",
    "gds-gdd": "gds-agent-game-designer",
    "gds-quick-dev": "gds-agent-game-dev",
}


@dataclass(frozen=True)
class GateCheck:
    allowed: bool
    target_skill: str
    missing_prerequisites: tuple[str, ...]
    message: str = ""


def _is_prerequisite_met(prerequisite: str, completed: set[str]) -> bool:
    if prerequisite in completed:
        return True
    skill, _, action = prerequisite.partition(":")
    if action:
        return prerequisite in completed or skill in completed
    return skill in completed or any(item.startswith(f"{skill}:") for item in completed)


def check_skill_gates(
    skill_id: str,
    *,
    project_root: Path | None = None,
    catalog: dict[str, HelpEntry] | None = None,
) -> GateCheck:
    """Return whether *skill_id* can run given completed workflow steps."""
    entries = catalog if catalog is not None else load_help_catalog(project_root)
    entry = entries.get(skill_id)
    if not entry or not entry.preceded_by:
        return GateCheck(allowed=True, target_skill=skill_id, missing_prerequisites=())

    state = load_state(project_root)
    completed = set(state.get("completed") or [])
    missing = tuple(
        prereq for prereq in entry.preceded_by if not _is_prerequisite_met(prereq, completed)
    )
    if not missing:
        return GateCheck(allowed=True, target_skill=skill_id, missing_prerequisites=())

    message = f"Gate BMAD : compléter `{missing[0]}` avant `{skill_id}`" + (
        " (requis)" if entry.required else " (recommandé)"
    )
    if entry.required:
        return GateCheck(
            allowed=False,
            target_skill=skill_id,
            missing_prerequisites=missing,
            message=message,
        )
    return GateCheck(
        allowed=True,
        target_skill=skill_id,
        missing_prerequisites=missing,
        message=message,
    )


def agent_for_skill(skill_id: str) -> str:
    return SKILL_AGENT_MAP.get(skill_id, "bmad-agent-analyst")


def _badge_for_redirect(skill_id: str, catalog: dict[str, HelpEntry]) -> str:
    from akomagni.flow.intent import _badge

    entry = catalog.get(skill_id)
    label = entry.display_name if entry else skill_id
    return _badge(agent_for_skill(skill_id), label)


def apply_workflow_gates(
    decision: RouteDecision,
    *,
    project_root: Path | None = None,
) -> RouteDecision:
    """Redirect routing when required BMAD prerequisites are not complete."""
    catalog = load_help_catalog(project_root)
    if not catalog:
        return decision

    gate = check_skill_gates(decision.skill, project_root=project_root, catalog=catalog)
    if gate.allowed or not gate.missing_prerequisites:
        if gate.message and gate.missing_prerequisites:
            return RouteDecision(
                agent_id=decision.agent_id,
                skill=decision.skill,
                confidence=decision.confidence,
                badge=decision.badge,
                hint=f"{decision.hint} | {gate.message}",
                greenfield=decision.greenfield,
            )
        return decision

    prereq = gate.missing_prerequisites[0]
    redirect_skill = prereq.split(":")[0]
    return RouteDecision(
        agent_id=agent_for_skill(redirect_skill),
        skill=redirect_skill,
        confidence=decision.confidence,
        badge=_badge_for_redirect(redirect_skill, catalog),
        hint=gate.message,
        greenfield=decision.greenfield,
    )
