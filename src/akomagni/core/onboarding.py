"""First-run / new-project onboarding for Akomagni CLI."""

from __future__ import annotations

import os
import shutil
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

_SKIP_DIR_NAMES = {
    ".akomagni",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
}


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
    """Canonical folder for user projects (``C:\\Akomagni`` on Windows).

    Override with ``AKOMAGNI_PROJECTS_ROOT`` (used in tests).
    """
    override = (os.environ.get("AKOMAGNI_PROJECTS_ROOT") or "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path("C:/Akomagni")
    return Path.home() / "Akomagni"


def ensure_projects_root() -> Path:
    """Create the projects root if missing; return the resolved path."""
    root = default_projects_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise ProjectPathError(
            f"Cannot create projects folder at {root} (access denied).\n"
            "Set AKOMAGNI_PROJECTS_ROOT to a writable directory, or run as a user "
            "that can create C:\\Akomagni."
        ) from exc
    except OSError as exc:
        raise ProjectPathError(f"Cannot create projects folder at {root}: {exc}") from exc
    return root.resolve()


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
    """Resolve a user project path under the Akomagni projects root.

    Absolute paths are kept as-is. Relative names (``./app_test``, ``app_test``)
    always land under :func:`default_projects_root` (``C:\\Akomagni\\…``), so a
    shell opened in System32 never tries to create folders there.
    """
    raw = Path(str(project).strip() or ".")
    if raw.is_absolute():
        return raw.expanduser().resolve()

    ensure_projects_root()
    # Normalize ``./app_test`` / ``app_test`` / ``nested/app`` → under projects root
    name = Path(*raw.parts) if raw.parts else Path("app")
    # Drop leading ``.`` segments from ``./x``
    parts = [p for p in name.parts if p not in {".", ""}]
    if not parts or parts == ["."]:
        base = (start or Path.cwd()).resolve()
        if is_unsafe_cwd(base):
            return (default_projects_root() / "app").resolve()
        return base
    return (default_projects_root().joinpath(*parts)).expanduser().resolve()


def project_has_content(path: Path) -> bool:
    """True when the folder exists and already contains user/project data."""
    root = path.expanduser()
    if not root.is_dir():
        return False
    if (root / ".akomagni").is_dir():
        return True
    try:
        return any(root.iterdir())
    except OSError:
        return False


def summarize_project_files(root: Path, *, max_files: int = 40) -> str:
    """Compact file list for the model when continuing an existing project."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        return f"Project root: {root} (empty / not created yet)."

    lines: list[str] = [f"Project root: {root}"]
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.lower() in _SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        lines.append(f"- {rel}")
        count += 1
        if count >= max_files:
            lines.append(f"… ({max_files}+ files; use fs_list / fs_read for more)")
            break
    if count == 0:
        lines.append("- (no user files yet — only workspace markers)")
    return "\n".join(lines)


def choose_existing_project(*, root: Path, prompt: PromptFn) -> Path:
    """Ask whether to modify, rename, or delete an existing project folder."""
    print(f"Project already exists: {root}")
    print("  [m]odify  — continue and work with existing files")
    print("  [n]ew     — create another project under the Akomagni folder")
    print("  [d]elete  — remove this project and start fresh")
    while True:
        choice = prompt("Choice [m/n/d]").strip().lower() or "m"
        if choice in {"m", "modify", "mod", "continue", "c"}:
            return root
        if choice in {"n", "new", "autre", "other"}:
            name = prompt("New project name").strip()
            if not name:
                print("Name required.")
                continue
            candidate = resolve_project_path(name)
            if project_has_content(candidate):
                root = candidate
                print(f"Project already exists: {root}")
                continue
            return candidate
        if choice in {"d", "delete", "del", "rm", "supprimer"}:
            confirm = prompt(f"Type DELETE to remove {root}").strip()
            if confirm != "DELETE":
                print("Delete cancelled.")
                continue
            if root.exists():
                shutil.rmtree(root)
            return root
        print("Choose m, n, or d.")


def scaffold_project(path: Path) -> Path:
    """Create a project folder with ``.akomagni/`` workspace markers."""
    root = path.expanduser().resolve()
    try:
        # Ensure parent projects root exists when under the default tree
        try:
            projects = default_projects_root().resolve()
            if projects in root.parents or root == projects:
                ensure_projects_root()
        except ProjectPathError:
            pass
        root.mkdir(parents=True, exist_ok=True)
        (root / ".akomagni").mkdir(parents=True, exist_ok=True)
        (root / ".akomagni" / "memory" / "learnings").mkdir(parents=True, exist_ok=True)
        (root / ".akomagni" / "workflow").mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        hint = default_projects_root() / "app_test"
        raise ProjectPathError(
            f"Cannot create project at {root} (access denied).\n"
            "Projects default to C:\\Akomagni on Windows, e.g.:\n"
            f"  akomagni run cli --project {hint.name}\n"
            f"Resolved path: {hint}"
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

    ensure_projects_root()
    if project:
        root = resolve_project_path(project)
    else:
        default_name = "app"
        project_input = prompt(f"Project name [{default_name}] (under {default_projects_root()})")
        root = resolve_project_path(project_input.strip() or default_name)

    created = not project_has_content(root)
    if not created:
        root = choose_existing_project(root=root, prompt=prompt)
        created = not project_has_content(root)

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
