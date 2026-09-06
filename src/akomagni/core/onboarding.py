"""First-run / new-project onboarding for Akomagni CLI."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from akomagni.core.config import load_config
from akomagni.inference.connect import (
    ConnectError,
    connect_provider,
    normalize_provider,
    save_config,
)

PromptFn = Callable[[str], str]


@dataclass(frozen=True)
class SessionSetup:
    """Result of interactive session setup."""

    provider: str
    project_root: Path
    created_project: bool
    connected: bool


class ProjectPathError(RuntimeError):
    """Raised when a project path cannot be created safely."""


def needs_provider_onboarding(config: dict[str, Any] | None = None) -> bool:
    cfg = config or load_config()
    onboarding = cfg.get("onboarding") or {}
    return not bool(onboarding.get("provider_ready"))


def mark_provider_ready(provider: str) -> None:
    cfg = load_config()
    onboarding = dict(cfg.get("onboarding") or {})
    onboarding["provider_ready"] = True
    onboarding["provider"] = provider
    cfg["onboarding"] = onboarding
    save_config(cfg)


def default_projects_root() -> Path:
    """Writable base for relative ``--project`` paths when cwd is unsafe."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "akomagni" / "projects"
    return Path.home() / "akomagni-projects"


def is_unsafe_cwd(path: Path | None = None) -> bool:
    """True when *path* (default: cwd) is a protected system directory."""
    current = (path or Path.cwd()).resolve()
    # Drive root (C:\)
    if current.parent == current:
        return True
    for part in current.parts:
        low = part.lower()
        if low in {"windows", "system32", "syswow64", "programdata"}:
            return True
        if low.startswith("program files"):
            return True
    return False


def resolve_project_path(project: str | Path, *, start: Path | None = None) -> Path:
    """Resolve a user project path, avoiding protected system folders.

    Relative paths use *start* (or cwd). If that base is unsafe (e.g. System32),
    they are placed under :func:`default_projects_root` instead.
    """
    raw = Path(str(project).strip() or ".")
    base = (start or Path.cwd()).resolve()
    if raw.is_absolute():
        return raw.expanduser().resolve()
    if is_unsafe_cwd(base):
        return (default_projects_root() / raw).expanduser().resolve()
    return (base / raw).expanduser().resolve()


def scaffold_project(path: Path) -> Path:
    """Create a project folder with ``.akomagni/`` workspace markers."""
    root = path.expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".akomagni").mkdir(parents=True, exist_ok=True)
        (root / ".akomagni" / "memory" / "learnings").mkdir(parents=True, exist_ok=True)
        (root / ".akomagni" / "workflow").mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        hint = default_projects_root() / "app_test"
        raise ProjectPathError(
            f"Cannot create project at {root} (access denied).\n"
            "Use a writable folder, e.g.:\n"
            "  cd %USERPROFILE%\\Documents\n"
            "  akomagni run cli --project ./app_test\n"
            f"Or an absolute path:\n"
            f"  akomagni run cli --project {hint}"
        ) from exc
    state = root / ".akomagni" / "workflow" / "state.yaml"
    if not state.is_file():
        state.write_text(
            yaml.safe_dump({"phase": "start", "completed_skills": []}, sort_keys=False),
            encoding="utf-8",
        )
    return root


def save_hf_token(token: str) -> None:
    """Persist a Hugging Face Hub token for gated GGUF downloads."""
    cleaned = token.strip()
    if not cleaned:
        raise ConnectError("Hugging Face token cannot be empty.")
    cfg = load_config()
    block = dict(cfg.get("huggingface") or {})
    block["token_env"] = "HF_TOKEN"  # nosec B105 — env var name, not a secret
    block["api_key"] = cleaned
    cfg["huggingface"] = block
    save_config(cfg)


def resolve_hf_token(config: dict[str, Any] | None = None) -> str | None:
    """Resolve HF Hub token from config or environment."""
    cfg = config or load_config()
    block = cfg.get("huggingface") or {}
    inline = block.get("api_key")
    if inline and str(inline).strip():
        return str(inline).strip()
    for key in (str(block.get("token_env") or "HF_TOKEN"), "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    return None


def run_connect_wizard(*, prompt: PromptFn, include_hf: bool = True) -> dict[str, Any]:
    """One simple flow: pick provider, enter keys, optional HF token."""
    choice = prompt("Provider [local / rodium / foundry]").strip().lower() or "local"
    if choice in {"foundry", "azure"}:
        provider = "azure"
    elif choice in {"rodium", "local"}:
        provider = choice
    else:
        raise ConnectError("Choose local, rodium, or foundry.")

    result: dict[str, Any] = {"provider": provider, "hf_saved": False}

    if provider == "local":
        connect_provider("local", sync_ide=False)
    elif provider == "rodium":
        key = prompt("Rodium API key (rd_sk_…)")
        connect_provider("rodium", api_key=key, sync_ide=True)
        try:
            from akomagni.inference.model_picker import interactive_pick_model

            print("Choose how Rodium picks models (Auto recommended).")
            interactive_pick_model(prompt=prompt)
        except OSError:
            pass
    else:
        url = prompt("Azure Foundry URL (…/openai/v1/)")
        key = prompt("Azure API key")
        connect_provider("azure", base_url=url, api_key=key, sync_ide=True)

    if include_hf:
        hf = prompt("Hugging Face token (optional, Enter to skip)")
        if hf.strip():
            save_hf_token(hf)
            result["hf_saved"] = True

    mark_provider_ready(provider if provider != "azure" else "foundry")
    result["provider"] = "foundry" if provider == "azure" else provider
    try:
        from akomagni.skills.link import ensure_skills_linked

        ensure_skills_linked()
    except OSError:
        pass
    return result


def run_session_setup(
    *,
    prompt: PromptFn,
    project: str | None = None,
    provider: str | None = None,
    skip_provider: bool = False,
) -> SessionSetup:
    """Ask for provider (if needed) and project path, then scaffold."""
    cfg = load_config()
    chosen = provider
    connected = False

    if not skip_provider and (chosen or needs_provider_onboarding(cfg)):
        if not chosen:
            wizard = run_connect_wizard(prompt=prompt, include_hf=True)
            chosen = str(wizard["provider"])
            connected = True
        else:
            normalized = normalize_provider("foundry" if chosen == "foundry" else chosen)
            if normalized == "local":
                connect_provider("local", sync_ide=False)
            elif normalized == "rodium":
                key = prompt("Rodium API key (rd_sk_…)")
                connect_provider("rodium", api_key=key)
            else:
                url = prompt("Azure Foundry URL (…/openai/v1/)")
                key = prompt("Azure API key")
                connect_provider("azure", base_url=url, api_key=key)
            mark_provider_ready(chosen)
            connected = True
    elif chosen:
        connected = False

    if project:
        root = resolve_project_path(project)
    else:
        default_base = default_projects_root() if is_unsafe_cwd() else Path.cwd()
        project_input = prompt(f"Project folder [{default_base / 'app'}]")
        root = resolve_project_path(project_input.strip() or str(default_base / "app"))
    created = not (root / ".akomagni").is_dir()
    scaffold_project(root)
    try:
        from akomagni.skills.link import ensure_skills_linked

        ensure_skills_linked(root)
    except OSError:
        pass

    provider_name = chosen or str((load_config().get("inference") or {}).get("provider", "local"))
    if provider_name == "azure":
        provider_name = "foundry"
    return SessionSetup(
        provider=provider_name,
        project_root=root.resolve(),
        created_project=created,
        connected=connected,
    )
