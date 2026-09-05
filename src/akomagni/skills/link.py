"""Link BMAD skill directories into the global Akomagni skills search path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from akomagni.core.config import DATA_DIR, SKILLS_DIR, load_config
from akomagni.core.project import SKILL_DIR_NAMES
from akomagni.inference.connect import save_config


def _known_skill_locations() -> list[Path]:
    """Extra places to look when the user is outside a BMAD checkout."""
    home = Path.home()
    locations = [
        home / ".agent" / "skills",
        home / ".agents" / "skills",
        home / ".claude" / "skills",
        home / ".cursor" / "skills",
        Path("D:/Money/.agent/skills"),
        Path("D:/Money/.agents/skills"),
        Path("D:/Money/.claude/skills"),
    ]
    # Install tree lives under LocalAppData/akomagni; Money may sit next to repos.
    for parent in (DATA_DIR, Path.cwd().resolve()):
        for rel in (
            "../Money/.agent/skills",
            "../Money/.claude/skills",
            "../../Money/.agent/skills",
        ):
            locations.append((parent / rel).resolve())
    return locations


def extra_skill_roots(config: dict[str, Any] | None = None) -> list[Path]:
    """Configured skill directories (absolute paths)."""
    cfg = config or load_config()
    block = cfg.get("skills") or {}
    roots: list[Path] = []
    for raw in block.get("extra_roots") or []:
        path = Path(str(raw)).expanduser()
        if path.is_dir():
            roots.append(path.resolve())
    return roots


def discover_skill_sources(start: Path | None = None) -> list[Path]:
    """Find BMAD skill install folders near *start*, home, or known workspaces."""
    found: list[Path] = []
    seen: set[Path] = set()
    cwd = (start or Path.cwd()).resolve()
    search_roots = [
        cwd,
        *cwd.parents,
        *[p.parent for p in _known_skill_locations() if p.parent.exists()],
    ]

    def _consider(candidate: Path) -> None:
        try:
            resolved = candidate.resolve()
        except OSError:
            return
        if resolved in seen or not resolved.is_dir():
            return
        if any(resolved.glob("*/SKILL.md")):
            seen.add(resolved)
            found.append(resolved)

    for root in search_roots:
        for rel in SKILL_DIR_NAMES:
            _consider(root / rel)
        if found:
            return found

    for location in _known_skill_locations():
        _consider(location)
        if found:
            break
    return found


def register_skill_root(source: Path) -> Path:
    """Persist *source* in config so discovery works outside the BMAD tree."""
    resolved = source.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Skill source not found: {resolved}")
    if not any(resolved.glob("*/SKILL.md")):
        raise FileNotFoundError(f"No skills (*/SKILL.md) under {resolved}")

    cfg = load_config()
    block = dict(cfg.get("skills") or {})
    roots = [str(Path(r).expanduser().resolve()) for r in (block.get("extra_roots") or [])]
    key = str(resolved)
    if key not in roots:
        roots.append(key)
    block["extra_roots"] = roots
    # Remember the BMAD checkout so render_skill.py works outside that tree.
    from akomagni.core.project import find_project_root

    bmad = find_project_root(resolved)
    if bmad is not None:
        block["bmad_project_root"] = str(bmad)
    cfg["skills"] = block
    save_config(cfg)

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    marker = SKILLS_DIR / ".linked-roots"
    existing = marker.read_text(encoding="utf-8").splitlines() if marker.is_file() else []
    if key not in existing:
        existing.append(key)
        marker.write_text("\n".join(existing) + "\n", encoding="utf-8")
    return resolved


def ensure_skills_linked(start: Path | None = None) -> list[Path]:
    """Auto-register nearby BMAD skill folders when none are configured yet."""
    current = extra_skill_roots()
    if current:
        return current
    if SKILLS_DIR.is_dir() and any(SKILLS_DIR.glob("*/SKILL.md")):
        return [SKILLS_DIR]
    linked: list[Path] = []
    for source in discover_skill_sources(start):
        linked.append(register_skill_root(source))
    return linked
