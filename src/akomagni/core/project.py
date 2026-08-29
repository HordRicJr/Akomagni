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


def skill_search_roots(project_root: Path | None = None) -> list[Path]:
    """Directories to scan for installed BMAD skill folders."""
    from akomagni.core.config import SKILLS_DIR

    roots: list[Path] = []
    if SKILLS_DIR.is_dir():
        roots.append(SKILLS_DIR)
    root = project_root or find_project_root()
    if root:
        for rel in SKILL_DIR_NAMES:
            candidate = root / rel
            if candidate.is_dir():
                roots.append(candidate)
    return roots
