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
    """True when the skill should drive the turn (not unstructured free chat).

    In the CLI this means: load skill guidance and continue the conversation
    with the model — do not hand off to an IDE.
    """
    sid = (skill_id or "").lower()
    if sid in {"chat", "image-pipeline", ""}:
        return False
    return sid.startswith(("bmad-", "gds-")) or is_implementation_skill(sid)


def build_skill_cli_guidance(
    skill: SkillInfo | None,
    run_result: SkillRunResult | None = None,
    *,
    max_chars: int = 12000,
) -> str:
    """Load SKILL.md (+ optional rendered workflow) for CLI-guided inference."""
    if skill is None:
        return ""
    parts: list[str] = []
    skill_md = skill.path / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[…truncated for CLI context…]"
        parts.append(f"### Skill `{skill.skill_id}` (SKILL.md)\n\n{text}")
    if run_result and run_result.workflow_path and run_result.workflow_path.is_file():
        wf = run_result.workflow_path.read_text(encoding="utf-8").strip()
        if len(wf) > max_chars:
            wf = wf[:max_chars] + "\n\n[…truncated for CLI context…]"
        parts.append(f"### Rendered workflow\n\n{wf}")
    elif run_result and run_result.stdout.strip():
        parts.append(f"### Skill render output\n\n{run_result.stdout.strip()[:max_chars]}")
    return "\n\n".join(parts)


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
            "1. Continue in the Akomagni CLI (or your agent) as this skill.",
            f"2. Follow skill `{decision.skill}` / agent `{decision.agent_id}`.",
            "3. Use the user message above as the first turn.",
            (
                "4. Read and follow the rendered workflow file above."
                if run_result and run_result.workflow_path
                else "4. Follow the skill's SKILL.md workflow to completion."
            ),
            "5. Do not invent a full project dump in one shot — collaborate step by step.",
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
    from akomagni.flow.gates import agent_for_skill
    from akomagni.flow.intent import RouteDecision, _badge, classify_message

    preliminary_root = project_root or find_project_root()
    decision = route_message(message, project_root=preliminary_root)
    # Keep an active BMAD skill across short follow-ups ("je valide", "1. …").
    if (
        skill_override
        and skill_override not in {"chat", "image-pipeline", ""}
        and (decision.skill == "chat" or decision.confidence < 0.8)
    ):
        if skill_override in {"bmad-brainstorming", "gds-brainstorm-game"}:
            decision = classify_message(
                message if skill_override == "bmad-brainstorming" else f"jeu {message}",
                greenfield=True,
            )
        else:
            agent_id = agent_for_skill(skill_override)
            decision = RouteDecision(
                agent_id=agent_id,
                skill=skill_override,
                confidence=0.9,
                badge=_badge(agent_id, skill_override),
                hint=f"Continuing active skill `{skill_override}`.",
            )
    skill_id = decision.skill
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
    # Workflow/session storage: explicit --project / .akomagni workspace first.
    # Never inherit a parent BMAD checkout (Money) just because cwd is nested.
    from akomagni.core.project import find_akomagni_workspace

    storage_root = None
    if project_root is not None:
        storage_root = project_root.resolve()
    else:
        storage_root = find_akomagni_workspace()
    if storage_root is None:
        storage_root = find_project_root()
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
