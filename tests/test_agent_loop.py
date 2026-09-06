"""Agent tool-loop parsing and execution."""

from __future__ import annotations

from akomagni.flow.intent import RouteDecision
from akomagni.inference.agent_loop import (
    execute_tool_call,
    parse_tool_calls,
    run_agent_tool_turn,
    strip_tool_markup,
    wants_project_tools,
)
from akomagni.mcp.tools import AgentTools


def test_parse_and_strip_tool_blocks():
    raw = (
        "Je crée App.jsx dans le projet.\n"
        "<<<TOOL>>>\n"
        '{"name":"fs_write","path":"src/App.jsx","content":"export default function App(){return null}"}\n'
        "<<<END_TOOL>>>\n"
        "<<<DONE>>>"
    )
    calls = parse_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["name"] == "fs_write"
    visible = strip_tool_markup(raw)
    assert "<<<TOOL>>>" not in visible
    assert "export default" not in visible
    assert "crée App.jsx" in visible or "Je crée" in visible


def test_parse_skips_invalid_json():
    raw = "<<<TOOL>>>\n{not-json}\n<<<END_TOOL>>>"
    assert parse_tool_calls(raw) == []


def test_execute_fs_write_read_list_and_unknown(tmp_path):
    tools = AgentTools(tmp_path, auto_approve=True)
    result = execute_tool_call(
        tools,
        {"name": "fs_write", "path": "hello.txt", "content": "hi"},
    )
    assert result.ok
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "hi"
    assert execute_tool_call(tools, {"name": "fs_read", "path": "hello.txt"}).output == "hi"
    listed = execute_tool_call(tools, {"name": "fs_list", "path": "."})
    assert listed.ok and "hello.txt" in listed.output
    unknown = execute_tool_call(tools, {"name": "nope"})
    assert unknown.ok is False


def test_execute_shell_run(tmp_path):
    tools = AgentTools(tmp_path, auto_approve=True)
    result = execute_tool_call(tools, {"name": "shell_run", "command": "echo hello"})
    assert result.ok


def test_wants_project_tools_for_build_phrases():
    chat = RouteDecision("akomagni", "chat", 0.5, "x", "y")
    assert wants_project_tools("crée les fichiers maintenant", chat) is True
    assert wants_project_tools("juste une app de gestion", chat) is False
    build = RouteDecision("bmad-agent-dev", "bmad-build", 0.9, "x", "y")
    assert wants_project_tools("continue", build) is True


def test_run_agent_tool_turn_writes_files(tmp_path):
    decision = RouteDecision("bmad-agent-dev", "bmad-build", 0.9, "dev", "build")
    raw = (
        "Je prépare le fichier principal.\n"
        "<<<TOOL>>>\n"
        '{"name":"fs_write","path":"README.md","content":"# Todo app"}\n'
        "<<<END_TOOL>>>\n"
        "<<<DONE>>>"
    )

    def fake_chat(message, **kwargs):
        return raw

    seen: list[str] = []
    turn = run_agent_tool_turn(
        "crée les fichiers",
        decision,
        workspace=tmp_path,
        chat_fn=fake_chat,
        on_action=seen.append,
    )
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# Todo app"
    assert "README.md" in " ".join(turn.actions)
    assert "```" not in turn.user_reply
    assert turn.done is True
    assert seen


def test_run_agent_tool_turn_continues_then_finishes(tmp_path):
    decision = RouteDecision("bmad-agent-dev", "bmad-build", 0.9, "dev", "build")
    replies = iter(
        [
            (
                "Écriture en cours.\n"
                "<<<TOOL>>>\n"
                '{"name":"fs_write","path":"a.txt","content":"1"}\n'
                "<<<END_TOOL>>>"
            ),
            "Terminé sans outils. <<<DONE>>>",
        ]
    )

    def fake_chat(message, **kwargs):
        return next(replies)

    turn = run_agent_tool_turn(
        "crée les fichiers",
        decision,
        workspace=tmp_path,
        chat_fn=fake_chat,
        max_rounds=3,
    )
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "1"
    assert turn.done is True


def test_run_agent_tool_turn_no_tools_default_reply(tmp_path):
    decision = RouteDecision("bmad-agent-dev", "bmad-build", 0.9, "dev", "build")

    def fake_chat(message, **kwargs):
        return ""

    turn = run_agent_tool_turn("continue", decision, workspace=tmp_path, chat_fn=fake_chat)
    assert turn.user_reply
