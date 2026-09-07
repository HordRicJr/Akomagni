"""Bootstrap Microsoft Entra auth for Foundry (azure-identity + Azure CLI)."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from akomagni.inference.foundry import ENTRA_SCOPE, get_foundry_entra_token

ProgressFn = Callable[[str], None]


@dataclass
class EntraSetupResult:
    identity_installed: bool = False
    az_available: bool = False
    az_logged_in: bool = False
    token_ok: bool = False
    messages: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.token_ok


def azure_identity_available() -> bool:
    try:
        importlib.import_module("azure.identity")
        return True
    except ImportError:
        return False


def find_az_cli() -> str | None:
    return shutil.which("az")


def _pip_install_azure_identity(*, timeout: float = 180.0) -> tuple[bool, str]:
    """Install azure-identity into the current interpreter."""
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "azure-identity>=1.15",
    ]
    try:
        completed = subprocess.run(  # nosec B603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "pip install azure-identity timed out"
    except OSError as exc:
        return False, f"pip install failed: {exc}"

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return False, detail[:400] or f"pip exit {completed.returncode}"

    # Ensure fresh import after install
    for name in list(sys.modules):
        if name == "azure" or name.startswith("azure."):
            sys.modules.pop(name, None)
    if not azure_identity_available():
        return False, "azure-identity installed but still not importable"
    return True, "azure-identity ready"


def install_azure_identity_background(
    *,
    on_progress: ProgressFn | None = None,
    timeout: float = 180.0,
) -> tuple[bool, str]:
    """Run pip install in a worker thread so the CLI stays responsive to progress."""
    result: dict[str, Any] = {"ok": False, "detail": ""}

    def _worker() -> None:
        ok, detail = _pip_install_azure_identity(timeout=timeout)
        result["ok"] = ok
        result["detail"] = detail

    if on_progress:
        on_progress("Installing azure-identity in background…")
    thread = threading.Thread(target=_worker, name="akomagni-azure-identity", daemon=True)
    thread.start()
    # Wait with soft progress ticks
    started = time.monotonic()
    while thread.is_alive():
        if time.monotonic() - started > timeout + 5:  # pragma: no cover - watchdog
            return False, "azure-identity install still running after timeout"
        time.sleep(0.4)
    return bool(result["ok"]), str(result["detail"])


def az_account_logged_in(*, az_bin: str | None = None) -> bool:
    binary = az_bin or find_az_cli()
    if not binary:
        return False
    try:
        completed = subprocess.run(  # nosec B603
            [binary, "account", "show", "-o", "none"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def run_az_login(
    *,
    az_bin: str | None = None,
    on_progress: ProgressFn | None = None,
    timeout: float = 300.0,
) -> tuple[bool, str]:
    """Launch ``az login`` (browser / device flow). Must stay attached to the TTY."""
    binary = az_bin or find_az_cli()
    if not binary:
        return (
            False,
            "Azure CLI (az) not found on PATH — install from https://aka.ms/installazurecliwindows",
        )

    if on_progress:
        on_progress("Launching az login (complete sign-in in the browser)…")

    env = os.environ.copy()
    try:
        # Do not capture stdout/stderr so the browser/device code UI works.
        completed = subprocess.run(  # nosec B603
            [binary, "login"],
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "az login timed out"
    except OSError as exc:
        return False, f"az login failed: {exc}"

    if completed.returncode != 0:
        return False, f"az login exited with code {completed.returncode}"
    if not az_account_logged_in(az_bin=binary):
        return False, "az login finished but no account is active"
    return True, "Azure CLI session ready"


def verify_entra_token(*, scope: str = ENTRA_SCOPE) -> tuple[bool, str]:
    try:
        token = get_foundry_entra_token(scope=scope)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if not token:
        return False, "empty Entra token"
    return True, "Entra token acquired"


def ensure_foundry_entra(
    *,
    login_if_needed: bool = True,
    on_progress: ProgressFn | None = None,
    install_timeout: float = 180.0,
    login_timeout: float = 300.0,
) -> EntraSetupResult:
    """Ensure azure-identity is installed and Azure CLI can mint Foundry tokens.

    Steps:
    1. Install ``azure-identity`` in a background thread if missing.
    2. Detect Azure CLI; if not logged in and *login_if_needed*, run ``az login``.
    3. Verify ``DefaultAzureCredential`` can obtain ``https://ai.azure.com/.default``.
    """
    result = EntraSetupResult()
    log = result.messages.append

    def progress(msg: str) -> None:
        log(msg)
        if on_progress:
            on_progress(msg)

    # 1) azure-identity
    if azure_identity_available():
        result.identity_installed = True
        progress("azure-identity already available")
    else:
        ok, detail = install_azure_identity_background(
            on_progress=progress,
            timeout=install_timeout,
        )
        result.identity_installed = ok
        if ok:
            progress(detail)
        else:
            result.error = f"Could not install azure-identity: {detail}"
            progress(result.error)
            return result

    # 2) Azure CLI session (preferred path for DefaultAzureCredential on desktops)
    az_bin = find_az_cli()
    result.az_available = bool(az_bin)
    if not az_bin:
        progress("Azure CLI not found — DefaultAzureCredential may still work via other sources")
    else:
        if az_account_logged_in(az_bin=az_bin):
            result.az_logged_in = True
            progress("Azure CLI already logged in")
        elif login_if_needed:
            ok, detail = run_az_login(
                az_bin=az_bin,
                on_progress=progress,
                timeout=login_timeout,
            )
            result.az_logged_in = ok
            if ok:
                progress(detail)
            else:
                # Not fatal yet — VS Code / env credentials might still work
                progress(f"az login issue: {detail} (will still try DefaultAzureCredential)")
        else:
            progress("Azure CLI present but not logged in (login skipped)")

    # 3) Token probe
    ok, detail = verify_entra_token()
    result.token_ok = ok
    if ok:
        progress(detail)
    else:
        result.error = (
            f"Entra token failed: {detail}. "
            "Run: az login  (or set AZURE_OPENAI_API_KEY for key auth)"
        )
        progress(result.error)
    return result
