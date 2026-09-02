"""Akomagni Flow workflow state on disk."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from akomagni.core.project import resolve_workspace_root


def workflow_dir(
    project_root: Path | None = None,
    *,
    start: Path | None = None,
    discover: bool = True,
) -> Path:
    if project_root is not None:
        return project_root / ".akomagni" / "workflow"
    if discover:
        root, is_project = resolve_workspace_root(None, start=start)
        if is_project:
            return root / ".akomagni" / "workflow"
    from akomagni.core.config import DATA_DIR

    return DATA_DIR / "workflow"


def load_state(
    project_root: Path | None = None,
    *,
    start: Path | None = None,
    discover: bool = True,
) -> dict[str, Any]:
    path = workflow_dir(project_root, start=start, discover=discover) / "state.yaml"
    if not path.is_file():
        return {"phase": "anytime", "gates": {}, "completed": []}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_state(
    state: dict[str, Any],
    project_root: Path | None = None,
    *,
    start: Path | None = None,
    discover: bool = True,
) -> Path:
    directory = workflow_dir(project_root, start=start, discover=discover)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(state, f, allow_unicode=True, default_flow_style=False)
    return path


def record_invocation(
    *,
    agent_id: str,
    skill_id: str,
    session_path: Path,
    project_root: Path | None = None,
) -> Path:
    discover = project_root is not None
    state = load_state(project_root, discover=discover)
    state["active_agent"] = agent_id
    state["active_skill"] = skill_id
    state.setdefault("completed", [])
    if skill_id not in state["completed"]:
        state["completed"].append(skill_id)
    state["last_session"] = str(session_path)
    state["updated_at"] = datetime.now(UTC).isoformat()
    if skill_id in ("bmad-brainstorming", "gds-brainstorm-game"):
        state.setdefault("gates", {})["brainstorm"] = "in_progress"
    return save_state(state, project_root, discover=discover)
