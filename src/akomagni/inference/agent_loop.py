"""CLI agent loop: model announces work, tools write/run inside the project."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from akomagni.flow.intent import RouteDecision
from akomagni.inference.chat import build_flow_system_prompt
from akomagni.inference.client import chat_completion
from akomagni.mcp.tools import AgentTools, ToolResult
from akomagni.skills.invoke import is_implementation_skill

_TOOL_BLOCK = re.compile(
    r"<<<TOOL>>>\s*(\{.*?\})\s*<<<END_TOOL>>>",
    re.DOTALL | re.IGNORECASE,
)
_DONE_MARK = re.compile(r"<<<DONE>>>", re.IGNORECASE)

TOOL_INSTRUCTIONS = """
## Project tools (required for file work)
You can modify the user's project with tools. Prefer tools over pasting source code.

Rules:
- Never dump full source files or long code blocks in the user-visible reply.
- Tell the user briefly what you are doing (1-3 short sentences).
- Emit zero or more tool calls using exactly this format:

<<<TOOL>>>
{"name":"fs_write","path":"relative/path.ext","content":"file contents here"}
<<<END_TOOL>>>

Available tools:
- fs_write: {"name":"fs_write","path":"...","content":"..."}
- fs_read: {"name":"fs_read","path":"..."}
- fs_list: {"name":"fs_list","path":"."}
- shell_run: {"name":"shell_run","command":"npm create vite@latest . -- --template react"}

After tools for this turn, either ask one short question OR end with <<<DONE>>> when the requested work is finished.
Keep user-visible text free of code fences unless the user explicitly asks to see code.
""".strip()

_BUILD_SIGNALS = (
    "crée les fichier",
    "creer les fichier",
    "create the file",
    "write the file",
    "fais l'app",
    "fais l app",
    "fais le site",
    "build the app",
    "génère le projet",
    "genere le projet",
    "scaffold",
    "npm create",
    "vite",
    "implemente",
    "implémente",
    "commence à coder",
    "commence a coder",
    "code l'app",
    "code l app",
)


def wants_project_tools(message: str, decision: RouteDecision) -> bool:
    """True when the turn should use sandboxed project tools."""
    if is_implementation_skill(decision.skill):
        return True
    if decision.skill in {"bmad-build", "bmad-quick-dev", "gds-quick-dev"}:
        return True
    lowered = message.lower()
    return any(sig in lowered for sig in _BUILD_SIGNALS)


def strip_tool_markup(text: str) -> str:
    """Remove tool blocks / done markers for the user-visible reply."""
    cleaned = _TOOL_BLOCK.sub("", text)
    cleaned = _DONE_MARK.sub("", cleaned)
    # Drop accidental fenced code if tools were used (keep short inline ticks).
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in _TOOL_BLOCK.finditer(text):
        raw = match.group(1).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("name"):
            calls.append(payload)
    return calls


def execute_tool_call(tools: AgentTools, call: dict[str, Any]) -> ToolResult:
    name = str(call.get("name", "")).strip().lower()
    if name == "fs_write":
        return tools.fs_write(str(call.get("path", "")), str(call.get("content", "")))
    if name == "fs_read":
        return tools.fs_read(str(call.get("path", "")))
    if name == "fs_list":
        return tools.fs_list(str(call.get("path", ".") or "."))
    if name == "shell_run":
        return tools.shell_run(str(call.get("command", "")), cwd=call.get("cwd"))  # type: ignore[arg-type]
    return ToolResult(ok=False, output=f"unknown tool: {name}")


@dataclass
class AgentTurnResult:
    user_reply: str
    actions: list[str] = field(default_factory=list)
    done: bool = False
    raw: str = ""


def run_agent_tool_turn(
    message: str,
    decision: RouteDecision,
    *,
    workspace: Path,
    history: list[dict[str, str]] | None = None,
    skill_guidance: str = "",
    rag_context: str = "",
    chat_fn: Callable[..., str] | None = None,
    host: str = "127.0.0.1",
    port: int = 8787,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    max_rounds: int = 4,
    auto_approve: bool = True,
    on_action: Callable[[str], None] | None = None,
) -> AgentTurnResult:
    """Ask the model to work with tools; return a short user-facing summary."""
    tools = AgentTools(workspace, auto_approve=auto_approve)
    system = build_flow_system_prompt(
        decision,
        rag_context=rag_context,
        skill_guidance=skill_guidance,
    )
    system = f"{system}\n\n{TOOL_INSTRUCTIONS}\nWorkspace root: {workspace}"
    runner = chat_fn or chat_completion
    working_history = list(history or [])
    actions: list[str] = []
    last_raw = ""
    visible = ""

    user_message = message
    for _ in range(max(1, max_rounds)):
        last_raw = runner(
            user_message,
            host=host,
            port=port,
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_prompt=system,
            history=working_history,
        )
        calls = parse_tool_calls(last_raw)
        visible = strip_tool_markup(last_raw)
        if not calls:
            break

        working_history.append({"role": "user", "content": user_message})
        working_history.append({"role": "assistant", "content": last_raw})
        results: list[str] = []
        for call in calls:
            name = str(call.get("name", "tool"))
            path = str(call.get("path") or call.get("command") or "")
            label = f"{name} {path}".strip()
            if on_action:
                on_action(label)
            result = execute_tool_call(tools, call)
            status = "ok" if result.ok else "error"
            line = f"{status}: {label} — {result.output[:500]}"
            actions.append(line)
            results.append(line)
        if _DONE_MARK.search(last_raw):
            return AgentTurnResult(
                user_reply=visible or "Travail terminé dans le projet.",
                actions=actions,
                done=True,
                raw=last_raw,
            )
        user_message = (
            "Tool results:\n" + "\n".join(results) + "\nContinue. Prefer more tools if needed. "
            "Do not paste source code to the user. End with <<<DONE>>> when finished."
        )

    done = bool(_DONE_MARK.search(last_raw))
    if not visible:
        visible = (
            "J'ai travaillé dans le projet."
            if actions
            else "Dis-moi la prochaine étape (fichiers à créer, stack, etc.)."
        )
    return AgentTurnResult(user_reply=visible, actions=actions, done=done, raw=last_raw)
