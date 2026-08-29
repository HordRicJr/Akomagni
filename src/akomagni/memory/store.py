"""Memory store paths and status."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.config import MEMORY_DIR


def project_memory_dir() -> Path:
    return Path.cwd() / ".akomagni" / "memory"


def memory_status() -> str:
    central = MEMORY_DIR
    project = project_memory_dir()
    lines = [
        "Akomagni Memory",
        "",
        f"  Centrale : {central}",
        f"    profile.md      : {'✓' if (central / 'profile.md').exists() else '—'}",
        f"    preferences.yaml: {'✓' if (central / 'preferences.yaml').exists() else '—'}",
        f"    stacks/         : {'✓' if (central / 'stacks').is_dir() else '—'}",
        "",
        f"  Projet   : {project}",
        "    (créé à la première capture projet)",
    ]
    if project.exists():
        lines.append(f"    fichiers        : {len(list(project.rglob('*')))} entrées")
    return "\n".join(lines)
