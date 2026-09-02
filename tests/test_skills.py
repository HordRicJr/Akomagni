from pathlib import Path

import pytest

from akomagni.core.project import find_project_root
from akomagni.skills.discovery import discover_skills, find_skill
from akomagni.skills.invoke import invoke_skill


def test_invoke_writes_session(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    result = invoke_skill("implement the login API with JWT")
    assert result.session_path.is_file()
    text = result.session_path.read_text(encoding="utf-8")
    assert "login API" in text
    assert result.decision.agent_id == "bmad-agent-dev"
    assert (result.project_root / ".akomagni" / "workflow" / "state.yaml").is_file()


def test_discover_skills_empty_without_bmad(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert discover_skills() == {}


@pytest.mark.skipif(
    not Path(__file__).resolve().parents[2].parent.joinpath("_bmad").is_dir(),
    reason="BMAD workspace not available",
)
def test_discover_skills_in_parent_money_workspace():
    money_root = Path(__file__).resolve().parents[2].parent
    skills = discover_skills(money_root)
    assert "bmad-brainstorming" in skills
    info = find_skill("bmad-brainstorming", money_root)
    assert info is not None
    assert info.path.joinpath("SKILL.md").is_file()


def test_find_project_root_from_money():
    money_root = Path(__file__).resolve().parents[2].parent
    if not (money_root / "_bmad").is_dir():
        pytest.skip("BMAD workspace not available")
    assert find_project_root(money_root / "akomagni") == money_root
