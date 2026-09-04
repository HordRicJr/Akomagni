"""Inference module tests — llama-server wrapper and model pull."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from akomagni.core.registry.catalog import list_catalog, resolve_catalog_name
from akomagni.inference.llama import (
    LlamaServerError,
    build_server_command,
    find_llama_server,
    list_local_models,
    resolve_model_path,
    run_llama_server,
    serve_inference,
    wait_for_health,
)
from akomagni.inference.pull import ModelPullError, pull_model


def test_resolve_catalog_name_direct():
    assert resolve_catalog_name("LLAMA-3.2-3B") is not None


def test_list_catalog():
    assert len(list_catalog()) >= 4


def test_resolve_catalog_name():
    entry = resolve_catalog_name("qwen-coder-7b")
    assert entry is not None
    assert entry.name == "qwen2.5-coder-7b"


def test_find_llama_server_from_path(tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")
    assert find_llama_server(str(binary)) == binary


def test_find_llama_server_from_which():
    with patch("akomagni.inference.llama.shutil.which", return_value="/usr/bin/llama-server"):
        assert find_llama_server(None) == Path("/usr/bin/llama-server")


def test_find_llama_server_missing():
    with patch("akomagni.inference.llama.shutil.which", return_value=None):
        assert find_llama_server(None) is None


def test_build_server_command():
    cmd = build_server_command(
        Path("/bin/llama-server"),
        model_path=Path("/models/test.gguf"),
        host="127.0.0.1",
        port=8787,
        ctx_size=8192,
        n_gpu_layers=32,
    )
    assert Path(cmd[0]) == Path("/bin/llama-server")
    assert "--model" in cmd
    assert Path(cmd[cmd.index("--model") + 1]) == Path("/models/test.gguf")
    assert "--n-gpu-layers" in cmd


def test_resolve_model_path_by_file(tmp_path):
    model = tmp_path / "custom.gguf"
    model.write_text("gguf", encoding="utf-8")
    assert resolve_model_path(str(model), models_dir=tmp_path) == model


def test_resolve_model_path_first_local(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    first = models / "alpha.gguf"
    first.write_text("gguf", encoding="utf-8")
    assert resolve_model_path(None, models_dir=models) == first


def test_wait_for_health_success():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_response):
        url = wait_for_health("127.0.0.1", 8787, timeout=1.0, poll_interval=0.01)
    assert "8787" in url


def test_wait_for_health_timeout():
    with (
        patch("urllib.request.urlopen", side_effect=OSError("refused")),
        pytest.raises(LlamaServerError),
    ):
        wait_for_health("127.0.0.1", 8787, timeout=0.1, poll_interval=0.01)


def test_serve_inference_missing_binary(tmp_path):
    with (
        patch("akomagni.inference.llama.find_llama_server", return_value=None),
        pytest.raises(LlamaServerError, match="llama-server not found"),
    ):
        serve_inference(models_dir=tmp_path)


def test_serve_inference_missing_model(tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")
    with (
        patch("akomagni.inference.llama.find_llama_server", return_value=binary),
        pytest.raises(LlamaServerError, match="No GGUF model found"),
    ):
        serve_inference(models_dir=tmp_path)


def test_pull_model_unknown():
    with pytest.raises(ModelPullError, match="Unknown model"):
        pull_model("not-a-real-model", models_dir=Path("/tmp"))


def test_pull_model_missing_hub(tmp_path):
    with (
        patch.dict("sys.modules", {"huggingface_hub": None}),
        pytest.raises(ModelPullError, match="huggingface-hub"),
    ):
        pull_model("phi-3.5-mini", models_dir=tmp_path)


def test_pull_model_already_downloaded(tmp_path):
    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None
    dest = tmp_path / entry.name / entry.filename
    dest.parent.mkdir(parents=True)
    dest.write_text("gguf", encoding="utf-8")
    result = pull_model("phi-3.5-mini", models_dir=tmp_path)
    assert result == dest


def test_pull_model_downloads(tmp_path):
    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None
    assert entry.repo_id == "bartowski/Phi-3.5-mini-instruct-GGUF"
    assert entry.filename == "Phi-3.5-mini-instruct-Q4_K_M.gguf"
    dest = tmp_path / entry.name / entry.filename

    def fake_download(**_kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("gguf", encoding="utf-8")
        return str(dest)

    mock_hub = MagicMock()
    mock_hub.hf_hub_download = fake_download
    with patch.dict("sys.modules", {"huggingface_hub": mock_hub}):
        result = pull_model("phi-3.5-mini", models_dir=tmp_path)
    assert result == dest
    assert dest.is_file()


def test_pull_model_hub_401(tmp_path):
    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None

    def boom(**_kwargs):
        raise RuntimeError("401 Unauthorized Invalid username or password")

    mock_hub = MagicMock()
    mock_hub.hf_hub_download = boom
    with (
        patch.dict("sys.modules", {"huggingface_hub": mock_hub}),
        pytest.raises(ModelPullError, match="401 Unauthorized"),
    ):
        pull_model("phi-3.5-mini", models_dir=tmp_path)


def test_format_hub_error_variants():
    from akomagni.inference.pull import _format_hub_error

    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None
    assert "not found" in _format_hub_error(RuntimeError("Repository Not Found 404"), entry).lower()
    assert "gated" in _format_hub_error(RuntimeError("repo is gated"), entry).lower()
    assert "Download failed" in _format_hub_error(RuntimeError("network down"), entry)


def test_format_catalog_entry():
    from akomagni.inference.pull import format_catalog_entry

    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None
    text = format_catalog_entry(entry)
    assert entry.name in text
    assert entry.profile in text


def test_pull_model_copies_when_cache_path_differs(tmp_path):
    entry = resolve_catalog_name("phi-3.5-mini")
    assert entry is not None
    dest = tmp_path / entry.name / entry.filename
    cache = tmp_path / entry.name / "cache" / entry.filename

    def fake_download(**_kwargs):
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text("gguf", encoding="utf-8")
        return str(cache)

    mock_hub = MagicMock()
    mock_hub.hf_hub_download = fake_download
    with patch.dict("sys.modules", {"huggingface_hub": mock_hub}):
        result = pull_model("phi-3.5-mini", models_dir=tmp_path)
    assert result == dest
    assert dest.read_text(encoding="utf-8") == "gguf"


def test_list_local_models(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "a.gguf").write_text("x", encoding="utf-8")
    assert len(list_local_models(models)) == 1


def test_resolve_model_path_by_name(tmp_path):
    models = tmp_path / "models" / "phi-3.5-mini"
    models.mkdir(parents=True)
    model = models / "phi.gguf"
    model.write_text("x", encoding="utf-8")
    assert resolve_model_path("phi.gguf", models_dir=tmp_path / "models") == model


def test_serve_inference_delegates(tmp_path):
    model = tmp_path / "test.gguf"
    model.write_text("x", encoding="utf-8")
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")
    with (
        patch("akomagni.inference.llama.find_llama_server", return_value=binary),
        patch("akomagni.inference.llama.run_llama_server") as mock_run,
    ):
        serve_inference(model=str(model), models_dir=tmp_path)
    mock_run.assert_called_once()


def test_run_llama_server_success(tmp_path):
    model = tmp_path / "m.gguf"
    model.write_text("x", encoding="utf-8")
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, 0, 0, 0]
    mock_proc.returncode = 0
    mock_proc.stdout = None

    with (
        patch("akomagni.inference.llama.subprocess.Popen", return_value=mock_proc),
        patch(
            "akomagni.inference.llama.wait_for_health",
            return_value="http://127.0.0.1:8787/health",
        ),
        patch("akomagni.inference.llama.signal.signal"),
        patch("akomagni.inference.llama.time.sleep"),
    ):
        run_llama_server(host="127.0.0.1", port=8787, model_path=model, binary=binary)


def test_run_llama_server_health_failure(tmp_path):
    model = tmp_path / "m.gguf"
    model.write_text("x", encoding="utf-8")
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock(read=MagicMock(return_value="error output"))

    with (
        patch("akomagni.inference.llama.subprocess.Popen", return_value=mock_proc),
        patch("akomagni.inference.llama.wait_for_health", side_effect=LlamaServerError("timeout")),
        patch("akomagni.inference.llama.signal.signal"),
        pytest.raises(LlamaServerError, match="failed health check"),
    ):
        run_llama_server(host="127.0.0.1", port=8787, model_path=model, binary=binary)


def test_server_serve_exits_on_error(tmp_path, monkeypatch):
    from akomagni.inference.server import serve

    monkeypatch.setattr(
        "akomagni.inference.server.serve_inference",
        MagicMock(side_effect=LlamaServerError("boom")),
    )
    with pytest.raises(SystemExit) as exc:
        serve(models_dir=tmp_path)
    assert exc.value.code == 1
