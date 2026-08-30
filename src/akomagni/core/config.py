"""Akomagni configuration (~/.akomagni/config.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_data_dir

APP_NAME = "akomagni"
DATA_DIR = Path(user_data_dir(APP_NAME, appauthor=False))
CONFIG_PATH = DATA_DIR / "config.yaml"
MEMORY_DIR = DATA_DIR / "memory"
MODELS_DIR = DATA_DIR / "models"
SKILLS_DIR = DATA_DIR / "skills"

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "router": {
        "mode": "auto",
        "model": "router",
        "domains": {
            "code": "qwen2.5-coder-7b",
            "design": "llama-3.1-8b",
            "image": None,
            "text": "phi-3.5-mini",
        },
    },
    "inference": {
        "host": "127.0.0.1",
        "port": 8787,
        "binary": None,
        "default_model": None,
        "ctx_size": 4096,
        "n_gpu_layers": -1,
    },
    "workflow": {
        "brainstorm": {
            "mode": "mandatory",
            "greenfield_only": True,
            "host_agent": "bmad-agent-analyst",
        }
    },
    "memory": {
        "auto_capture": False,
        "capture_global": False,
        "central_dir": str(MEMORY_DIR),
    },
    "rag": {
        "chunk_size": 800,
        "chunk_overlap": 120,
        "default_limit": 5,
        "rrf_k": 60,
    },
    "models": {
        "profiles": {
            "light": ["Phi-3.5-mini", "Llama-3.2-3B"],
            "standard": ["Qwen2.5-Coder-7B", "Llama-3.1-8B-Instruct"],
            "power": ["Qwen2.5-Coder-14B", "Llama-3.1-70B-Instruct"],
        }
    },
}


def ensure_default_config() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            yaml.dump(DEFAULT_CONFIG, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
    _ensure_memory_scaffold()
    return CONFIG_PATH


def _ensure_memory_scaffold() -> None:
    profile = MEMORY_DIR / "profile.md"
    if not profile.exists():
        profile.write_text(
            "# Profil Akomagni\n\n# Rempli à l'onboarding ou enrichi au fil du temps.\n",
            encoding="utf-8",
        )
    prefs = MEMORY_DIR / "preferences.yaml"
    if not prefs.exists():
        prefs.write_text("language: fr\n", encoding="utf-8")
    stacks = MEMORY_DIR / "stacks"
    stacks.mkdir(exist_ok=True)
    for name, body in {
        "web.md": "# Stack web\n\n",
        "backend.md": "# Stack backend\n\n",
        "design.md": "# Stack design\n\n",
    }.items():
        path = stacks / name
        if not path.exists():
            path.write_text(body, encoding="utf-8")


def load_config() -> dict[str, Any]:
    ensure_default_config()
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    merged = {**DEFAULT_CONFIG, **data}
    return merged
