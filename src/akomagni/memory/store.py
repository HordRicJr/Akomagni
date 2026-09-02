"""Memory store paths and status."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.config import MEMORY_DIR, load_config
from akomagni.core.i18n import resolve_language, translate


def project_memory_dir(project_root: Path | None = None) -> Path:
    from akomagni.core.project import find_project_root

    root = project_root or find_project_root()
    if root is None:
        return Path(".akomagni") / "memory"
    return root / ".akomagni" / "memory"


def memory_status(*, lang: str | None = None) -> str:
    cfg = load_config()
    language = lang or resolve_language(cfg)
    central = MEMORY_DIR
    project = project_memory_dir()
    lines = [
        translate("memory.title", language),
        "",
        translate("memory.central", language, path=central),
        f"    profile.md      : {'✓' if (central / 'profile.md').exists() else '—'}",
        f"    preferences.yaml: {'✓' if (central / 'preferences.yaml').exists() else '—'}",
        f"    stacks/         : {'✓' if (central / 'stacks').is_dir() else '—'}",
        "",
        translate("memory.project", language, path=project),
        translate("memory.project_hint", language),
    ]
    if project.exists():
        lines.append(
            translate(
                "memory.project_files",
                language,
                count=len(list(project.rglob("*"))),
            )
        )
    return "\n".join(lines)
