"""Project root discovery for BMAD / Akomagni workspaces."""

from __future__ import annotations

from pathlib import Path

BMAD_MARKERS = ("_bmad", ".bmad")
SKILL_DIR_NAMES = (".claude/skills", ".agents/skills", ".agent/skills")


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* (or cwd) looking for a BMAD project root."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / "_bmad").is_dir():
            return directory
        if (directory / ".bmad").is_dir():
            return directory
    return None


def resolve_workspace_root(
    project_root: Path | None = None,
    *,
    start: Path | None = None,
) -> tuple[Path, bool]:
    """Return ``(storage_root, is_bmad_project)`` for workflow/session data.

    In a BMAD workspace, data lives under ``<project>/.akomagni/``. Outside a
    project, use the central Akomagni data directory (``platformdirs``) instead
    of the current working directory — so running from ``System32`` still works.
    """
    if project_root is not None:
        return project_root.resolve(), True
    found = find_project_root(start)
    if found is not None:
        return found, True
    from akomagni.core.config import DATA_DIR

    return DATA_DIR, False


def skill_search_roots(project_root: Path | None = None) -> list[Path]:
    """Directories to scan for installed BMAD skill folders."""
    from akomagni.core.config import SKILLS_DIR
    from akomagni.skills.link import extra_skill_roots

    roots: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        resolved = path.resolve()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)

    if SKILLS_DIR.is_dir():
        _add(SKILLS_DIR)
    for extra in extra_skill_roots():
        _add(extra)
    root = project_root or find_project_root()
    if root:
        for rel in SKILL_DIR_NAMES:
            candidate = root / rel
            if candidate.is_dir():
                _add(candidate)
    return roots
