"""Hugging Face model recommendations by hardware profile."""

from __future__ import annotations

from akomagni.core.config import DEFAULT_CONFIG, MODELS_DIR
from akomagni.core.doctor.scan import run_doctor


def recommend_models() -> dict:
    report = run_doctor()
    profile = report["profile"]
    models = DEFAULT_CONFIG["models"]["profiles"].get(profile, [])
    return {
        "profile": profile,
        "models": models,
        "models_dir": str(MODELS_DIR),
        "hardware": {
            "ram_total_gb": report["ram_total_gb"],
            "ram_available_gb": report["ram_available_gb"],
            "gpu": report["gpu"],
        },
    }
