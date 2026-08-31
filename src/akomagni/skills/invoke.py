"""Build BMAD skill activation sessions for Akomagni Flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from akomagni.core.config import load_config
from akomagni.core.project import find_project_root
from akomagni.flow.intent import RouteDecision
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import record_invocation
from akomagni.memory.inject import load_central_context, load_project_context
from akomagni.rag.context import retrieve_rag_context
from akomagni.skills.discovery import SkillInfo, find_skill
from akomagni.skills.runner import SkillRunResult, run_skill_subprocess


@dataclass(frozen=True)
class InvokeResult:
    decision: RouteDecision
    session_path: Path
    skill: SkillInfo | None
    project_root: Path | None
    run_result: SkillRunResult | None = None


def _agent_skill_path(agent_id: str, project_root: Path | None) -> Path | None:
    agent_skill = find_skill(agent_id, project_root)
    return agent_skill.path if agent_skill else None


def _build_session_markdown(
    *,
    message: str,
    decision: RouteDecision,
    skill: SkillInfo | None,
    agent_path: Path | None,
    central: str,
    project: str,
    run_result: SkillRunResult | None = None,
) -> str:
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
    if run_result is not None:
        lines.extend(
            [
                "## Skill execution (uv run)",
                "",
                (
                    f"- Command: `{' '.join(run_result.command)}`"
                    if run_result.command
                    else "- Command: _none_"
                ),
                f"- Exit code: {run_result.returncode}",
            ]
        )
        if run_result.workflow_path:
            lines.extend(["", f"- Workflow: `{run_result.workflow_path}`", ""])
        if run_result.error:
            lines.extend(["", f"- Error: {run_result.error}", ""])
        if run_result.stdout.strip():
            lines.extend(["", "### stdout", "", "```", run_result.stdout.strip(), "```", ""])
    lines.extend(
        [
            "## Activation instructions",
            "",
            "1. Open this project in Cursor (or your BMAD-capable agent).",
            f"2. Activate agent `{decision.agent_id}` and skill `{decision.skill}`.",
            "3. Paste the user message above as the first turn.",
            (
                "4. Read and follow the rendered workflow file above."
                if run_result and run_result.workflow_path
                else "4. Follow the skill's SKILL.md workflow to completion."
            ),
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
    execute: bool = False,
    rag_context: str | None = None,
) -> InvokeResult:
    """Route *message*, resolve skill paths, write session bundle."""
    root = project_root or find_project_root() or Path.cwd()
    decision = route_message(message, project_root=root)
    skill_id = skill_override or decision.skill
    skill = find_skill(skill_id, root) if skill_id not in ("chat", "image-pipeline") else None
    agent_path = _agent_skill_path(decision.agent_id, root)
    central = load_central_context()
    project = load_project_context()
    rag = rag_context
    if rag is None:
        cfg = load_config()
        rag_cfg = cfg.get("rag", {})
        if rag_cfg.get("inject", True):
            rag = retrieve_rag_context(
                message,
                project=bool(rag_cfg.get("inject_project", True)),
                project_root=root,
                limit=int(rag_cfg.get("inject_limit", 3)),
                rrf_k=int(rag_cfg.get("rrf_k", 60)),
            )
        else:
            rag = ""
    else:
        rag = rag or ""

    run_result: SkillRunResult | None = None
    if execute and skill is not None:
        run_result = run_skill_subprocess(
            project_root=root,
            skill_path=skill.path,
            message=message,
            central_context=central,
            project_context=project,
            rag_context=rag,
        )

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
            central=central,
            project=project,
            run_result=run_result,
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
        run_result=run_result,
    )
