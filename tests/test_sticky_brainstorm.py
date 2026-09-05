"""Sticky brainstorm + first-prompt greenfield behaviour."""

from __future__ import annotations

from akomagni.flow.intent import classify_message
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import save_state
from akomagni.skills.invoke import invoke_skill


def test_first_prompt_on_fresh_project_routes_brainstorm(tmp_path, monkeypatch):
    app = tmp_path / "app_test"
    (app / ".akomagni").mkdir(parents=True)
    monkeypatch.chdir(app)
    decision = route_message("salut on commence", project_root=app)
    assert decision.skill == "bmad-brainstorming"


def test_followup_stays_on_brainstorm_while_in_progress(tmp_path, monkeypatch):
    app = tmp_path / "app_test"
    (app / ".akomagni" / "workflow").mkdir(parents=True)
    save_state(
        {
            "phase": "anytime",
            "gates": {"brainstorm": "in_progress"},
            "completed": ["bmad-brainstorming"],
        },
        project_root=app,
    )
    monkeypatch.chdir(app)
    decision = route_message("1 gestion tâche personnel", project_root=app)
    assert decision.skill == "bmad-brainstorming"
    decision2 = route_message("je valide ce que tu proposes", project_root=app)
    assert decision2.skill == "bmad-brainstorming"
    decision3 = route_message("commence", project_root=app)
    assert decision3.skill == "bmad-brainstorming"


def test_sticky_override_keeps_brainstorm(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    monkeypatch.setattr("akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: None)
    monkeypatch.setattr("akomagni.core.bmad_kernel.ensure_bmad_kernel", lambda **_: None)
    monkeypatch.chdir(app)

    first = invoke_skill("help me brainstorm a todo app", project_root=app)
    assert first.decision.skill == "bmad-brainstorming"
    second = invoke_skill(
        "1 personal tasks",
        project_root=app,
        skill_override="bmad-brainstorming",
    )
    assert second.decision.skill == "bmad-brainstorming"
    assert second.session_path.is_relative_to(app.resolve())


def test_creer_moi_routes_brainstorm():
    decision = classify_message("créer moi une mini application de gestion en web avec react")
    assert decision.skill == "bmad-brainstorming"


def test_simple_agent_phrases():
    assert classify_message("prd").skill == "bmad-prd"
    assert classify_message("ux").skill == "bmad-ux"
    assert classify_message("archi").skill == "bmad-architecture"
    assert classify_message("mary").skill == "bmad-brainstorming"
