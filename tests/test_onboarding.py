"""Tests for connect wizard, HF token, and session onboarding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.core.onboarding import (
    mark_provider_ready,
    needs_provider_onboarding,
    resolve_hf_token,
    run_connect_wizard,
    run_session_setup,
    save_hf_token,
    scaffold_project,
)
from akomagni.inference.pull import resolve_pull_entry

runner = CliRunner()


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    from akomagni.core.config import ensure_default_config

    ensure_default_config()
    return home


def test_scaffold_project(tmp_path):
    root = scaffold_project(tmp_path / "app")
    assert (root / ".akomagni" / "workflow" / "state.yaml").is_file()


def test_save_and_resolve_hf_token(akomagni_home):
    save_hf_token("hf_test_token")
    assert resolve_hf_token() == "hf_test_token"


def test_needs_provider_onboarding(akomagni_home):
    assert needs_provider_onboarding() is True
    mark_provider_ready("local")
    assert needs_provider_onboarding() is False


def test_run_connect_wizard_local(akomagni_home):
    answers = iter(["local", ""])
    result = run_connect_wizard(prompt=lambda _m: next(answers), include_hf=True)
    assert result["provider"] == "local"
    assert needs_provider_onboarding() is False


def test_run_session_setup_with_project(akomagni_home, tmp_path):
    mark_provider_ready("local")
    project = tmp_path / "budget-app"
    session = run_session_setup(
        prompt=lambda _m: str(project),
        project=str(project),
        skip_provider=True,
    )
    assert session.project_root == project.resolve()
    assert (project / ".akomagni").is_dir()


def test_resolve_pull_entry_hf_spec():
    entry = resolve_pull_entry("owner/repo:model-Q4_K_M.gguf")
    assert entry.repo_id == "owner/repo"
    assert entry.filename == "model-Q4_K_M.gguf"
    assert "owner__repo" in entry.name


def test_connect_hf_cli(akomagni_home):
    result = runner.invoke(app, ["connect", "hf"], input="hf_cli_token\n")
    assert result.exit_code == 0
    assert "Hugging Face token saved" in result.stdout
    assert resolve_hf_token() == "hf_cli_token"


def test_connect_setup_wizard_cli(akomagni_home):
    result = runner.invoke(app, ["connect"], input="local\n\n")
    assert result.exit_code == 0
    assert "Connected" in result.stdout


def test_run_connect_wizard_rodium(akomagni_home, monkeypatch):
    calls: list[str] = []

    def _fake_connect(name, **kwargs):
        calls.append(name)
        from akomagni.inference.connect import ConnectResult

        return ConnectResult(
            provider=name,
            base_url="https://api.rodiumai.io/v1",
            api_key_saved=True,
            online=True,
            models=["rodium/fast"],
        )

    monkeypatch.setattr("akomagni.core.onboarding.connect_provider", _fake_connect)
    answers = iter(["rodium", "rd_sk_x", "hf_token"])
    result = run_connect_wizard(prompt=lambda _m: next(answers), include_hf=True)
    assert result["provider"] == "rodium"
    assert result["hf_saved"] is True
    assert calls == ["rodium"]


def test_run_connect_wizard_foundry(akomagni_home, monkeypatch):
    monkeypatch.setattr(
        "akomagni.core.onboarding.connect_provider",
        lambda *a, **k: type("R", (), {"provider": "azure"})(),
    )
    answers = iter(["foundry", "https://x.openai.azure.com/openai/v1/", "az_key", ""])
    result = run_connect_wizard(prompt=lambda _m: next(answers), include_hf=True)
    assert result["provider"] == "foundry"


def test_run_connect_wizard_invalid(akomagni_home):
    from akomagni.inference.connect import ConnectError

    with pytest.raises(ConnectError):
        run_connect_wizard(prompt=lambda _m: "nope", include_hf=False)


def test_session_setup_prompts_provider(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "akomagni.core.onboarding.connect_provider",
        lambda *a, **k: None,
    )
    project = tmp_path / "p1"
    answers = iter(["local", "", str(project)])
    session = run_session_setup(prompt=lambda _m: next(answers))
    assert session.project_root == project.resolve()
    assert session.connected is True


def test_pick_gguf_and_pull_custom(tmp_path, monkeypatch, akomagni_home):
    from akomagni.inference import pull as pull_mod

    monkeypatch.setattr(
        pull_mod,
        "_pick_gguf_filename",
        lambda repo_id, token=None: "model-Q4_K_M.gguf",
    )

    def _fake_download(**kwargs):
        dest = Path(kwargs["local_dir"]) / kwargs["filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"gguf")
        return str(dest)

    import sys
    from types import ModuleType

    hub = ModuleType("huggingface_hub")
    hub.hf_hub_download = _fake_download
    hub.list_repo_files = lambda *a, **k: ["model-Q4_K_M.gguf", "other.gguf"]
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)

    path = pull_mod.pull_model("owner/repo", models_dir=tmp_path / "models")
    assert path.is_file()
    assert path.name == "model-Q4_K_M.gguf"


def test_resolve_pull_entry_unknown():
    with pytest.raises(Exception, match="Unknown model"):
        resolve_pull_entry("not-a-model")


def test_pick_gguf_filename_prefers_q4(monkeypatch):
    import sys
    from types import ModuleType

    from akomagni.inference.pull import ModelPullError, _pick_gguf_filename

    hub = ModuleType("huggingface_hub")
    hub.list_repo_files = lambda *a, **k: ["big.gguf", "phi-Q4_K_M.gguf", "tiny.gguf"]
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    assert _pick_gguf_filename("owner/repo", token=None) == "phi-Q4_K_M.gguf"

    hub.list_repo_files = lambda *a, **k: []
    with pytest.raises(ModelPullError, match="No .gguf"):
        _pick_gguf_filename("owner/repo", token=None)


def test_session_setup_provider_rodium(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.setattr("akomagni.core.onboarding.connect_provider", lambda *a, **k: None)
    project = tmp_path / "rodium-app"
    session = run_session_setup(
        prompt=lambda _m: "rd_sk_test",
        project=str(project),
        provider="rodium",
    )
    assert session.provider == "rodium"
    assert session.connected is True


def test_session_setup_provider_foundry(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.setattr("akomagni.core.onboarding.connect_provider", lambda *a, **k: None)
    project = tmp_path / "foundry-app"
    answers = iter(["https://x.openai.azure.com/openai/v1/", "az_key"])
    session = run_session_setup(
        prompt=lambda _m: next(answers),
        project=str(project),
        provider="foundry",
    )
    assert session.provider == "foundry"


def test_save_hf_token_empty(akomagni_home):
    from akomagni.inference.connect import ConnectError

    with pytest.raises(ConnectError):
        save_hf_token("   ")


def test_run_cli_project_flag(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "budget"
    with patch("rich.console.Console.input", side_effect=EOFError()):
        result = runner.invoke(
            app,
            ["run", "cli", "--no-setup", "--no-inference", "--project", str(project)],
        )
    assert result.exit_code == 0
    assert (project / ".akomagni").is_dir()


def test_run_cli_setup_onboarding(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "new-app"

    class FakeSession:
        provider = "local"
        project_root = project
        created_project = True
        connected = True

    project.mkdir()
    (project / ".akomagni").mkdir()
    monkeypatch.setattr(
        "akomagni.core.onboarding.run_session_setup",
        lambda **kwargs: FakeSession(),
    )
    monkeypatch.setattr(
        "akomagni.core.onboarding.needs_provider_onboarding",
        lambda _cfg=None: True,
    )
    with patch("rich.console.Console.input", side_effect=EOFError()):
        result = runner.invoke(app, ["run", "cli", "--no-inference", "--setup"])
    assert result.exit_code == 0
    assert "Provider" in result.stdout or "Project" in result.stdout


def test_connect_foundry_cli(akomagni_home, monkeypatch):
    status = type("S", (), {"online": True, "models": ["gpt"], "error": None})()
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    with patch(
        "typer.prompt",
        side_effect=[
            "https://res.openai.azure.com/openai/v1/",
            "az_key",
            "",
        ],
    ):
        result = runner.invoke(app, ["connect", "foundry", "--no-sync"])
    assert result.exit_code == 0
    assert "Foundry" in result.stdout or "Connected" in result.stdout


def test_connect_local_cli(akomagni_home):
    result = runner.invoke(app, ["connect", "local"])
    assert result.exit_code == 0
    assert "local" in result.stdout.lower()


def test_format_hub_error_messages():
    from akomagni.core.registry.catalog import ModelCatalogEntry
    from akomagni.inference.pull import _format_hub_error

    entry = ModelCatalogEntry("n", "org/repo", "f.gguf", "custom")
    assert "401" in _format_hub_error(RuntimeError("401 Unauthorized"), entry)
    assert "Model repo not found" in _format_hub_error(RuntimeError("404"), entry)
    assert "gated" in _format_hub_error(RuntimeError("model is gated"), entry).lower()
    assert "Download failed" in _format_hub_error(RuntimeError("boom"), entry)


def test_import_train_stack_missing(monkeypatch):
    import builtins

    from akomagni.train.lora import TrainError
    from akomagni.train.runner import import_train_stack

    real_import = builtins.__import__

    def _fake(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".", 1)[0]
        if root in {"torch", "transformers", "peft", "datasets", "trl"}:
            raise ImportError(name, name=root)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake)
    with pytest.raises(TrainError, match="akomagni\\[train\\]"):
        import_train_stack()


def test_bnb_available_import_error(monkeypatch):
    import builtins

    from akomagni.train.runner import _bnb_available

    class Cuda:
        @staticmethod
        def is_available():
            return True

    torch = type("T", (), {"cuda": Cuda})()
    real_import = builtins.__import__

    def _fake(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "bitsandbytes" or name.startswith("bitsandbytes"):
            raise ImportError("no bnb", name="bitsandbytes")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake)
    assert _bnb_available(torch) is False
