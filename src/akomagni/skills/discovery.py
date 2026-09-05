"""Discover BMAD skills on disk."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from akomagni.core.project import find_project_root, skill_search_roots

_FRONTMATTER = re.compile(r"^---\s*\r?\n(.*?)\r?\n---", re.DOTALL)


@dataclass(frozen=True)
class SkillInfo:
    skill_id: str
    name: str
    description: str
    path: Path
    module: str = ""


def _parse_skill_md(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None}


def _skill_from_path(skill_md: Path) -> SkillInfo | None:
    meta = _parse_skill_md(skill_md)
    skill_id = meta.get("name") or skill_md.parent.name
    return SkillInfo(
        skill_id=skill_id,
        name=skill_id,
        description=meta.get("description", ""),
        path=skill_md.parent,
    )


def discover_skills(project_root: Path | None = None) -> dict[str, SkillInfo]:
    """Return skill_id → SkillInfo from all known install locations.

    First match wins so the shipped BMAD kernel (listed first in
    ``skill_search_roots``) is not overridden by older linked trees.
    """
    found: dict[str, SkillInfo] = {}
    for root in skill_search_roots(project_root):
        for skill_md in root.glob("*/SKILL.md"):
            info = _skill_from_path(skill_md)
            if info and info.skill_id not in found:
                found[info.skill_id] = info
    root = project_root or find_project_root()
    if root:
        manifest = root / "_bmad" / "_config" / "skill-manifest.csv"
        if manifest.is_file():
            with manifest.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    skill_id = row.get("name", "").strip()
                    rel = row.get("path", "").strip()
                    if not skill_id or not rel or skill_id in found:
                        continue
                    skill_path = root / rel
                    if skill_path.is_file():
                        info = _skill_from_path(skill_path)
                        if info:
                            found[skill_id] = SkillInfo(
                                skill_id=skill_id,
                                name=skill_id,
                                description=row.get("description", info.description),
                                path=skill_path.parent,
                                module=row.get("module", ""),
                            )
    return found


def find_skill(skill_id: str, project_root: Path | None = None) -> SkillInfo | None:
    return discover_skills(project_root).get(skill_id)
