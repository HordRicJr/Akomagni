"""Tests for akomagni connect command."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.inference.connect import (
    ConnectError,
    connect_provider,
    normalize_provider,
    sync_vscode_settings,
)

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
    return home


def test_normalize_provider_aliases():
    assert normalize_provider("foundry") == "azure"
    assert normalize_provider("rodium") == "rodium"


def test_normalize_provider_unknown():
    with pytest.raises(ConnectError):
        normalize_provider("unknown")


def test_sync_vscode_settings(tmp_path):
    path = sync_vscode_settings(
        tmp_path,
        provider="rodium",
        base_url="https://api.rodiumai.io/v1",
        api_key="rd_sk_test",
        model="openai/gpt-4o",
    )
    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["akomagni.apiKey"] == "rd_sk_test"


def test_connect_rodium_saves_config(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])

    status = SimpleNamespace(online=True, models=["openai/gpt-4o"], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    result = connect_provider(
        "rodium",
        api_key="rd_sk_test",
        workspace=tmp_path,
    )
    assert result.api_key_saved is True
    assert result.online is True
    settings = tmp_path / ".vscode" / "settings.json"
    assert settings.is_file()


def test_connect_cli_interactive(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.chdir(tmp_path)

    status = SimpleNamespace(online=True, models=[], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )

    with patch("typer.prompt", side_effect=["https://api.rodiumai.io/v1", "rd_sk_interactive", ""]):
        result = runner.invoke(app, ["connect", "rodium"])
    assert result.exit_code == 0
    assert "Connected" in result.stdout


def test_connect_foundry_requires_url(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["connect", "foundry"])
    assert result.exit_code != 0
