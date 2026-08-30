"""Akomagni Flow workflow state on disk."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def workflow_dir(project_root: Path | None = None) -> Path:
    base = project_root or Path.cwd()
    return base / ".akomagni" / "workflow"


def load_state(project_root: Path | None = None) -> dict[str, Any]:
    path = workflow_dir(project_root) / "state.yaml"
    if not path.is_file():
        return {"phase": "anytime", "gates": {}, "completed": []}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_state(state: dict[str, Any], project_root: Path | None = None) -> Path:
    directory = workflow_dir(project_root)
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
    # sessions/ → workflow/ → .akomagni/ → project root
    root = project_root or session_path.parent.parent.parent.parent
    state = load_state(root)
    state["active_agent"] = agent_id
    state["active_skill"] = skill_id
    state.setdefault("completed", [])
    if skill_id not in state["completed"]:
        state["completed"].append(skill_id)
    state["last_session"] = str(session_path)
    state["updated_at"] = datetime.now(UTC).isoformat()
    if skill_id in ("bmad-brainstorming", "gds-brainstorm-game"):
        state.setdefault("gates", {})["brainstorm"] = "in_progress"
    return save_state(state, root)
