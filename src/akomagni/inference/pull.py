"""Download GGUF models from Hugging Face Hub."""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from akomagni.core.registry.catalog import ModelCatalogEntry, resolve_catalog_name

console = Console()


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
            "If the repo is gated/private, login first:\n"
            "  huggingface-cli login\n"
            "Or set HF_TOKEN / HUGGING_FACE_HUB_TOKEN, then retry:\n"
            f"  akomagni model pull {entry.name}"
        )
    if "404" in text or "repository not found" in lower or name == "RepositoryNotFoundError":
        return (
            f"Model repo not found: {entry.repo_id}\n"
            f"File: {entry.filename}\n"
            "Run: akomagni model catalog"
        )
    if "gated" in lower:
        return (
            f"Repo {entry.repo_id} is gated. Accept the license on Hugging Face, then:\n"
            "  huggingface-cli login\n"
            f"  akomagni model pull {entry.name}"
        )
    return f"Download failed: {text[:400]}"


def pull_model(
    name: str,
    *,
    models_dir: Path,
    force: bool = False,
) -> Path:
    """Download a catalog model into *models_dir* with resume support."""
    entry = resolve_catalog_name(name)
    if not entry:
        raise ModelPullError(
            f"Unknown model '{name}'. Run [bold]akomagni model catalog[/bold] for options."
        )

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
            cached = hf_hub_download(  # nosec B615 — catalog pins repo+filename; revision=main
                repo_id=entry.repo_id,
                filename=entry.filename,
                revision="main",
                local_dir=str(dest_dir),
            )
    except Exception as exc:  # noqa: BLE001 — surface hub errors cleanly to CLI
        raise ModelPullError(_format_hub_error(exc, entry)) from exc

    cached_path = Path(cached)
    if cached_path.resolve() != dest_file.resolve():
        shutil.copy2(cached_path, dest_file)

    console.print(f"[green]Downloaded[/] → {dest_file}")
    return dest_file


def format_catalog_entry(entry: ModelCatalogEntry) -> str:
    return f"{entry.name} [{entry.profile}] — {entry.description}"
