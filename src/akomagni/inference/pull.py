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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("Downloading from Hugging Face…", total=None)
        cached = hf_hub_download(
            repo_id=entry.repo_id,
            filename=entry.filename,
            local_dir=str(dest_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )

    cached_path = Path(cached)
    if cached_path.resolve() != dest_file.resolve():
        shutil.copy2(cached_path, dest_file)

    console.print(f"[green]Downloaded[/] → {dest_file}")
    return dest_file


def format_catalog_entry(entry: ModelCatalogEntry) -> str:
    return f"{entry.name} [{entry.profile}] — {entry.description}"
