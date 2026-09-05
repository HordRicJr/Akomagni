"""Execute BMAD skills via ``uv run`` subprocess."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_WORKFLOW_LINE = re.compile(r"^read and follow (.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class SkillRunResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    workflow_path: Path | None
    success: bool
    error: str = ""


def find_uv() -> str | None:
    """Return ``uv`` executable path when available."""
    return shutil.which("uv")


def render_script_path(project_root: Path) -> Path | None:
    """Return BMAD render script when the project has one installed."""
    from akomagni.core.project import render_skill_script

    return render_skill_script(project_root)


def parse_workflow_path(stdout: str) -> Path | None:
    """Parse ``read and follow <path>`` from render_skill stdout."""
    match = _WORKFLOW_LINE.search(stdout.strip())
    if not match:
        return None
    candidate = Path(match.group(1).strip().strip('"'))
    return candidate if candidate.is_file() else None


def build_context_env(
    *,
    message: str,
    central_context: str,
    project_context: str,
    rag_context: str = "",
) -> dict[str, str]:
    """Environment variables passed to BMAD skill subprocesses."""
    parts: list[str] = []
    if central_context.strip():
        parts.append(central_context.strip())
    if project_context.strip():
        parts.append(project_context.strip())
    memory = "\n\n".join(parts)
    env = {
        "AKOMAGNI_USER_MESSAGE": message.strip(),
    }
    if memory:
        env["AKOMAGNI_MEMORY_CONTEXT"] = memory
    if rag_context.strip():
        env["AKOMAGNI_RAG_CONTEXT"] = rag_context.strip()
    return env


def build_render_command(
    *,
    uv: str,
    project_root: Path,
    skill_path: Path,
) -> list[str]:
    """Build argv for ``uv run render_skill.py``."""
    script = render_script_path(project_root)
    if script is None:
        raise FileNotFoundError(f"BMAD render script not found under {project_root}")
    return [
        uv,
        "run",
        "--no-cache",
        str(script),
        "--project-root",
        str(project_root),
        "--skill",
        str(skill_path),
    ]


def run_skill_subprocess(
    *,
    project_root: Path,
    skill_path: Path,
    message: str,
    central_context: str = "",
    project_context: str = "",
    rag_context: str = "",
    uv: str | None = None,
    timeout: float | None = 120.0,
) -> SkillRunResult:
    """Run ``render_skill.py`` for *skill_path* and return captured output."""
    uv_bin = uv or find_uv()
    if not uv_bin:
        return SkillRunResult(
            command=(),
            returncode=127,
            stdout="",
            stderr="",
            workflow_path=None,
            success=False,
            error="uv not found on PATH",
        )

    try:
        command = build_render_command(
            uv=uv_bin,
            project_root=project_root,
            skill_path=skill_path,
        )
    except FileNotFoundError as exc:
        return SkillRunResult(
            command=(),
            returncode=127,
            stdout="",
            stderr="",
            workflow_path=None,
            success=False,
            error=str(exc),
        )

    env = os.environ.copy()
    env.update(
        build_context_env(
            message=message,
            central_context=central_context,
            project_context=project_context,
            rag_context=rag_context,
        )
    )
    try:
        completed = subprocess.run(  # nosec B603
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return SkillRunResult(
            command=tuple(command),
            returncode=124,
            stdout="",
            stderr="",
            workflow_path=None,
            success=False,
            error=f"skill subprocess timed out after {timeout}s",
        )
    except OSError as exc:
        return SkillRunResult(
            command=tuple(command),
            returncode=1,
            stdout="",
            stderr="",
            workflow_path=None,
            success=False,
            error=str(exc),
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    workflow_path = parse_workflow_path(stdout) if completed.returncode == 0 else None
    success = completed.returncode == 0 and workflow_path is not None
    error = ""
    if completed.returncode != 0:
        error = stderr.strip() or stdout.strip() or f"exit code {completed.returncode}"
    elif workflow_path is None:
        error = "render_skill did not return a workflow path"

    return SkillRunResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        workflow_path=workflow_path,
        success=success,
        error=error,
    )
