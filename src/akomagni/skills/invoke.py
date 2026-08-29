"""Build BMAD skill activation sessions for Akomagni Flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from akomagni.core.project import find_project_root
from akomagni.flow.intent import RouteDecision
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import record_invocation
from akomagni.memory.inject import load_central_context, load_project_context
from akomagni.skills.discovery import SkillInfo, find_skill


@dataclass(frozen=True)
class InvokeResult:
    decision: RouteDecision
    session_path: Path
    skill: SkillInfo | None
    project_root: Path | None


def _agent_skill_path(agent_id: str, project_root: Path | None) -> Path | None:
    agent_skill = find_skill(agent_id, project_root)
    return agent_skill.path if agent_skill else None


def _build_session_markdown(
    *,
    message: str,
    decision: RouteDecision,
    skill: SkillInfo | None,
    agent_path: Path | None,
) -> str:
    central = load_central_context()
    project = load_project_context()
    lines = [
        "# Akomagni Flow session",
        "",
        f"- **Agent:** {decision.badge} (`{decision.agent_id}`)",
        f"- **Skill:** `{decision.skill}`",
        f"- **Confidence:** {decision.confidence:.0%}",
        f"- **Created:** {datetime.now(UTC).isoformat()}",
        "",
        "## User message",
        "",
        message.strip(),
        "",
    ]
    if skill:
        lines.extend(
            [
                "## Skill",
                "",
                f"- Path: `{skill.path}`",
                f"- SKILL.md: `{skill.path / 'SKILL.md'}`",
                "",
            ]
        )
    if agent_path:
        lines.extend(
            [
                "## Agent persona",
                "",
                f"- Path: `{agent_path}`",
                f"- customize.toml: `{agent_path / 'customize.toml'}`",
                "",
            ]
        )
    if central.strip():
        lines.extend(["## Akomagni Memory (central)", "", central.strip(), ""])
    if project.strip():
        lines.extend(["## Akomagni Memory (project)", "", project.strip(), ""])
    lines.extend(
        [
            "## Activation instructions",
            "",
            "1. Open this project in Cursor (or your BMAD-capable agent).",
            f"2. Activate agent `{decision.agent_id}` and skill `{decision.skill}`.",
            "3. Paste the user message above as the first turn.",
            "4. Follow the skill's SKILL.md workflow to completion.",
            "",
            decision.hint,
            "",
        ]
    )
    return "\n".join(lines)


def invoke_skill(
    message: str,
    *,
    project_root: Path | None = None,
    skill_override: str | None = None,
) -> InvokeResult:
    """Route *message*, resolve skill paths, write session bundle."""
    root = project_root or find_project_root() or Path.cwd()
    decision = route_message(message)
    skill_id = skill_override or decision.skill
    skill = find_skill(skill_id, root) if skill_id not in ("chat", "image-pipeline") else None
    agent_path = _agent_skill_path(decision.agent_id, root)

    sessions = root / ".akomagni" / "workflow" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safe_skill = skill_id.replace("/", "-")
    session_path = sessions / f"{stamp}-{safe_skill}.md"
    session_path.write_text(
        _build_session_markdown(
            message=message,
            decision=decision,
            skill=skill,
            agent_path=agent_path,
        ),
        encoding="utf-8",
    )
    record_invocation(
        agent_id=decision.agent_id,
        skill_id=skill_id,
        session_path=session_path,
        project_root=root,
    )
    return InvokeResult(
        decision=decision,
        session_path=session_path,
        skill=skill,
        project_root=root,
    )
