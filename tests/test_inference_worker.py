"""Tests for background inference worker hot-swap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from akomagni.inference.worker import (
    WorkerState,
    hot_swap_model,
    read_worker_state,
    start_worker_background,
    stop_worker,
)


def test_stop_worker_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr("akomagni.inference.worker.WORKER_STATE_PATH", tmp_path / "worker.yaml")
    assert stop_worker() is False


def test_stop_worker_running(tmp_path, monkeypatch):
    path = tmp_path / "worker.yaml"
    monkeypatch.setattr("akomagni.inference.worker.WORKER_STATE_PATH", path)
    path.write_text(
        "pid: 4242\nmodel_path: /models/test.gguf\nhost: 127.0.0.1\nport: 8787\n",
        encoding="utf-8",
    )
    with (
        patch("akomagni.inference.worker._process_alive", return_value=True),
        patch("akomagni.inference.worker.time.sleep"),
        patch("akomagni.inference.worker.os.kill") as kill,
    ):
        assert stop_worker() is True
    assert kill.called


def test_read_worker_state(tmp_path, monkeypatch):
    path = tmp_path / "worker.yaml"
    monkeypatch.setattr("akomagni.inference.worker.WORKER_STATE_PATH", path)
    path.write_text(
        "pid: 4242\nmodel_path: /models/test.gguf\nhost: 127.0.0.1\nport: 8787\n",
        encoding="utf-8",
    )
    state = read_worker_state()
    assert state == WorkerState(
        pid=4242, model_path="/models/test.gguf", host="127.0.0.1", port=8787
    )


def test_start_worker_background(tmp_path, monkeypatch):
    model = tmp_path / "test.gguf"
    model.write_text("gguf", encoding="utf-8")
    monkeypatch.setattr("akomagni.inference.worker.WORKER_STATE_PATH", tmp_path / "worker.yaml")
    proc = type("Proc", (), {"pid": 77})()
    with (
        patch("akomagni.inference.worker.stop_worker"),
        patch("akomagni.inference.worker.subprocess.Popen", return_value=proc),
        patch("akomagni.inference.worker.wait_for_health"),
    ):
        state = start_worker_background(
            model_path=model,
            host="127.0.0.1",
            port=8787,
            binary=Path("/bin/llama-server"),
        )
    assert state.pid == 77
    assert read_worker_state() is not None


def test_hot_swap_model_missing(tmp_path):
    result = hot_swap_model("missing-model", models_dir=tmp_path)
    assert result.swapped is False
    assert "not found" in result.message.lower()


def test_hot_swap_model_success(tmp_path):
    model = tmp_path / "phi-3.5-mini-instruct-q4.gguf"
    model.write_text("gguf", encoding="utf-8")
    worker = WorkerState(pid=99, model_path=str(model), host="127.0.0.1", port=8787)
    with (
        patch(
            "akomagni.inference.worker.find_llama_server", return_value=Path("/bin/llama-server")
        ),
        patch("akomagni.inference.worker.start_worker_background", return_value=worker),
        patch("akomagni.inference.worker.read_worker_state", return_value=None),
    ):
        result = hot_swap_model("phi-3.5-mini", models_dir=tmp_path)
    assert result.swapped is True
    assert result.worker is not None


def test_hot_swap_model_already_loaded(tmp_path):
    model = tmp_path / "phi-3.5-mini-instruct-q4.gguf"
    model.write_text("gguf", encoding="utf-8")
    current = WorkerState(pid=42, model_path=str(model), host="127.0.0.1", port=8787)
    with (
        patch(
            "akomagni.inference.worker.find_llama_server", return_value=Path("/bin/llama-server")
        ),
        patch("akomagni.inference.worker.read_worker_state", return_value=current),
        patch("akomagni.inference.worker._process_alive", return_value=True),
    ):
        result = hot_swap_model("phi-3.5-mini", models_dir=tmp_path)
    assert result.swapped is False
    assert "already loaded" in result.message.lower()
