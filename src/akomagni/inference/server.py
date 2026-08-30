"""Local inference server — llama.cpp llama-server wrapper."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from akomagni.core.config import MODELS_DIR, load_config
from akomagni.inference.llama import LlamaServerError, serve_inference

console = Console()


def serve_stub(*, host: str = "127.0.0.1", port: int = 8787) -> None:
    """Legacy stub kept for tests and offline fallback messaging."""
    console.print(
        f"[yellow]Akomagni inference[/] — stub v0.1\n"
        f"API OpenAI-compatible prévue sur [bold]http://{host}:{port}[/]\n"
        "Prochaine étape : brancher llama-server / llama.cpp.\n"
        "Arrêt (rien à écouter pour l'instant)."
    )


def serve(
    *,
    host: str | None = None,
    port: int | None = None,
    model: str | None = None,
    binary: str | None = None,
    models_dir: Path | None = None,
) -> None:
    """Start llama-server subprocess with health check."""
    cfg = load_config()
    inference = cfg.get("inference", {})
    host = host or inference.get("host", "127.0.0.1")
    port = port or inference.get("port", 8787)
    binary = binary or inference.get("binary")
    model = model or inference.get("default_model")
    models_dir = models_dir or MODELS_DIR
    ctx_size = int(inference.get("ctx_size", 4096))
    n_gpu_layers = int(inference.get("n_gpu_layers", -1))

    try:
        serve_inference(
            host=host,
            port=port,
            model=model,
            binary=binary,
            models_dir=models_dir,
            ctx_size=ctx_size,
            n_gpu_layers=n_gpu_layers,
        )
    except LlamaServerError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(1) from exc
