"""Self-update for one-liner / git installs."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class UpdateError(RuntimeError):
    """Raised when Akomagni cannot update itself."""


@dataclass(frozen=True)
class UpdateResult:
    """Summary of a successful self-update."""

    install_dir: Path
    bin_path: Path
    previous_ref: str
    current_ref: str


def default_install_dir() -> Path:
    """Default clone location used by install scripts."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "akomagni"
        return Path.home() / "AppData" / "Local" / "akomagni"
    return Path.home() / ".local" / "share" / "akomagni"


def default_bin_dir() -> Path:
    """Default user binary directory used by install scripts."""
    if platform.system() == "Windows":
        return Path.home() / ".local" / "bin"
    return Path.home() / ".local" / "bin"


def find_install_root() -> Path | None:
    """Locate the Akomagni source tree backing the running CLI."""
    exe = Path(sys.executable).resolve()
    parts = exe.parts
    if "Scripts" in parts:
        idx = parts.index("Scripts")
        candidate = Path(*parts[:idx])
        if (candidate.parent / "pyproject.toml").is_file():
            return candidate.parent
    if "bin" in parts:
        idx = parts.index("bin")
        candidate = Path(*parts[:idx])
        if (candidate.parent / "pyproject.toml").is_file():
            return candidate.parent

    install_dir = default_install_dir()
    if (install_dir / "pyproject.toml").is_file():
        return install_dir
    return None


def _git_ref(root: Path) -> str:
    result = subprocess.run(  # nosec B603
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def run_update(*, install_dir: Path | None = None, bin_dir: Path | None = None) -> UpdateResult:
    """Pull latest main and reinstall the editable package."""
    root = install_dir or find_install_root()
    if root is None or not (root / "pyproject.toml").is_file():
        raise UpdateError(
            "Cannot locate Akomagni install directory. "
            "Re-run the install one-liner from https://hordricjr.github.io/Akomagni/install/"
        )

    if not (root / ".git").is_dir():
        raise UpdateError(f"No git checkout at {root}. Re-run the install one-liner to reinstall.")

    if shutil.which("git") is None:
        raise UpdateError("git is required for akomagni update.")

    previous = _git_ref(root)
    pull = subprocess.run(  # nosec B603
        ["git", "-C", str(root), "pull", "--ff-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        detail = (pull.stderr or pull.stdout or "").strip()
        raise UpdateError(f"git pull failed: {detail}")

    python_exe = sys.executable
    venv_python = (
        root
        / ".venv"
        / ("Scripts" if platform.system() == "Windows" else "bin")
        / ("python.exe" if platform.system() == "Windows" else "python")
    )
    if venv_python.is_file():
        python_exe = str(venv_python)

    pip_upgrade = subprocess.run(  # nosec B603
        [python_exe, "-m", "pip", "install", "-U", "pip"],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_upgrade.returncode != 0:
        detail = (pip_upgrade.stderr or pip_upgrade.stdout or "").strip()
        raise UpdateError(f"pip upgrade failed: {detail}")

    from akomagni.core.deps import CORE_DEPENDENCIES

    pip_deps = subprocess.run(  # nosec B603
        [python_exe, "-m", "pip", "install", "--upgrade", *CORE_DEPENDENCIES],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_deps.returncode != 0:
        detail = (pip_deps.stderr or pip_deps.stdout or "").strip()
        raise UpdateError(f"dependency install failed: {detail}")

    pip_install = subprocess.run(  # nosec B603
        [python_exe, "-m", "pip", "install", "-e", str(root), "--no-deps"],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_install.returncode != 0:
        detail = (pip_install.stderr or pip_install.stdout or "").strip()
        raise UpdateError(f"pip install failed: {detail}")

    target_bin = bin_dir or Path(os.environ.get("AKOMAGNI_BIN_DIR", str(default_bin_dir())))
    target_bin.mkdir(parents=True, exist_ok=True)
    scripts_dir = root / ".venv" / ("Scripts" if platform.system() == "Windows" else "bin")
    source_bin = scripts_dir / ("akomagni.exe" if platform.system() == "Windows" else "akomagni")
    if not source_bin.is_file():
        raise UpdateError(f"Missing CLI binary after update: {source_bin}")

    dest_bin = target_bin / ("akomagni.exe" if platform.system() == "Windows" else "akomagni")
    if platform.system() == "Windows":
        shutil.copy2(source_bin, dest_bin)
    else:
        if dest_bin.exists() or dest_bin.is_symlink():
            dest_bin.unlink()
        dest_bin.symlink_to(source_bin)

    current = _git_ref(root)
    return UpdateResult(
        install_dir=root,
        bin_path=dest_bin,
        previous_ref=previous,
        current_ref=current,
    )
