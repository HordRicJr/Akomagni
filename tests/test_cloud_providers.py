"""Tests for cloud inference endpoints and providers."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.ide.setup import (
    build_env_example,
    build_ide_guide,
    build_vscode_extensions_recommendations,
)
from akomagni.inference.endpoint import (
    RODIUM_DEFAULT_BASE_URL,
    cloud_model_for_domain,
    resolve_inference_endpoint,
)
from akomagni.inference.providers import apply_provider_preset

runner = CliRunner()


def test_resolve_rodium_endpoint(monkeypatch):
    monkeypatch.setenv("RODIUMAI_API_KEY", "rd_sk_test")
    cfg = apply_provider_preset({"version": 1}, "rodium")
    endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.provider == "rodium"
    assert endpoint.base_url == RODIUM_DEFAULT_BASE_URL
    assert endpoint.api_key == "rd_sk_test"
    assert endpoint.is_local is False


def test_cloud_model_for_domain_rodium():
    cfg = apply_provider_preset({"version": 1}, "rodium")
    # Avoid live catalogue flakiness in unit tests.
    with patch("akomagni.inference.model_picker.resolve_session_cloud_model") as mocked:
        mocked.side_effect = lambda domain, **kwargs: {
            "code": "rodiumai/smart",
            "text": "google/gemini-3.1-flash-lite-preview",
            "image": "google/gemini-3-pro-image",
            "design": "anthropic/claude-haiku-4-5-20251001",
        }[domain]
        assert cloud_model_for_domain("code", config=cfg) == "rodiumai/smart"
        assert cloud_model_for_domain("text", config=cfg) == "google/gemini-3.1-flash-lite-preview"
        assert cloud_model_for_domain("image", config=cfg) == "google/gemini-3-pro-image"


def test_sanitize_legacy_rodium_basic():
    from akomagni.inference.endpoint import sanitize_rodium_model

    assert sanitize_rodium_model("rodium/basic") == "google/gemini-3.1-flash-lite-preview"
    assert sanitize_rodium_model("rodium/fast", domain="code") == "rodiumai/smart"
    assert sanitize_rodium_model("openai/gpt-4o") == "openai/gpt-4o"


def test_apply_rodium_preset_refreshes_basic_model(akomagni_home):
    cfg = {
        "version": 1,
        "providers": {
            "rodium": {
                "api_key": "rd_sk_keep",
                "models": {"text": "rodium/basic", "code": "rodium/fast", "design": "rodium/pro"},
            }
        },
    }
    merged = apply_provider_preset(cfg, "rodium")
    models = merged["providers"]["rodium"]["models"]
    assert models["text"] == "google/gemini-3.1-flash-lite-preview"
    assert models["code"] == "rodiumai/smart"
    assert models["design"].startswith(("anthropic/", "google/", "openai/"))
    assert merged["providers"]["rodium"]["api_key"] == "rd_sk_keep"


def test_apply_azure_provider_requires_base_url():
    with pytest.raises(ValueError, match="Unknown provider"):
        apply_provider_preset({"version": 1}, "nope")


def test_config_provider_rodium(akomagni_home, monkeypatch):
    monkeypatch.setenv("RODIUMAI_API_KEY", "rd_sk_test")
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "provider", "rodium"])
    assert result.exit_code == 0
    show = runner.invoke(app, ["config", "show"])
    assert "rodium" in show.stdout
    assert "api.rodiumai.io" in show.stdout


def test_build_vscode_extensions_includes_akomagni_chat():
    payload = build_vscode_extensions_recommendations(provider="rodium")
    assert "Akomagni.akomagni" in payload["recommendations"]


def test_build_env_example_mentions_rodium_and_azure():
    text = build_env_example(provider="local")
    assert "RODIUMAI_API_KEY" in text
    assert "AZURE_OPENAI_API_KEY" in text


def test_build_ide_guide_mentions_foundry():
    text = build_ide_guide(provider="azure")
    assert "Foundry Toolkit" in text
    assert "ai.azure.com" in text


def test_ide_setup_with_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ide", "setup", "--provider", "rodium"])
    assert result.exit_code == 0
    assert (tmp_path / ".vscode" / "extensions.json").is_file()
    assert (tmp_path / ".env.example").is_file()
    assert (tmp_path / "AKOMAGNI_IDE.md").is_file()


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    return home
