"""Hardware detection and profile recommendation."""

from __future__ import annotations

import platform
import shutil
from typing import Any

import psutil

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


def run_doctor() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage("/") if platform.system() != "Windows" else shutil.disk_usage("C:\\")
    ram_total_gb = round(vm.total / (1024**3), 1)
    ram_available_gb = round(vm.available / (1024**3), 1)
    disk_free_gb = round(disk.free / (1024**3), 1)
    gpu = _detect_gpu()
    profile = _recommend_profile(ram_total_gb, gpu.get("vram_gb"))
    models = _model_suggestions(profile)

    lines = [
        "Akomagni doctor — rapport machine",
        "",
        f"  OS          : {platform.system()} {platform.release()} ({platform.machine()})",
        f"  CPU         : {psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads",
        f"  RAM         : {ram_available_gb} Go libres / {ram_total_gb} Go total",
        f"  Disque libre: {disk_free_gb} Go",
    ]
    if gpu["name"]:
        lines.append(f"  GPU         : {gpu['name']} ({gpu['vram_gb']} Go VRAM)")
    else:
        lines.append("  GPU         : non détectée (CPU inference)")
    lines.extend(
        [
            "",
            f"  Profil recommandé : [bold]{profile}[/bold]",
            f"  Modèles suggérés  : {', '.join(models)}",
            "",
            "  Tu peux installer des modèles plus gros si ta machine le permet.",
            "  → akomagni model pull <name>  (à venir)",
        ]
    )

    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "ram_total_gb": ram_total_gb,
        "ram_available_gb": ram_available_gb,
        "disk_free_gb": disk_free_gb,
        "gpu": gpu,
        "profile": profile,
        "models": models,
        "summary": "\n".join(lines),
    }
