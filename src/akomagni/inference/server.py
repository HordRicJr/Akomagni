"""Local inference server (OpenAI-compatible API stub)."""

from __future__ import annotations

from rich.console import Console

console = Console()


def serve_stub(*, host: str = "127.0.0.1", port: int = 8787) -> None:
    console.print(
        f"[yellow]Akomagni inference[/] — stub v0.1\n"
        f"API OpenAI-compatible prévue sur [bold]http://{host}:{port}[/]\n"
        "Prochaine étape : brancher llama-server / llama.cpp.\n"
        "Arrêt (rien à écouter pour l'instant)."
    )
