"""Build BMAD skill activation sessions for Akomagni Flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from akomagni.core.config import load_config
from akomagni.core.project import find_project_root, resolve_bmad_project_root
from akomagni.flow.intent import RouteDecision
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import record_invocation, workflow_dir
from akomagni.memory.inject import load_central_context, load_project_context
from akomagni.rag.context import retrieve_rag_context
from akomagni.skills.discovery import SkillInfo, find_skill
from akomagni.skills.runner import SkillRunResult, run_skill_subprocess

# Skills that must not fall back to free-chat code dumps in the CLI.
_IMPLEMENTATION_SKILLS = frozenset(
    {
        "bmad-build",
        "bmad-build-auto",
        "bmad-quick-dev",
        "bmad-dev-story",
        "bmad-dev-auto",
        "gds-quick-dev",
        "gds-dev-story",
        "bmad-create-story",
    }
)


def is_implementation_skill(skill_id: str) -> bool:
    """True when the skill is meant to write/edit a real codebase."""
    sid = (skill_id or "").lower()
    if sid in _IMPLEMENTATION_SKILLS:
        return True
    return any(tok in sid for tok in ("-build", "dev-story", "quick-dev", "implement"))


def prefers_session_over_free_chat(skill_id: str) -> bool:
    """BMAD workflow skills should activate in Cursor, not dump snippets in CLI chat."""
    sid = (skill_id or "").lower()
    if sid in {"chat", "image-pipeline", ""}:
        return False
    return sid.startswith(("bmad-", "gds-")) or is_implementation_skill(sid)


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
    preliminary_root = project_root or find_project_root()
    decision = route_message(message, project_root=preliminary_root)
    skill_id = skill_override or decision.skill
    skill = (
        find_skill(skill_id, preliminary_root)
        if skill_id not in ("chat", "image-pipeline")
        else None
    )
    bmad_root = resolve_bmad_project_root(
        project_root,
        skill_path=skill.path if skill else None,
    )
    if skill is None and skill_id not in ("chat", "image-pipeline"):
        skill = find_skill(skill_id, bmad_root)
    agent_path = _agent_skill_path(decision.agent_id, bmad_root)
    central = load_central_context()
    # Workflow/session storage: ambient user project or central DATA_DIR — never
    # the shipped kernel alone (skills come from the kernel; state stays local).
    storage_root = find_project_root()
    if storage_root is None and project_root is not None:
        storage_root = project_root.resolve()
    project = load_project_context(storage_root or bmad_root)
    rag = rag_context
    if rag is None:
        cfg = load_config()
        rag_cfg = cfg.get("rag", {})
        if rag_cfg.get("inject", True):
            rag = retrieve_rag_context(
                message,
                project=bool(rag_cfg.get("inject_project", True)),
                project_root=storage_root or bmad_root,
                limit=int(rag_cfg.get("inject_limit", 3)),
                rrf_k=int(rag_cfg.get("rrf_k", 60)),
            )
        else:
            rag = ""
    else:
        rag = rag or ""

    run_result: SkillRunResult | None = None
    if execute and skill is not None:
        exec_root = bmad_root or resolve_bmad_project_root(skill_path=skill.path)
        run_result = run_skill_subprocess(
            project_root=exec_root or Path.cwd(),
            skill_path=skill.path,
            message=message,
            central_context=central,
            project_context=project,
            rag_context=rag,
        )

    sessions = workflow_dir(storage_root, discover=storage_root is not None) / "sessions"
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
        project_root=storage_root,
    )
    return InvokeResult(
        decision=decision,
        session_path=session_path,
        skill=skill,
        project_root=storage_root,
        run_result=run_result,
    )
