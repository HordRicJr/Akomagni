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
    "language": "en",
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
        "provider": "local",
        "host": "127.0.0.1",
        "port": 8787,
        "binary": None,
        "default_model": None,
        "cloud_model_mode": "auto",
        "pinned_model": None,
        "ctx_size": 4096,
        "n_gpu_layers": -1,
    },
    "providers": {
        "rodium": {
            "base_url": "https://api.rodiumai.io/v1",
            "api_key_env": "RODIUMAI_API_KEY",
            "models": {
                "code": "rodiumai/smart",
                "design": "anthropic/claude-haiku-4-5-20251001",
                "text": "google/gemini-3.1-flash-lite-preview",
                "image": "google/gemini-3.1-flash-image",
            },
        },
        "azure": {
            "base_url": None,
            "api_key_env": "AZURE_OPENAI_API_KEY",
            "deployments": {
                "code": "gpt-4o",
                "design": "gpt-4o",
                "text": "gpt-4o-mini",
            },
        },
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
        "inject": True,
        "inject_limit": 3,
        "inject_project": True,
    },
    "mcp": {
        "workspace": None,
        "auto_approve": False,
        "shell_timeout": 30,
    },
    "onboarding": {
        "provider_ready": False,
    },
    "huggingface": {
        "token_env": "HF_TOKEN",  # nosec B105 — env var name, not a secret
        "api_key": None,
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
            "# Akomagni profile\n\n# Filled during onboarding or enriched over time.\n",
            encoding="utf-8",
        )
    prefs = MEMORY_DIR / "preferences.yaml"
    if not prefs.exists():
        prefs.write_text("language: en\n", encoding="utf-8")
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
