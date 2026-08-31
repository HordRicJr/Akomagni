"""Tests for BMAD skill subprocess runner."""

from __future__ import annotations

from unittest.mock import patch

from akomagni.skills.invoke import invoke_skill
from akomagni.skills.runner import (
    SkillRunResult,
    build_context_env,
    build_render_command,
    parse_workflow_path,
    run_skill_subprocess,
)


def test_parse_workflow_path(tmp_path):
    workflow = tmp_path / "workflow.md"
    workflow.write_text("# workflow", encoding="utf-8")
    stdout = f"read and follow {workflow}\n"
    assert parse_workflow_path(stdout) == workflow


def test_parse_workflow_path_missing():
    assert parse_workflow_path("HALT: broken\n") is None


def test_build_context_env():
    env = build_context_env(
        message="build login",
        central_context="profile",
        project_context="notes",
    )
    assert env["AKOMAGNI_USER_MESSAGE"] == "build login"
    assert "profile" in env["AKOMAGNI_MEMORY_CONTEXT"]
    assert "notes" in env["AKOMAGNI_MEMORY_CONTEXT"]


def test_build_render_command(tmp_path):
    script = tmp_path / "_bmad" / "scripts"
    script.mkdir(parents=True)
    render = script / "render_skill.py"
    render.write_text("# stub", encoding="utf-8")
    skill = tmp_path / "skills" / "bmad-build"
    skill.mkdir(parents=True)
    cmd = build_render_command(uv="uv", project_root=tmp_path, skill_path=skill)
    assert cmd[:4] == ["uv", "run", "--no-cache", str(render)]
    assert cmd[-2:] == ["--skill", str(skill)]


def test_run_skill_subprocess_missing_uv(tmp_path):
    skill = tmp_path / "skill"
    skill.mkdir()
    result = run_skill_subprocess(
        project_root=tmp_path,
        skill_path=skill,
        message="hello",
        uv="__missing_uv__",
    )
    assert result.success is False
    assert result.returncode == 127


def test_run_skill_subprocess_missing_render_script(tmp_path):
    skill = tmp_path / "skill"
    skill.mkdir()
    result = run_skill_subprocess(
        project_root=tmp_path,
        skill_path=skill,
        message="hello",
        uv="uv",
    )
    assert result.success is False
    assert "render script" in result.error.lower()


def test_run_skill_subprocess_success(tmp_path):
    script = tmp_path / "_bmad" / "scripts"
    script.mkdir(parents=True)
    (script / "render_skill.py").write_text("# stub", encoding="utf-8")
    skill = tmp_path / "skills" / "bmad-build"
    skill.mkdir(parents=True)
    workflow = tmp_path / "workflow.md"
    workflow.write_text("# workflow", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = f"read and follow {workflow}\n"
        stderr = ""

    with patch("akomagni.skills.runner.subprocess.run", return_value=Completed()) as run:
        result = run_skill_subprocess(
            project_root=tmp_path,
            skill_path=skill,
            message="implement auth",
            central_context="central memory",
            project_context="project memory",
            uv="uv",
        )

    assert result.success is True
    assert result.workflow_path == workflow
    run.assert_called_once()
    env = run.call_args.kwargs["env"]
    assert env["AKOMAGNI_USER_MESSAGE"] == "implement auth"
    assert "central memory" in env["AKOMAGNI_MEMORY_CONTEXT"]


def test_run_skill_subprocess_nonzero_exit(tmp_path):
    script = tmp_path / "_bmad" / "scripts"
    script.mkdir(parents=True)
    (script / "render_skill.py").write_text("# stub", encoding="utf-8")
    skill = tmp_path / "skills" / "bmad-build"
    skill.mkdir(parents=True)

    class Completed:
        returncode = 1
        stdout = "HALT: broken"
        stderr = ""

    with patch("akomagni.skills.runner.subprocess.run", return_value=Completed()):
        result = run_skill_subprocess(
            project_root=tmp_path,
            skill_path=skill,
            message="implement auth",
            uv="uv",
        )

    assert result.success is False
    assert "HALT" in result.error


def test_run_skill_subprocess_timeout(tmp_path):
    script = tmp_path / "_bmad" / "scripts"
    script.mkdir(parents=True)
    (script / "render_skill.py").write_text("# stub", encoding="utf-8")
    skill = tmp_path / "skills" / "bmad-build"
    skill.mkdir(parents=True)

    import subprocess

    with patch(
        "akomagni.skills.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="uv", timeout=1),
    ):
        result = run_skill_subprocess(
            project_root=tmp_path,
            skill_path=skill,
            message="implement auth",
            uv="uv",
            timeout=1.0,
        )

    assert result.success is False
    assert result.returncode == 124


def test_invoke_skill_execute_appends_run_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "_bmad" / "scripts"
    script.mkdir(parents=True)
    (script / "render_skill.py").write_text("# stub", encoding="utf-8")
    skill_root = tmp_path / ".claude" / "skills" / "bmad-build"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: bmad-build\ndescription: build\n---\n",
        encoding="utf-8",
    )
    workflow = tmp_path / "rendered" / "workflow.md"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("# rendered", encoding="utf-8")
    run_result = SkillRunResult(
        command=("uv", "run", "render_skill.py"),
        returncode=0,
        stdout=f"read and follow {workflow}\n",
        stderr="",
        workflow_path=workflow,
        success=True,
    )

    with patch("akomagni.skills.invoke.run_skill_subprocess", return_value=run_result):
        result = invoke_skill("implement login API", execute=True, project_root=tmp_path)

    text = result.session_path.read_text(encoding="utf-8")
    assert "## Skill execution (uv run)" in text
    assert str(workflow) in text
    assert result.run_result is not None
    assert result.run_result.success is True
