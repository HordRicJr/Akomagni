"""Pinned runtime dependencies for install/update scripts."""

from __future__ import annotations

CORE_DEPENDENCIES: tuple[str, ...] = (
    "platformdirs>=4.0",
    "typer>=0.12",
    "rich>=13.7",
    "pyyaml>=6.0",
    "psutil>=5.9",
    "sqlite-vec>=0.1.6",
)
