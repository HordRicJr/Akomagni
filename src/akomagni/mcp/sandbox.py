"""Workspace path sandbox for agent tools."""

from __future__ import annotations

from pathlib import Path


class SandboxError(ValueError):
    """Raised when a path escapes the workspace sandbox."""


def resolve_workspace(path: Path | str | None = None) -> Path:
    """Resolve the MCP workspace root."""
    if path is None:
        from akomagni.core.config import load_config
        from akomagni.core.project import find_project_root

        cfg = load_config().get("mcp", {})
        configured = cfg.get("workspace")
        if configured:
            return Path(configured).expanduser().resolve()
        project = find_project_root()
        if project is not None:
            return project.resolve()
        return Path.cwd().resolve()
    return Path(path).expanduser().resolve()


def resolve_path(relative: str, workspace: Path) -> Path:
    """Resolve *relative* inside *workspace*; reject path traversal."""
    workspace = workspace.resolve()
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise SandboxError(f"path escapes workspace: {relative}") from exc
    return candidate
