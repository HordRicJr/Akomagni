"""Project root discovery for BMAD / Akomagni workspaces."""

from __future__ import annotations

from pathlib import Path

BMAD_MARKERS = ("_bmad", ".bmad")
SKILL_DIR_NAMES = (".claude/skills", ".agents/skills", ".agent/skills")
_RENDER_REL = Path("_bmad") / "scripts" / "render_skill.py"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* (or cwd) looking for a BMAD project root.

    Prefer trees that contain ``_bmad/`` (where ``render_skill.py`` lives). A lone
    ``.bmad`` marker without ``_bmad`` is ignored so a home-folder stub cannot
    shadow the real workspace.
    """
    current = (start or Path.cwd()).resolve()
    fallback: Path | None = None
    for directory in (current, *current.parents):
        bmad_dir = directory / "_bmad"
        if bmad_dir.is_dir():
            return directory
        if (
            fallback is None
            and (directory / ".bmad").is_dir()
            and (directory / _RENDER_REL).is_file()
        ):
            fallback = directory
    return fallback


def find_bmad_root_from_skill(skill_path: Path | None) -> Path | None:
    """Infer the BMAD checkout that owns *skill_path* (…/skills/<id>)."""
    if skill_path is None:
        return None
    return find_project_root(skill_path.resolve())


def configured_bmad_root() -> Path | None:
    """Optional workspace root persisted by ``akomagni skill link``."""
    try:
        from akomagni.core.config import load_config
    except ImportError:  # pragma: no cover - import cycle guard
        return None
    cfg = load_config()
    block = cfg.get("skills") or {}
    raw = block.get("bmad_project_root")
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if (path / "_bmad").is_dir() or (path / ".bmad").is_dir():
        return path.resolve()
    return None


def resolve_bmad_project_root(
    project_root: Path | None = None,
    *,
    skill_path: Path | None = None,
    start: Path | None = None,
) -> Path | None:
    """Best BMAD root for skill execution / render_skill.py.

    Prefer an explicit root, then the skill's ancestor tree, then cwd discovery,
    then a linked workspace from config / known skill roots.
    """
    if project_root is not None:
        return project_root.resolve()
    # Prefer the skill's checkout so CLI outside that tree still finds render_skill.py
    # (and so ambient cwd markers cannot steal resolution from an explicit skill path).
    from_skill = find_bmad_root_from_skill(skill_path)
    if from_skill is not None:
        return from_skill
    found = find_project_root(start)
    if found is not None:
        return found
    configured = configured_bmad_root()
    if configured is not None:
        return configured
    try:
        from akomagni.skills.link import extra_skill_roots
    except ImportError:  # pragma: no cover
        return None
    for root in extra_skill_roots():
        candidate = find_project_root(root)
        if candidate is not None:
            return candidate
    return None


def render_skill_script(project_root: Path | None) -> Path | None:
    """Return ``render_skill.py`` under *project_root* when present."""
    if project_root is None:
        return None
    path = project_root.resolve() / _RENDER_REL
    return path if path.is_file() else None


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
    root = project_root or find_project_root() or configured_bmad_root()
    if root:
        for rel in SKILL_DIR_NAMES:
            candidate = root / rel
            if candidate.is_dir():
                _add(candidate)
    return roots
