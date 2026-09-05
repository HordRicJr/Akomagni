"""Download GGUF models from Hugging Face Hub."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from akomagni.core.registry.catalog import ModelCatalogEntry, resolve_catalog_name

console = Console()

_HF_SPEC = re.compile(
    r"^(?P<repo>[^/]+/[^/:]+)(?::(?P<file>.+\.gguf))?$",
    re.IGNORECASE,
)


class ModelPullError(RuntimeError):
    """Raised when a model cannot be downloaded."""


def _format_hub_error(exc: Exception, entry: ModelCatalogEntry) -> str:
    """Turn Hugging Face exceptions into a short actionable message."""
    name = type(exc).__name__
    text = str(exc)
    lower = text.lower()
    if "401" in text or "unauthorized" in lower or "invalid username" in lower:
        return (
            f"Download failed for {entry.repo_id}/{entry.filename} (401 Unauthorized).\n"
            "Connect Hugging Face once:\n"
            "  akomagni connect\n"
            "Or set HF_TOKEN, then retry:\n"
            f"  akomagni model pull {entry.repo_id}:{entry.filename}"
        )
    if "404" in text or "repository not found" in lower or name == "RepositoryNotFoundError":
        return (
            f"Model repo not found: {entry.repo_id}\n"
            f"File: {entry.filename}\n"
            "Use catalog names or owner/repo:file.gguf"
        )
    if "gated" in lower:
        return (
            f"Repo {entry.repo_id} is gated. Accept the license on Hugging Face, then:\n"
            "  akomagni connect\n"
            f"  akomagni model pull {entry.repo_id}:{entry.filename}"
        )
    return f"Download failed: {text[:400]}"


def _pick_gguf_filename(repo_id: str, *, token: str | None) -> str:
    try:
        from huggingface_hub import list_repo_files
    except ImportError as exc:
        raise ModelPullError(
            "huggingface-hub is required for model pull.\n"
            "Install with: pip install 'akomagni[inference]'"
        ) from exc

    files = [
        f
        for f in list_repo_files(repo_id, repo_type="model", token=token)
        if f.lower().endswith(".gguf")
    ]
    if not files:
        raise ModelPullError(f"No .gguf files found in {repo_id}")
    preferred = [f for f in files if "q4_k_m" in f.lower() or "Q4_K_M" in f]
    return min(preferred or files, key=len)


def resolve_pull_entry(name: str, *, token: str | None = None) -> ModelCatalogEntry:
    """Resolve a catalog alias or ``owner/repo[:file.gguf]`` pull spec."""
    entry = resolve_catalog_name(name)
    if entry is not None:
        return entry

    match = _HF_SPEC.match(name.strip())
    if not match:
        raise ModelPullError(
            f"Unknown model '{name}'.\n"
            "Use a catalog name (akomagni model catalog) or Hugging Face:\n"
            "  akomagni model pull owner/repo:file.gguf"
        )

    repo_id = match.group("repo")
    filename = match.group("file")
    if not filename:
        filename = _pick_gguf_filename(repo_id, token=token)
    slug = repo_id.replace("/", "__").lower()
    return ModelCatalogEntry(
        name=slug,
        repo_id=repo_id,
        filename=filename,
        profile="custom",
        description=f"Custom Hugging Face GGUF from {repo_id}",
    )


def pull_model(
    name: str,
    *,
    models_dir: Path,
    force: bool = False,
    token: str | None = None,
) -> Path:
    """Download a catalog or arbitrary Hugging Face GGUF into *models_dir*."""
    from akomagni.core.onboarding import resolve_hf_token

    hub_token = token if token is not None else resolve_hf_token()
    entry = resolve_pull_entry(name, token=hub_token)

    dest_dir = models_dir / entry.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / entry.filename

    if dest_file.is_file() and not force:
        console.print(f"[green]Already downloaded:[/] {dest_file}")
        return dest_file

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ModelPullError(
            "huggingface-hub is required for model pull.\n"
            "Install with: pip install 'akomagni[inference]'"
        ) from exc

    console.print(
        f"[bold]Pulling[/] {entry.name}\n"
        f"  Repo : {entry.repo_id}\n"
        f"  File : {entry.filename}\n"
        f"  Dest : {dest_dir}"
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task("Downloading from Hugging Face…", total=None)
            cached = hf_hub_download(  # nosec B615
                repo_id=entry.repo_id,
                filename=entry.filename,
                revision="main",
                local_dir=str(dest_dir),
                token=hub_token,
            )
    except Exception as exc:
        raise ModelPullError(_format_hub_error(exc, entry)) from exc

    cached_path = Path(cached)
    if cached_path.resolve() != dest_file.resolve():
        shutil.copy2(cached_path, dest_file)

    console.print(f"[green]Downloaded[/] → {dest_file}")
    return dest_file


def format_catalog_entry(entry: ModelCatalogEntry) -> str:
    return f"{entry.name} [{entry.profile}] — {entry.description}"
