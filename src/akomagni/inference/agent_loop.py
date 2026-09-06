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

_TOOL_OPEN = re.compile(r"<<<TOOL>>>\s*", re.IGNORECASE)
_TOOL_CLOSE = re.compile(r"<<<END_TOOL>>>", re.IGNORECASE)
_DONE_MARK = re.compile(r"<<<DONE>>>", re.IGNORECASE)

TOOL_INSTRUCTIONS = """
## Project tools (required for file work)
You are in IMPLEMENTATION mode. You MUST use tools to create real files on disk.
Do not paste long source code into the chat. The user sees your short status text + tool progress.

### Visibility (required)
1. First write 2-5 short sentences telling the user what you will do now
   (e.g. "Je crée le projet React + localStorage, puis j'installe npm et je lance le serveur.").
2. Then emit tool calls.
3. After tools, summarize what succeeded and the next step (or <<<DONE>>>).

### Tool format (exact)
<<<TOOL>>>
{"name":"fs_write","path":"relative/path.ext","content":"file contents here"}
<<<END_TOOL>>>

Available tools:
- fs_write: {"name":"fs_write","path":"...","content":"..."}
- fs_read: {"name":"fs_read","path":"..."}
- fs_list: {"name":"fs_list","path":"."}
- shell_run: {"name":"shell_run","command":"npm install"}
- shell_bg: {"name":"shell_bg","command":"npm run dev"}  (long-running: Vite/dev server)
- open_url: {"name":"open_url","url":"http://127.0.0.1:5173"}

### Scaffolding rules
- The workspace already has `.akomagni/` — do NOT run `npm create vite@latest .` (fails: dir not empty).
- Prefer writing Vite+React files with fs_write (package.json, vite.config.js, index.html, src/*), then `npm install`.
- Use non-interactive commands only (no prompts).
- When the app is ready: shell_bg `npm run dev` (or `npx vite`), then open_url the local URL, then <<<DONE>>>.
- End user-visible text with the URL (usually http://127.0.0.1:5173).
""".strip()

_BUILD_SIGNALS = (
    "on continue",
    "continuons",
    "continue l'app",
    "continue l app",
    "reprends",
    "on reprend",
    "crée les fichier",
    "creer les fichier",
    "crée le fichier",
    "creer le fichier",
    "create the file",
    "write the file",
    "fais l'app",
    "fais l app",
    "fais le site",
    "fais tout",
    "oui fais",
    "vas y",
    "vas-y",
    "go ahead",
    "do it",
    "build the app",
    "génère le projet",
    "genere le projet",
    "génère le fichier",
    "genere le fichier",
    "scaffold",
    "npm create",
    "vite",
    "implemente",
    "implémente",
    "implemente moi",
    "implémente moi",
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
    cleaned = text
    while True:
        open_m = _TOOL_OPEN.search(cleaned)
        if not open_m:
            break
        close_m = _TOOL_CLOSE.search(cleaned, open_m.end())
        if not close_m:
            cleaned = cleaned[: open_m.start()].rstrip()
            break
        cleaned = (cleaned[: open_m.start()] + cleaned[close_m.end() :]).strip()
    cleaned = _DONE_MARK.sub("", cleaned)
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Parse tool JSON between <<<TOOL>>> … <<<END_TOOL>>> (supports `}` inside content)."""
    calls: list[dict[str, Any]] = []
    pos = 0
    decoder = json.JSONDecoder()
    while True:
        open_m = _TOOL_OPEN.search(text, pos)
        if not open_m:
            break
        close_m = _TOOL_CLOSE.search(text, open_m.end())
        if not close_m:
            break
        raw = text[open_m.end() : close_m.start()].strip()
        pos = close_m.end()
        payload: Any = None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            brace = raw.find("{")
            if brace < 0:
                continue
            try:
                payload, _ = decoder.raw_decode(raw[brace:])
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
    if name == "shell_bg":
        return tools.shell_bg(str(call.get("command", "")), cwd=call.get("cwd"))  # type: ignore[arg-type]
    if name in {"open_url", "open_browser"}:
        return tools.open_url(str(call.get("url", "") or call.get("path", "")))
    return ToolResult(ok=False, output=f"unknown tool: {name}")


@dataclass
class AgentTurnResult:
    user_reply: str
    actions: list[str] = field(default_factory=list)
    done: bool = False
    raw: str = ""
    urls: list[str] = field(default_factory=list)


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
    max_rounds: int = 8,
    auto_approve: bool = True,
    on_action: Callable[[str], None] | None = None,
    on_announce: Callable[[str], None] | None = None,
    on_result: Callable[[str, bool], None] | None = None,
) -> AgentTurnResult:
    """Ask the model to work with tools; return a short user-facing summary."""
    tools = AgentTools(workspace, auto_approve=auto_approve, shell_timeout=180)
    system = build_flow_system_prompt(
        decision,
        rag_context=rag_context,
        skill_guidance=skill_guidance,
        tools_enabled=True,
    )
    system = f"{system}\n\n{TOOL_INSTRUCTIONS}\nWorkspace root: {workspace}"
    runner = chat_fn or chat_completion
    working_history = list(history or [])
    actions: list[str] = []
    urls: list[str] = []
    last_raw = ""
    visible = ""
    announces: list[str] = []

    user_message = (
        f"{message}\n\n"
        "(Reminder: announce briefly, then use tools. Prefer fs_write for React/Vite files "
        "because this folder already contains .akomagni. After npm install, shell_bg the "
        "dev server and open_url http://127.0.0.1:5173.)"
    )
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
        if visible:
            announces.append(visible)
            if on_announce:
                on_announce(visible)
        if not calls:
            break

        working_history.append({"role": "user", "content": user_message})
        working_history.append({"role": "assistant", "content": last_raw})
        results: list[str] = []
        for call in calls:
            name = str(call.get("name", "tool"))
            path = str(call.get("path") or call.get("command") or call.get("url") or "")
            label = f"{name} {path}".strip()
            if on_action:
                on_action(label)
            result = execute_tool_call(tools, call)
            status = "ok" if result.ok else "error"
            line = f"{status}: {label} — {result.output[:800]}"
            actions.append(line)
            results.append(line)
            if on_result:
                on_result(line, result.ok)
            if name in {"open_url", "open_browser"} and result.ok and path:
                urls.append(path)
            if name == "shell_bg" and result.ok:
                for match in re.finditer(r"https?://[^\s]+", result.output):
                    urls.append(match.group(0).rstrip(".,)"))
        if _DONE_MARK.search(last_raw):
            reply = visible or "Travail terminé dans le projet."
            if urls and "http" not in reply.lower():
                reply = f"{reply}\n\nOuvre: {urls[-1]}"
            return AgentTurnResult(
                user_reply=reply,
                actions=actions,
                done=True,
                raw=last_raw,
                urls=urls,
            )
        user_message = (
            "Tool results:\n"
            + "\n".join(results)
            + "\nContinue with more tools if needed. Announce briefly what you do next. "
            "Do not paste source code to the user. When the app runs, shell_bg the server, "
            "open_url, then <<<DONE>>>."
        )

    done = bool(_DONE_MARK.search(last_raw))
    if not visible:
        visible = (
            "J'ai travaillé dans le projet."
            if actions
            else "Dis-moi la prochaine étape (fichiers à créer, stack, etc.)."
        )
    if urls and "http" not in visible.lower():
        visible = f"{visible}\n\nOuvre: {urls[-1]}"
    elif announces and not visible:
        visible = announces[-1]
    return AgentTurnResult(
        user_reply=visible,
        actions=actions,
        done=done,
        raw=last_raw,
        urls=urls,
    )
