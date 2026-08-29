"""Context injection for agents (stub v0.1)."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.config import MEMORY_DIR


def load_central_context() -> str:
    parts: list[str] = []
    profile = MEMORY_DIR / "profile.md"
    if profile.exists():
        parts.append(profile.read_text(encoding="utf-8"))
    prefs = MEMORY_DIR / "preferences.yaml"
    if prefs.exists():
        parts.append(prefs.read_text(encoding="utf-8"))
    for stack in sorted((MEMORY_DIR / "stacks").glob("*.md")):
        parts.append(f"## {stack.name}\n{stack.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def load_project_context() -> str:
    project_dir = Path.cwd() / ".akomagni" / "memory"
    if not project_dir.exists():
        return ""
    chunks: list[str] = []
    for path in sorted(project_dir.rglob("*.md")):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)
