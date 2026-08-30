"""llama.cpp llama-server subprocess wrapper."""

from __future__ import annotations

import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

LLAMA_SERVER_NAMES = ("llama-server", "llama-server.exe")
DEFAULT_CTX_SIZE = 4096
HEALTH_PATHS = ("/health", "/v1/models")


class LlamaServerError(RuntimeError):
    """Raised when llama-server cannot start or become healthy."""


def find_llama_server(binary: str | None = None) -> Path | None:
    """Locate llama-server binary from config path or PATH."""
    if binary:
        path = Path(binary).expanduser()
        if path.is_file():
            return path
    for name in LLAMA_SERVER_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def list_local_models(models_dir: Path) -> list[Path]:
    """Return downloaded .gguf files under *models_dir*."""
    if not models_dir.is_dir():
        return []
    return sorted(models_dir.rglob("*.gguf"))


def resolve_model_path(
    model: str | None,
    *,
    models_dir: Path,
) -> Path | None:
    """Resolve a model name or path to a local .gguf file."""
    if model:
        candidate = Path(model).expanduser()
        if candidate.is_file() and candidate.suffix.lower() == ".gguf":
            return candidate
        by_name = models_dir / model
        if by_name.is_file():
            return by_name
        for path in list_local_models(models_dir):
            if path.name == model or path.stem.lower() == model.lower():
                return path
    local = list_local_models(models_dir)
    return local[0] if local else None


def build_server_command(
    binary: Path,
    *,
    model_path: Path,
    host: str,
    port: int,
    ctx_size: int = DEFAULT_CTX_SIZE,
    n_gpu_layers: int = -1,
) -> list[str]:
    """Build llama-server argv."""
    cmd = [
        str(binary),
        "--model",
        str(model_path),
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(ctx_size),
    ]
    if n_gpu_layers >= 0:
        cmd.extend(["--n-gpu-layers", str(n_gpu_layers)])
    return cmd


def wait_for_health(
    host: str,
    port: int,
    *,
    timeout: float = 60.0,
    poll_interval: float = 0.5,
) -> str:
    """Poll OpenAI/health endpoints until llama-server is ready."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for path in HEALTH_PATHS:
            url = f"http://{host}:{port}{path}"
            try:
                with urllib.request.urlopen(url, timeout=2) as response:  # nosec B310
                    if response.status == 200:
                        return url
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
        time.sleep(poll_interval)
    raise LlamaServerError(
        f"llama-server did not become healthy within {timeout:.0f}s (last error: {last_error})"
    )


def run_llama_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model_path: Path,
    binary: Path,
    ctx_size: int = DEFAULT_CTX_SIZE,
    n_gpu_layers: int = -1,
    health_timeout: float = 60.0,
) -> None:
    """Start llama-server, wait for health, block until interrupted."""
    cmd = build_server_command(
        binary,
        model_path=model_path,
        host=host,
        port=port,
        ctx_size=ctx_size,
        n_gpu_layers=n_gpu_layers,
    )
    console.print(
        f"[bold]Akomagni inference[/] — starting llama-server\n"
        f"  Model : {model_path}\n"
        f"  API   : http://{host}:{port}/v1"
    )
    process = subprocess.Popen(  # nosec B603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def _shutdown(*_args: Any) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    previous_int = signal.signal(signal.SIGINT, _shutdown)
    previous_term = None
    if hasattr(signal, "SIGTERM"):
        previous_term = signal.signal(signal.SIGTERM, _shutdown)

    try:
        try:
            health_url = wait_for_health(host, port, timeout=health_timeout)
        except LlamaServerError:
            output = ""
            if process.stdout:
                output = process.stdout.read(4000)
            process.terminate()
            raise LlamaServerError(
                f"llama-server failed health check.\nCommand: {' '.join(cmd)}\nOutput:\n{output}"
            ) from None

        console.print(f"[green]Ready[/] — {health_url}")
        console.print("[dim]Ctrl+C to stop.[/]")
        while process.poll() is None:
            time.sleep(0.2)
        if process.returncode not in (0, -signal.SIGINT, 130):
            raise LlamaServerError(f"llama-server exited with code {process.returncode}")
    finally:
        _shutdown()
        signal.signal(signal.SIGINT, previous_int)
        if previous_term is not None:
            signal.signal(signal.SIGTERM, previous_term)


def serve_inference(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
    binary: str | None = None,
    models_dir: Path,
    ctx_size: int = DEFAULT_CTX_SIZE,
    n_gpu_layers: int = -1,
) -> None:
    """High-level entry: resolve binary + model, then run server."""
    server_bin = find_llama_server(binary)
    if not server_bin:
        raise LlamaServerError(
            "llama-server not found.\n"
            "Install llama.cpp and ensure `llama-server` is on PATH, or set "
            "inference.binary in ~/.akomagni/config.yaml.\n"
            "See: https://github.com/ggerganov/llama.cpp"
        )

    model_path = resolve_model_path(model, models_dir=models_dir)
    if not model_path:
        raise LlamaServerError(
            "No GGUF model found.\n"
            "Download one with: [bold]akomagni model pull <name>[/bold]\n"
            "List catalog: akomagni model catalog"
        )

    run_llama_server(
        host=host,
        port=port,
        model_path=model_path,
        binary=server_bin,
        ctx_size=ctx_size,
        n_gpu_layers=n_gpu_layers,
    )
