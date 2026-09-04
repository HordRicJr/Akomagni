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


def _git_exe() -> str:
    git = shutil.which("git")
    if not git:
        raise UpdateError("git is required for akomagni update.")
    return git


def _git_ref(root: Path) -> str:
    result = subprocess.run(  # nosec B603
        [_git_exe(), "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def _install_cli_binary(source_bin: Path, dest_bin: Path) -> None:
    """Install CLI shim into the user bin dir (Windows-safe while running)."""
    dest_bin.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() != "Windows":
        if dest_bin.exists() or dest_bin.is_symlink():
            dest_bin.unlink()
        dest_bin.symlink_to(source_bin)
        return

    # Same path (shim already points at venv entrypoint) — nothing to do.
    try:
        if source_bin.resolve() == dest_bin.resolve():
            return
    except OSError:
        pass

    # On Windows the running akomagni.exe locks itself. Prefer rename-away,
    # then put the new binary in place. Never let PermissionError bubble out.
    staging = dest_bin.with_name(f"{dest_bin.name}.{os.getpid()}.new")
    backup = dest_bin.with_name(dest_bin.name + ".old")
    try:
        if staging.exists():
            staging.unlink()
    except OSError:
        pass

    try:
        shutil.copy2(source_bin, staging)
    except OSError as exc:
        raise UpdateError(
            f"Cannot stage new CLI binary at {staging}: {exc}\n"
            "Close other Akomagni terminals, then retry `akomagni update`, or reinstall:\n"
            "  irm https://hordricjr.github.io/Akomagni/install/windows | iex"
        ) from exc

    try:
        if backup.exists():
            backup.unlink()
    except OSError:
        pass

    if dest_bin.exists():
        try:
            os.replace(str(dest_bin), str(backup))
        except OSError:
            try:
                # Last resort overwrite (often fails while process holds the lock).
                shutil.copy2(staging, dest_bin)
                staging.unlink(missing_ok=True)
                return
            except OSError as exc:
                staging.unlink(missing_ok=True)
                raise UpdateError(
                    f"Cannot replace {dest_bin} while it is in use (WinError 32).\n"
                    "The package code was updated; only the launcher shim is locked.\n"
                    "Close this window, open a new PowerShell, then run:\n"
                    "  irm https://hordricjr.github.io/Akomagni/install/windows | iex\n"
                    f"Detail: {exc}"
                ) from exc

    try:
        os.replace(str(staging), str(dest_bin))
    except OSError as exc:
        staging.unlink(missing_ok=True)
        raise UpdateError(
            f"Cannot finalize CLI binary at {dest_bin}: {exc}\n"
            "Reinstall with: irm https://hordricjr.github.io/Akomagni/install/windows | iex"
        ) from exc

    try:
        if backup.exists():
            backup.unlink()
    except OSError:
        pass  # leftover .old is removed on the next successful update


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

    git = _git_exe()
    previous = _git_ref(root)
    branch = os.environ.get("AKOMAGNI_BRANCH", "main").strip() or "main"
    # Shallow clones often lack other remote branches; write origin/<branch> explicitly.
    fetch = subprocess.run(  # nosec B603
        [
            git,
            "-C",
            str(root),
            "fetch",
            "--depth",
            "1",
            "origin",
            f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode != 0:
        detail = (fetch.stderr or fetch.stdout or "").strip()
        raise UpdateError(f"git fetch failed: {detail}")

    checkout = subprocess.run(  # nosec B603
        [git, "-C", str(root), "checkout", "-f", "-B", branch, f"origin/{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if checkout.returncode != 0:
        detail = (checkout.stderr or checkout.stdout or "").strip()
        raise UpdateError(f"git checkout {branch} failed: {detail}")

    reset = subprocess.run(  # nosec B603
        [git, "-C", str(root), "reset", "--hard", f"origin/{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if reset.returncode != 0:
        detail = (reset.stderr or reset.stdout or "").strip()
        raise UpdateError(f"git reset failed: {detail}")

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
    # Package code is already updated; shim replace is best-effort on Windows.
    try:
        _install_cli_binary(source_bin, dest_bin)
    except UpdateError as exc:
        if platform.system() == "Windows":
            from rich.console import Console

            Console().print(
                f"[yellow]Warning:[/] launcher shim not refreshed ({exc}).\n"
                "Code update succeeded. Open a [bold]new[/] PowerShell and run:\n"
                "  irm https://hordricjr.github.io/Akomagni/install/windows | iex"
            )
        else:
            raise
    except OSError as exc:
        if platform.system() == "Windows":
            from rich.console import Console

            Console().print(
                f"[yellow]Warning:[/] launcher shim locked ({exc}). "
                "Code update succeeded — reopen a new terminal or reinstall."
            )
        else:
            raise UpdateError(
                f"Failed to install CLI binary to {dest_bin}: {exc}\n"
                "Retry after closing other akomagni processes, or reinstall with the Windows one-liner."
            ) from exc

    current = _git_ref(root)
    return UpdateResult(
        install_dir=root,
        bin_path=dest_bin,
        previous_ref=previous,
        current_ref=current,
    )
