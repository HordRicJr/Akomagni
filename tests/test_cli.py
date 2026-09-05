"""CLI integration tests via Typer CliRunner."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.skills.runner import SkillRunResult

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
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Recommended profile" in result.stdout


def test_doctor_json(akomagni_home):
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert "profile" in result.stdout


def test_serve_missing_binary(akomagni_home):
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 1
    assert "llama-server" in result.stdout


def test_inference_status_offline(akomagni_home):
    result = runner.invoke(app, ["inference", "status"])
    assert result.exit_code == 1
    assert "Offline" in result.stdout


def test_inference_status_online(akomagni_home, monkeypatch):
    from akomagni.inference.client import InferenceStatus

    monkeypatch.setattr(
        "akomagni.cli.main.check_health_from_config",
        lambda *_args, **_kwargs: InferenceStatus(
            online=True,
            base_url="http://127.0.0.1:8787/v1",
            models=["local"],
        ),
    )
    result = runner.invoke(app, ["inference", "status"])
    assert result.exit_code == 0
    assert "Online" in result.stdout


def test_inference_chat_offline(akomagni_home):
    result = runner.invoke(app, ["inference", "chat", "hello"])
    assert result.exit_code == 1


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


def test_memory_add_project(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["memory", "add", "Use JWT for API auth", "-t", "Auth"])
    assert result.exit_code == 0
    assert "Saved (project)" in result.stdout
    assert (tmp_path / ".akomagni" / "memory" / "learnings").is_dir()


def test_memory_add_global(akomagni_home):
    result = runner.invoke(app, ["memory", "add", "Prefer Ruff", "--global"])
    assert result.exit_code == 0
    assert "Saved (central)" in result.stdout


def test_memory_promote(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    proj = tmp_path / ".akomagni" / "memory"
    proj.mkdir(parents=True)
    (proj / "notes.md").write_text("project note", encoding="utf-8")
    result = runner.invoke(app, ["memory", "promote"])
    assert result.exit_code == 0
    assert "central memory" in result.stdout or "mémoire centrale" in result.stdout


def test_router_classify():
    result = runner.invoke(app, ["router", "classify", "implement login API"])
    assert result.exit_code == 0
    assert "domain=code" in result.stdout


def test_router_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["router", "plan", "design landing page"])
    assert result.exit_code == 0
    assert "Domain" in result.stdout


def test_inference_swap_cli(tmp_path, monkeypatch):
    model = tmp_path / "phi-3.5-mini-instruct-q4.gguf"
    model.write_text("gguf", encoding="utf-8")
    monkeypatch.setattr("akomagni.cli.main.MODELS_DIR", tmp_path)
    worker = type(
        "Worker", (), {"pid": 1, "model_path": str(model), "host": "127.0.0.1", "port": 8787}
    )()
    swap = type("Swap", (), {"swapped": True, "message": "Loaded", "worker": worker})()
    with patch("akomagni.cli.main.hot_swap_model", return_value=swap):
        result = runner.invoke(app, ["inference", "swap", "phi-3.5-mini"])
    assert result.exit_code == 0
    assert "Loaded" in result.stdout


def test_inference_stop_cli(monkeypatch):
    with patch("akomagni.cli.main.stop_worker", return_value=True):
        result = runner.invoke(app, ["inference", "stop"])
    assert result.exit_code == 0
    assert "stopped" in result.stdout.lower()


def test_inference_worker_cli(monkeypatch):
    state = type(
        "State", (), {"pid": 9, "model_path": "/m.gguf", "host": "127.0.0.1", "port": 8787}
    )()
    with patch("akomagni.cli.main.read_worker_state", return_value=state):
        result = runner.invoke(app, ["inference", "worker"])
    assert result.exit_code == 0
    assert "PID" in result.stdout


def test_flow_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "route", "implement login API"])
    assert result.exit_code == 0
    assert "bmad-agent-dev" in result.stdout


def test_flow_router_mode_show_and_set(akomagni_home):
    runner.invoke(app, ["config", "init"])
    show = runner.invoke(app, ["flow", "router-mode"])
    assert show.exit_code == 0
    assert "auto" in show.stdout

    set_heuristic = runner.invoke(app, ["flow", "router-mode", "heuristic"])
    assert set_heuristic.exit_code == 0

    invalid = runner.invoke(app, ["flow", "router-mode", "invalid"])
    assert invalid.exit_code == 1


def test_flow_invoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "invoke", "fix bug in auth"])
    assert result.exit_code == 0
    assert "Session written" in result.stdout


def test_flow_invoke_exec_reports_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "invoke", "fix bug in auth", "--exec"])
    assert result.exit_code == 0
    assert "Skill exec failed" in result.stdout or "Session written" in result.stdout


def test_flow_invoke_exec_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_bmad").mkdir()
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: tmp_path)
    skill_root = tmp_path / ".claude" / "skills" / "bmad-build"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: bmad-build\ndescription: build\n---\n",
        encoding="utf-8",
    )
    workflow = tmp_path / "workflow.md"
    workflow.write_text("# workflow", encoding="utf-8")
    run_result = SkillRunResult(
        command=("uv", "run"),
        returncode=0,
        stdout="",
        stderr="",
        workflow_path=workflow,
        success=True,
    )
    with patch("akomagni.skills.invoke.run_skill_subprocess", return_value=run_result):
        result = runner.invoke(app, ["flow", "invoke", "fix bug in auth", "--exec"])
    assert result.exit_code == 0
    assert "Workflow rendered" in result.stdout


def test_flow_invoke_open(akomagni_home, monkeypatch):
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
    result = runner.invoke(app, ["flow", "invoke", "design landing page", "--open"])
    assert result.exit_code == 0
    assert "Akomagni Flow session" in result.stdout


def test_flow_status(akomagni_home, monkeypatch):
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


def test_model_catalog(akomagni_home):
    result = runner.invoke(app, ["model", "catalog"])
    assert result.exit_code == 0
    assert "qwen2.5-coder-7b" in result.stdout


def test_model_pull_unknown(akomagni_home):
    result = runner.invoke(app, ["model", "pull", "unknown-model"])
    assert result.exit_code == 1


def test_skill_list_empty(akomagni_home, monkeypatch):
    monkeypatch.chdir(akomagni_home)
    monkeypatch.setattr("akomagni.skills.link._known_skill_locations", list)
    monkeypatch.setattr("akomagni.skills.link.ensure_skills_linked", lambda start=None: [])
    monkeypatch.setattr("akomagni.cli.main.discover_skills", lambda project_root=None: {})
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 1
    assert "No skills found" in result.stdout or "skill link" in result.stdout.lower()


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
    assert "demo-skill" in result.stdout.replace("\n", "")


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
        result = runner.invoke(app, ["run", "cli", "--no-setup", "--no-invoke"])
    assert result.exit_code == 0


def test_run_cli_invoke(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
    messages = iter(["implement auth", ""])

    def fake_input(_):
        try:
            return next(messages)
        except StopIteration:
            raise EOFError

    with patch("akomagni.cli.main.console.input", side_effect=fake_input):
        result = runner.invoke(app, ["run", "cli", "--no-setup", "--no-inference"])
    assert result.exit_code == 0
    assert "Session:" in result.stdout


def test_run_cli_with_inference(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
    messages = iter(["hello there", ""])

    def fake_input(_):
        try:
            return next(messages)
        except StopIteration:
            raise EOFError

    with (
        patch("akomagni.cli.main.check_health_from_config") as mock_health,
        patch("akomagni.cli.main.try_chat_with_inference", return_value="Use JWT."),
        patch("akomagni.cli.main.console.input", side_effect=fake_input),
    ):
        mock_health.return_value = type(
            "S",
            (),
            {"online": True, "base_url": "http://127.0.0.1:8787/v1"},
        )()
        result = runner.invoke(app, ["run", "cli", "--no-setup"])
    assert result.exit_code == 0
    assert "Use JWT." in result.stdout
    assert "Inference online" in result.stdout


def test_run_cli_skips_free_chat_for_build_skill(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("akomagni.skills.invoke.find_project_root", lambda *_: None)
    messages = iter(["implement auth", ""])

    def fake_input(_):
        try:
            return next(messages)
        except StopIteration:
            raise EOFError

    with (
        patch("akomagni.cli.main.check_health_from_config") as mock_health,
        patch(
            "akomagni.cli.main.try_chat_with_inference", return_value="should not appear"
        ) as mock_chat,
        patch("akomagni.cli.main.console.input", side_effect=fake_input),
    ):
        mock_health.return_value = type(
            "S",
            (),
            {"online": True, "base_url": "http://127.0.0.1:8787/v1"},
        )()
        result = runner.invoke(app, ["run", "cli", "--no-setup"])
    assert result.exit_code == 0
    assert "should not appear" not in result.stdout
    assert "does not invent" in result.stdout
    mock_chat.assert_not_called()


def test_main_module():
    from akomagni import __main__

    assert __main__.app is app
