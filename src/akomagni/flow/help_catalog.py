"""BMAD help catalog loader (bmad-help.csv)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from akomagni.core.project import find_project_root

HELP_CSV_REL = Path("_bmad") / "_config" / "bmad-help.csv"


@dataclass(frozen=True)
class HelpEntry:
    module: str
    skill: str
    display_name: str
    action: str
    phase: str
    preceded_by: tuple[str, ...]
    followed_by: tuple[str, ...]
    required: bool


def _parse_prereqs(value: str) -> tuple[str, ...]:
    if not value or not value.strip():
        return ()
    return (value.strip(),)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def parse_help_csv(path: Path) -> dict[str, HelpEntry]:
    """Parse *bmad-help.csv* into a skill-id keyed catalog."""
    catalog: dict[str, HelpEntry] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            skill = (row.get("skill") or "").strip()
            if not skill or skill == "_meta":
                continue
            entry = HelpEntry(
                module=(row.get("module") or "").strip(),
                skill=skill,
                display_name=(row.get("display-name") or skill).strip(),
                action=(row.get("action") or "").strip(),
                phase=(row.get("phase") or "anytime").strip(),
                preceded_by=_parse_prereqs(row.get("preceded-by") or ""),
                followed_by=_parse_prereqs(row.get("followed-by") or ""),
                required=_parse_bool(row.get("required") or "false"),
            )
            catalog[skill] = entry
    return catalog


def help_csv_path(project_root: Path | None = None) -> Path | None:
    root = project_root or find_project_root()
    if not root:
        return None
    path = root / HELP_CSV_REL
    return path if path.is_file() else None


@lru_cache(maxsize=8)
def _load_cached(csv_path: str) -> dict[str, HelpEntry]:
    return parse_help_csv(Path(csv_path))


def load_help_catalog(project_root: Path | None = None) -> dict[str, HelpEntry]:
    """Load BMAD help catalog for the current project (cached per CSV path)."""
    path = help_csv_path(project_root)
    if not path:
        return {}
    return _load_cached(str(path.resolve()))


def clear_help_catalog_cache() -> None:
    _load_cached.cache_clear()
