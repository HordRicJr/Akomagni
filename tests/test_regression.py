"""Regression suite — critical paths that must never break between releases."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.flow.orchestrator import route_message
from akomagni.skills.invoke import invoke_skill

pytestmark = pytest.mark.regression

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


def test_regression_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "akomagni" in result.stdout


def test_regression_doctor_reports_profile(akomagni_home):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Profil recommandé" in result.stdout


def test_regression_config_lifecycle(akomagni_home):
    init = runner.invoke(app, ["config", "init"])
    assert init.exit_code == 0
    assert (akomagni_home / "config.yaml").is_file()

    show = runner.invoke(app, ["config", "show"])
    assert show.exit_code == 0
    assert "router" in show.stdout


def test_regression_memory_status(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["memory", "status"])
    assert result.exit_code == 0
    assert "Akomagni Memory" in result.stdout


def test_regression_flow_routes_brainstorm_greenfield():
    decision = route_message("J'ai une idée pour une nouvelle app de budget")
    assert decision.skill == "bmad-brainstorming"
    assert decision.greenfield is True


def test_regression_flow_routes_dev():
    decision = route_message("Implémente le endpoint login avec JWT")
    assert decision.agent_id == "bmad-agent-dev"
    assert decision.skill == "bmad-build"


def test_regression_flow_invoke_writes_session_and_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)

    result = invoke_skill("implement the login API with JWT")
    assert result.session_path.is_file()
    assert "login API" in result.session_path.read_text(encoding="utf-8")
    assert result.decision.agent_id == "bmad-agent-dev"

    state_path = tmp_path / ".akomagni" / "workflow" / "state.yaml"
    assert state_path.is_file()
    assert "active_agent" in state_path.read_text(encoding="utf-8")


def test_regression_flow_cli_invoke_and_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)

    invoke = runner.invoke(app, ["flow", "invoke", "design landing page"])
    assert invoke.exit_code == 0
    assert "Session written" in invoke.stdout

    status = runner.invoke(app, ["flow", "status"])
    assert status.exit_code == 0
    assert "active_agent" in status.stdout


def test_regression_skill_discovery_and_path(akomagni_home, monkeypatch):
    skill_dir = akomagni_home / "skills" / "regression-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: regression-skill\ndescription: regression fixture\n---\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(akomagni_home)

    listed = runner.invoke(app, ["skill", "list"])
    assert listed.exit_code == 0
    assert "regression-skill" in listed.stdout

    path = runner.invoke(app, ["skill", "path", "regression-skill"])
    assert path.exit_code == 0
    assert "regression-skill" in path.stdout.replace("\n", "")


def test_regression_model_recommend(akomagni_home):
    result = runner.invoke(app, ["model", "recommend"])
    assert result.exit_code == 0
    assert "Profile:" in result.stdout


def test_regression_serve_stub():
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    assert "Akomagni inference" in result.stdout


def test_regression_run_cli_session(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
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
