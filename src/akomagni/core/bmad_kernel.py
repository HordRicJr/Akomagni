"""Shipped BMAD kernel — skills and ``_bmad`` scripts live with the install.

Users do not need to know paths or run ``skill link``: install / update sync the
kernel, and discovery always includes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from akomagni.core.config import DATA_DIR, load_config
from akomagni.core.project import SKILL_DIR_NAMES

KERNEL_DIRNAME = "bmad-core"


@dataclass(frozen=True)
class BmadKernelInfo:
    """Active BMAD kernel location and skill count."""

    root: Path
    skill_count: int
    skills_dir: Path | None


def _skill_dir(root: Path) -> Path | None:
    for rel in (*SKILL_DIR_NAMES, "skills"):
        candidate = root / rel
        if candidate.is_dir() and any(candidate.glob("*/SKILL.md")):
            return candidate.resolve()
    return None


def _is_kernel(path: Path) -> bool:
    return path.is_dir() and (path / "_bmad").is_dir() and _skill_dir(path) is not None


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []
    try:
        from akomagni.core.update import default_install_dir, find_install_root

        install = find_install_root() or default_install_dir()
        candidates.append(install / KERNEL_DIRNAME)
    except ImportError:  # pragma: no cover - defensive
        pass
    candidates.append(DATA_DIR / KERNEL_DIRNAME)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / KERNEL_DIRNAME)
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "akomagni").is_dir():
            break
    return candidates


def find_shipped_bmad_core() -> Path | None:
    """Locate the BMAD kernel shipped with the Akomagni install / checkout."""
    seen: set[Path] = set()
    for raw in _candidate_roots():
        try:
            path = raw.resolve()
        except OSError:
            continue
        if path in seen:
            continue
        seen.add(path)
        if _is_kernel(path):
            return path
    return None


def count_kernel_skills(root: Path) -> int:
    skills = _skill_dir(root)
    if skills is None:
        return 0
    return sum(1 for child in skills.iterdir() if child.is_dir() and (child / "SKILL.md").is_file())


def ensure_bmad_kernel(*, persist: bool = True) -> BmadKernelInfo | None:
    """Register the shipped kernel so skills resolve without ``skill link``.

    Idempotent: if the kernel is already configured, this is a fast path check.
    """
    root = find_shipped_bmad_core()
    if root is None:
        return None

    skills = _skill_dir(root)
    info = BmadKernelInfo(
        root=root,
        skill_count=count_kernel_skills(root),
        skills_dir=skills,
    )
    if not persist:
        return info

    from akomagni.inference.connect import save_config

    cfg = load_config()
    block = dict(cfg.get("skills") or {})
    changed = False

    prev_raw = block.get("bmad_project_root")
    prev = Path(str(prev_raw)).expanduser() if prev_raw else None
    prev_ok = bool(prev and (prev / "_bmad").is_dir())
    # Prefer the shipped kernel when nothing valid is configured yet.
    if not prev_ok:
        block["bmad_project_root"] = str(root)
        changed = True

    if skills is not None:
        roots = [str(Path(r).expanduser().resolve()) for r in (block.get("extra_roots") or [])]
        key = str(skills)
        # Kernel first so discovery order matches skill_search_roots priority.
        ordered = [key]
        for item in roots:
            if item != key and item not in ordered:
                ordered.append(item)
        if ordered != roots:
            block["extra_roots"] = ordered
            changed = True

    if changed:
        cfg["skills"] = block
        save_config(cfg)

    return info


def changelog_highlights(root: Path, *, max_items: int = 20) -> list[str]:
    """Bullet highlights from CHANGELOG.md (Unreleased + latest version)."""
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    highlights: list[str] = []
    in_section = False
    sections_seen = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ["):
            # Skip compare-link footer sections that are not release notes.
            if "http" in stripped and stripped.endswith(")"):
                break
            sections_seen += 1
            in_section = sections_seen <= 2
            continue
        if not in_section:
            continue
        if stripped.startswith("- "):
            text = stripped[2:].strip()
            highlights.append(text)
            if len(highlights) >= max_items:
                break
    return highlights


def read_package_version(root: Path | None = None) -> str:
    """Read version from pyproject.toml or the installed package."""
    if root is not None:
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version"):
                    _, _, rest = line.partition("=")
                    return rest.strip().strip('"').strip("'")
    try:
        from akomagni import __version__

        return __version__
    except ImportError:  # pragma: no cover
        return "unknown"
