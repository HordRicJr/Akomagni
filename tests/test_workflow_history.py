"""Tests for workflow history persistence and resume routing."""

from __future__ import annotations

from akomagni.flow.history import (
    extract_session_user_messages,
    is_resume_continue,
    load_chat_history,
    prior_workflow_context,
    save_chat_history,
)
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import save_state


def test_is_resume_continue_phrases():
    assert is_resume_continue("on continue l'appp") is True
    assert is_resume_continue("continuons") is True
    assert is_resume_continue("1 gestion perso") is False


def test_resume_continue_routes_build_even_if_brainstorm_in_progress(tmp_path, monkeypatch):
    app = tmp_path / "app_test"
    (app / ".akomagni" / "workflow").mkdir(parents=True)
    save_state(
        {
            "phase": "start",
            "gates": {"brainstorm": "in_progress"},
            "completed": ["bmad-brainstorming"],
            "active_skill": "bmad-brainstorming",
        },
        project_root=app,
    )
    monkeypatch.chdir(app)
    decision = route_message("on continue l'app", project_root=app)
    assert decision.skill == "bmad-build"


def test_chat_history_roundtrip(tmp_path):
    app = tmp_path / "proj"
    (app / ".akomagni" / "workflow").mkdir(parents=True)
    save_chat_history(
        app,
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )
    loaded = load_chat_history(app)
    assert loaded == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]


def test_prior_workflow_context_reads_sessions(tmp_path):
    app = tmp_path / "proj"
    sessions = app / ".akomagni" / "workflow" / "sessions"
    sessions.mkdir(parents=True)
    save_state(
        {"phase": "start", "gates": {"brainstorm": "in_progress"}, "completed": []},
        project_root=app,
    )
    (sessions / "20260906-120000-bmad-brainstorming.md").write_text(
        "# Session\n\n## User message\n\nfais une todo app\n\n## Skill\n\nx\n",
        encoding="utf-8",
    )
    (sessions / "20260906-120100-bmad-brainstorming.md").write_text(
        "# Session\n\n## User message\n\n1 personnel 2 localStorage\n\n## Skill\n\nx\n",
        encoding="utf-8",
    )
    turns = extract_session_user_messages(app)
    assert turns == ["fais une todo app", "1 personnel 2 localStorage"]
    ctx = prior_workflow_context(app)
    assert "do NOT restart discovery" in ctx
    assert "1 personnel 2 localStorage" in ctx
