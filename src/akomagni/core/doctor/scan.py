"""Hardware detection and profile recommendation."""

from __future__ import annotations

import platform
import shutil
from typing import Any

import psutil

from akomagni.core.i18n import normalize_language, translate

PROFILE_LIGHT = "light"
PROFILE_STANDARD = "standard"
PROFILE_POWER = "power"


def _detect_gpu() -> dict[str, Any]:
    gpu: dict[str, Any] = {"name": None, "vram_gb": None, "backend": None}
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return gpu
    try:
        import subprocess

        result = subprocess.run(  # nosec B603
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().splitlines()[0]
            name, vram_mb = [p.strip() for p in line.split(",", 1)]
            gpu = {
                "name": name,
                "vram_gb": round(float(vram_mb) / 1024, 1),
                "backend": "cuda",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return gpu


def _recommend_profile(ram_gb: float, vram_gb: float | None) -> str:
    if vram_gb and vram_gb >= 12:
        return PROFILE_POWER
    if ram_gb >= 32:
        return PROFILE_POWER
    if ram_gb >= 16:
        return PROFILE_STANDARD
    return PROFILE_LIGHT


def _model_suggestions(profile: str) -> list[str]:
    from akomagni.core.config import DEFAULT_CONFIG

    return list(DEFAULT_CONFIG["models"]["profiles"].get(profile, []))


def run_doctor(*, lang: str | None = None) -> dict[str, Any]:
    language = normalize_language(lang)
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage("/") if platform.system() != "Windows" else shutil.disk_usage("C:\\")
    ram_total_gb = round(vm.total / (1024**3), 1)
    ram_available_gb = round(vm.available / (1024**3), 1)
    disk_free_gb = round(disk.free / (1024**3), 1)
    gpu = _detect_gpu()
    profile = _recommend_profile(ram_total_gb, gpu.get("vram_gb"))
    models = _model_suggestions(profile)

    lines = [
        translate("doctor.title", language),
        "",
        translate(
            "doctor.os",
            language,
            os=platform.system(),
            release=platform.release(),
            machine=platform.machine(),
        ),
        translate(
            "doctor.cpu",
            language,
            cores=psutil.cpu_count(logical=False),
            threads=psutil.cpu_count(),
        ),
        translate(
            "doctor.ram",
            language,
            available=ram_available_gb,
            total=ram_total_gb,
        ),
        translate("doctor.disk", language, free=disk_free_gb),
    ]
    if gpu["name"]:
        lines.append(
            translate(
                "doctor.gpu",
                language,
                name=gpu["name"],
                vram=gpu["vram_gb"],
            )
        )
    else:
        lines.append(translate("doctor.gpu_none", language))

    from akomagni.core.bmad_kernel import ensure_bmad_kernel

    kernel = ensure_bmad_kernel(persist=True)
    if kernel is not None:
        lines.append(
            translate(
                "doctor.bmad_kernel",
                language,
                count=kernel.skill_count,
                path=kernel.root,
            )
        )
    else:
        lines.append(translate("doctor.bmad_missing", language))

    lines.extend(
        [
            "",
            translate("doctor.recommended_profile", language, profile=profile),
            translate("doctor.suggested_models", language, models=", ".join(models)),
            "",
            translate("doctor.hint", language),
            translate("doctor.pull_hint", language),
        ]
    )

    return {
        "os": platform.system(),
        "bmad_kernel": (
            {
                "path": str(kernel.root),
                "skill_count": kernel.skill_count,
            }
            if kernel
            else None
        ),
        "arch": platform.machine(),
        "ram_total_gb": ram_total_gb,
        "ram_available_gb": ram_available_gb,
        "disk_free_gb": disk_free_gb,
        "gpu": gpu,
        "profile": profile,
        "models": models,
        "summary": "\n".join(lines),
        "language": language,
    }
