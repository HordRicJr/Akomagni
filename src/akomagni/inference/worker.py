"""Background llama-server worker for hot-swapping GGUF models."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from akomagni.core.config import DATA_DIR
from akomagni.inference.llama import (
    LlamaServerError,
    build_server_command,
    find_llama_server,
    resolve_model_path,
    wait_for_health,
)

WORKER_STATE_PATH = DATA_DIR / "inference" / "worker.yaml"


@dataclass(frozen=True)
class WorkerState:
    pid: int
    model_path: str
    host: str
    port: int


@dataclass(frozen=True)
class HotSwapResult:
    swapped: bool
    model_path: Path | None
    message: str
    worker: WorkerState | None = None


def _load_state() -> dict[str, Any]:
    if not WORKER_STATE_PATH.is_file():
        return {}
    with WORKER_STATE_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _save_state(state: dict[str, Any]) -> None:
    WORKER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WORKER_STATE_PATH.open("w", encoding="utf-8") as handle:
        yaml.dump(state, handle, default_flow_style=False)


def read_worker_state() -> WorkerState | None:
    data = _load_state()
    pid = data.get("pid")
    model_path = data.get("model_path")
    if not isinstance(pid, int) or not model_path:
        return None
    return WorkerState(
        pid=pid,
        model_path=str(model_path),
        host=str(data.get("host", "127.0.0.1")),
        port=int(data.get("port", 8787)),
    )


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_worker() -> bool:
    """Stop background worker if running. Returns True when a process was stopped."""
    state = read_worker_state()
    if state is None or not _process_alive(state.pid):
        _save_state({})
        return False
    try:
        os.kill(state.pid, signal.SIGTERM)
        for _ in range(20):
            if not _process_alive(state.pid):
                break
            time.sleep(0.1)
        if _process_alive(state.pid):
            if hasattr(signal, "SIGKILL"):
                os.kill(state.pid, signal.SIGKILL)
            else:
                os.kill(state.pid, signal.SIGTERM)
    except OSError:
        pass
    _save_state({})
    return True


def start_worker_background(
    *,
    model_path: Path,
    host: str,
    port: int,
    binary: Path,
    ctx_size: int = 4096,
    n_gpu_layers: int = -1,
    health_timeout: float = 60.0,
) -> WorkerState:
    """Start llama-server detached and persist worker state."""
    stop_worker()
    cmd = build_server_command(
        binary,
        model_path=model_path,
        host=host,
        port=port,
        ctx_size=ctx_size,
        n_gpu_layers=n_gpu_layers,
    )
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    process = subprocess.Popen(  # nosec B603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    wait_for_health(host, port, timeout=health_timeout)
    state = WorkerState(pid=process.pid, model_path=str(model_path), host=host, port=port)
    _save_state(
        {
            "pid": state.pid,
            "model_path": state.model_path,
            "host": state.host,
            "port": state.port,
        }
    )
    return state


def hot_swap_model(
    model: str,
    *,
    models_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    binary: str | None = None,
    ctx_size: int = 4096,
    n_gpu_layers: int = -1,
) -> HotSwapResult:
    """Stop the current worker (if any) and start *model* in the background."""
    model_path = resolve_model_path(model, models_dir=models_dir)
    if model_path is None:
        return HotSwapResult(
            swapped=False,
            model_path=None,
            message=f"Model not found locally: {model}. Run: akomagni model pull {model}",
        )

    server_bin = find_llama_server(binary)
    if not server_bin:
        return HotSwapResult(
            swapped=False,
            model_path=model_path,
            message="llama-server not found on PATH",
        )

    current = read_worker_state()
    if (
        current is not None
        and _process_alive(current.pid)
        and Path(current.model_path).resolve() == model_path.resolve()
    ):
        return HotSwapResult(
            swapped=False,
            model_path=model_path,
            message="Model already loaded",
            worker=current,
        )

    try:
        worker = start_worker_background(
            model_path=model_path,
            host=host,
            port=port,
            binary=server_bin,
            ctx_size=ctx_size,
            n_gpu_layers=n_gpu_layers,
        )
    except (LlamaServerError, OSError) as exc:
        return HotSwapResult(swapped=False, model_path=model_path, message=str(exc))

    return HotSwapResult(
        swapped=True,
        model_path=model_path,
        message=f"Loaded {model_path.name} on http://{host}:{port}/v1",
        worker=worker,
    )
