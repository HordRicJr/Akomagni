"""CLI integration tests via Typer CliRunner."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app

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


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "akomagni" in result.stdout


def test_doctor(akomagni_home):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Profil recommandé" in result.stdout


def test_doctor_json(akomagni_home):
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert "profile" in result.stdout


def test_serve():
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    assert "Akomagni inference" in result.stdout


def test_config_init(akomagni_home):
    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code == 0
    assert (akomagni_home / "config.yaml").is_file()


def test_config_show(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "router" in result.stdout


def test_memory_status(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["memory", "status"])
    assert result.exit_code == 0
    assert "Akomagni Memory" in result.stdout


def test_flow_route():
    result = runner.invoke(app, ["flow", "route", "implement login API"])
    assert result.exit_code == 0
    assert "bmad-agent-dev" in result.stdout


def test_flow_invoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "invoke", "fix bug in auth"])
    assert result.exit_code == 0
    assert "Session written" in result.stdout


def test_flow_invoke_open(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "invoke", "design landing page", "--open"])
    assert result.exit_code == 0
    assert "Akomagni Flow session" in result.stdout


def test_flow_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
    runner.invoke(app, ["flow", "invoke", "design landing page"])
    result = runner.invoke(app, ["flow", "status"])
    assert result.exit_code == 0
    assert "active_agent" in result.stdout


def test_model_recommend(akomagni_home):
    result = runner.invoke(app, ["model", "recommend"])
    assert result.exit_code == 0
    assert "Profile:" in result.stdout


def test_model_list(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["model", "list"])
    assert result.exit_code == 0
    assert "light" in result.stdout


def test_skill_list_empty(akomagni_home, monkeypatch):
    monkeypatch.chdir(akomagni_home)
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 1
    assert "No skills found" in result.stdout


def test_skill_list_with_skill(akomagni_home, monkeypatch):
    skill_dir = akomagni_home / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A demo skill\n---\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(akomagni_home)
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "demo-skill" in result.stdout


def test_skill_path_found(akomagni_home, monkeypatch):
    skill_dir = akomagni_home / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    monkeypatch.chdir(akomagni_home)
    result = runner.invoke(app, ["skill", "path", "demo-skill"])
    assert result.exit_code == 0
    assert "demo-skill" in result.stdout


def test_skill_path_not_found(akomagni_home, monkeypatch):
    monkeypatch.chdir(akomagni_home)
    result = runner.invoke(app, ["skill", "path", "missing-skill"])
    assert result.exit_code == 1


def test_run_ide_exits():
    result = runner.invoke(app, ["run", "ide"])
    assert result.exit_code == 1
    assert "Akomagni IDE" in result.stdout


def test_run_cli_no_invoke(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)

    def fake_input(_):
        raise EOFError

    with patch("akomagni.cli.main.console.input", side_effect=fake_input):
        result = runner.invoke(app, ["run", "cli", "--no-invoke"])
    assert result.exit_code == 0


def test_run_cli_invoke(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    messages = iter(["implement auth", ""])

    def fake_input(_):
        try:
            return next(messages)
        except StopIteration:
            raise EOFError

    with patch("akomagni.cli.main.console.input", side_effect=fake_input):
        result = runner.invoke(app, ["run", "cli"])
    assert result.exit_code == 0
    assert "Session:" in result.stdout


def test_main_module():
    from akomagni import __main__

    assert __main__.app is app
