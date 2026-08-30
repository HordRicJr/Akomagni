"""Memory add and promote operations."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from akomagni.core.config import MEMORY_DIR


class MemoryError(ValueError):
    """Raised when a memory operation cannot complete."""


@dataclass(frozen=True)
class PromoteResult:
    source: Path
    destination: Path
    files_copied: int


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")[:60] or "note"


def _learnings_dir(base: Path) -> Path:
    directory = base / "learnings"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def add_memory(
    text: str,
    *,
    global_: bool = False,
    title: str | None = None,
    project_root: Path | None = None,
) -> Path:
    """Append a learning note to project or central memory."""
    content = text.strip()
    if not content:
        raise MemoryError("memory text must not be empty")

    if global_:
        base = MEMORY_DIR
    else:
        root = project_root or Path.cwd()
        base = root / ".akomagni" / "memory"
        base.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = _slugify(title or content.splitlines()[0])
    path = _learnings_dir(base) / f"{stamp}-{slug}.md"
    heading = title or "Learning"
    path.write_text(f"# {heading}\n\n{content}\n", encoding="utf-8")
    return path


def promote_project_memory(*, project_root: Path | None = None) -> PromoteResult:
    """Copy project memory into central learnings (promoted snapshot)."""
    root = project_root or Path.cwd()
    source = root / ".akomagni" / "memory"
    if not source.is_dir() or not any(source.rglob("*")):
        raise MemoryError("no project memory found — run from a project with .akomagni/memory/")

    project_slug = _slugify(root.name)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    destination = _learnings_dir(MEMORY_DIR) / f"promoted-{project_slug}-{stamp}"
    destination.mkdir(parents=True, exist_ok=True)

    files_copied = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files_copied += 1

    if files_copied == 0:
        raise MemoryError("project memory directory is empty")

    return PromoteResult(source=source, destination=destination, files_copied=files_copied)
