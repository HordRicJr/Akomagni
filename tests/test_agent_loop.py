"""Agent tool-loop parsing and execution."""

from __future__ import annotations

import json

from akomagni.flow.intent import RouteDecision
from akomagni.inference.agent_loop import (
    execute_tool_call,
    is_code_work_request,
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


def test_parse_tool_json_with_braces_in_content():
    """Regression: JSX/content with `}` must not truncate JSON parsing."""
    content = 'export default function App() {\n  return <div className="x">{ok}</div>;\n}\n'
    payload = {"name": "fs_write", "path": "src/App.jsx", "content": content}
    raw = f"ok\n<<<TOOL>>>\n{json.dumps(payload)}\n<<<END_TOOL>>>\n"
    calls = parse_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["path"] == "src/App.jsx"
    assert "return <div" in calls[0]["content"]
    assert calls[0]["content"].count("}") >= 2


def test_parse_bracket_tool_calls_variant():
    raw = (
        "Je crée le CSS.\n"
        '[TOOL_CALLS]fs_write{"name":"fs_write","path":"src/index.css","content":"body{margin:0}"}\n'
        '[TOOL_CALLS]fs_read{"name":"fs_read","path":"src/main.jsx"}'
    )
    calls = parse_tool_calls(raw)
    assert len(calls) == 2
    assert calls[0]["path"] == "src/index.css"
    assert "margin:0" in calls[0]["content"]
    assert calls[1]["name"] == "fs_read"
    visible = strip_tool_markup(raw)
    assert "[TOOL_CALLS]" not in visible
    assert "crée le CSS" in visible


def test_code_work_signals_enable_tools():
    chat = RouteDecision("akomagni", "chat", 0.5, "x", "y")
    assert is_code_work_request("lance le serveur") is True
    assert wants_project_tools("lance le serveur", chat) is True
    assert (
        wants_project_tools(
            'Failed to resolve import "./index.css" from "src/main.jsx"',
            chat,
        )
        is True
    )
    ux = RouteDecision("bmad-agent-ux-designer", "bmad-ux", 0.85, "x", "y")
    assert wants_project_tools("corrige l'erreur d'import", ux) is True


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
    assert wants_project_tools("vas y", chat) is True
    assert wants_project_tools("Oui fais tout en même temps", chat) is True
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


def test_run_agent_tool_turn_summary_after_tools_without_done(tmp_path):
    decision = RouteDecision("bmad-agent-dev", "bmad-build", 0.9, "dev", "build")
    replies = iter(
        [
            ('<<<TOOL>>>\n{"name":"fs_write","path":"x.txt","content":"x"}\n<<<END_TOOL>>>'),
            "",
        ]
    )

    def fake_chat(message, **kwargs):
        return next(replies)

    turn = run_agent_tool_turn(
        "crée les fichiers",
        decision,
        workspace=tmp_path,
        chat_fn=fake_chat,
        max_rounds=2,
    )
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "x"
    assert turn.actions
    assert turn.user_reply
