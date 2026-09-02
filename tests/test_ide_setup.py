"""Tests for Akomagni IDE MCP setup helpers."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.ide.setup import IdeSetupError, build_mcp_config, ide_status, write_cursor_mcp_config

runner = CliRunner()


def test_build_mcp_config(tmp_path):
    payload = build_mcp_config(tmp_path, akomagni_command="/usr/bin/akomagni")
    server = payload["mcpServers"]["akomagni"]
    assert server["command"] == "/usr/bin/akomagni"
    assert server["args"][0:2] == ["mcp", "serve"]
    assert server["args"][-1] == str(tmp_path.resolve())


def test_write_cursor_mcp_config(tmp_path):
    result = write_cursor_mcp_config(tmp_path, akomagni_command="akomagni")
    assert result.cursor_config.is_file()
    assert result.vscode_config.is_file()
    assert result.extensions_config is not None
    assert result.extensions_config.is_file()
    payload = json.loads(result.cursor_config.read_text(encoding="utf-8"))
    assert "akomagni" in payload["mcpServers"]


def test_write_cursor_mcp_config_refuses_overwrite(tmp_path):
    write_cursor_mcp_config(tmp_path, akomagni_command="akomagni")
    with pytest.raises(IdeSetupError, match="already exists"):
        write_cursor_mcp_config(tmp_path, akomagni_command="akomagni")


def test_write_cursor_mcp_config_force_overwrite(tmp_path):
    write_cursor_mcp_config(tmp_path, akomagni_command="akomagni")
    result = write_cursor_mcp_config(tmp_path, overwrite=True, akomagni_command="akomagni2")
    payload = json.loads(result.cursor_config.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["akomagni"]["command"] == "akomagni2"


def test_ide_status(tmp_path):
    status = ide_status(tmp_path)
    assert status["cursor_config"] is False
    write_cursor_mcp_config(tmp_path, akomagni_command="akomagni")
    status = ide_status(tmp_path)
    assert status["cursor_config"] is True
    assert status["vscode_config"] is True


def test_ide_setup_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ide", "setup"])
    assert result.exit_code == 0
    assert "IDE setup complete" in result.stdout
    assert (tmp_path / ".cursor" / "mcp.json").is_file()


def test_ide_status_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ide", "status"])
    assert result.exit_code == 0
    assert "IDE status" in result.stdout
