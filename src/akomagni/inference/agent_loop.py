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
# Models often emit: [TOOL_CALLS]fs_write{"name":"fs_write",...}
_ALT_TOOL_HEAD = re.compile(r"\[TOOL_CALLS\]\s*([a-zA-Z_][\w]*)\s*", re.IGNORECASE)

TOOL_INSTRUCTIONS = """
## Project tools (required for file work)
You are in IMPLEMENTATION mode. You MUST use tools to create/read real files on disk.
Do not paste long source code into the chat. The user sees your short status text + tool progress.

### Visibility (required)
1. First write 2-5 short sentences telling the user what you will do now.
2. Then emit tool calls in the EXACT format below (nothing else).
3. After tools, summarize what succeeded and the next step (or <<<DONE>>>).

### Tool format (ONLY this — never [TOOL_CALLS] or bare fs_write{)
<<<TOOL>>>
{"name":"fs_write","path":"relative/path.ext","content":"file contents here"}
<<<END_TOOL>>>

Available tools:
- fs_write: {"name":"fs_write","path":"...","content":"..."}
- fs_read: {"name":"fs_read","path":"..."}  — read a file before fixing it
- fs_list: {"name":"fs_list","path":"."}    — list project files
- shell_run: {"name":"shell_run","command":"npm install"}
- shell_bg: {"name":"shell_bg","command":"npm run dev"}
- open_url: {"name":"open_url","url":"http://127.0.0.1:5173"}

### Debugging / fixes
- ALWAYS fs_list + fs_read the failing files BEFORE writing fixes.
- For Vite "Failed to resolve import ./X", create the missing file with fs_write.
- For React+Vite apps, ensure at least: index.html, vite.config.js, package.json,
  src/main.jsx, src/App.jsx, src/index.css.
- When asked to launch the server: shell_bg `npm run dev`, then open_url the returned url.
- If shell_bg fails, show the error and fix — do not claim the site is online.

### Scaffolding rules
- Workspace may already have `.akomagni/` — do NOT run `npm create vite@latest .`.
- Prefer fs_write for source files, then `npm install` if needed.
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
    "npm run",
    "vite",
    "implemente",
    "implémente",
    "implemente moi",
    "implémente moi",
    "commence à coder",
    "commence a coder",
    "code l'app",
    "code l app",
    "lance le serveur",
    "lancer le serveur",
    "lance serveur",
    "start the server",
    "start server",
    "run the server",
    "corrige",
    "fix the",
    "fix error",
    "erreur",
    "error",
    "failed to resolve",
    "import-analysis",
    "analyse les fichier",
    "analyze the file",
    "fichier manquant",
    "missing file",
    "index.css",
    "does the file exist",
)


def is_code_work_request(message: str) -> bool:
    """True when the user wants server/fix/file work (not brainstorm talk)."""
    lowered = message.lower()
    return any(sig in lowered for sig in _BUILD_SIGNALS)


def wants_project_tools(message: str, decision: RouteDecision) -> bool:
    """True when the turn should use sandboxed project tools."""
    if is_implementation_skill(decision.skill):
        return True
    if decision.skill in {"bmad-build", "bmad-quick-dev", "gds-quick-dev"}:
        return True
    # UX/arch often get routed on "css/import" words — still need real file tools.
    return is_code_work_request(message)


def _decode_json_object(text: str, start: int = 0) -> tuple[dict[str, Any] | None, int]:
    decoder = json.JSONDecoder()
    slice_ = text[start:].lstrip()
    if not slice_.startswith("{"):
        brace = slice_.find("{")
        if brace < 0:
            return None, start
        slice_ = slice_[brace:]
        start = len(text) - len(slice_)
    try:
        payload, consumed = decoder.raw_decode(slice_)
    except json.JSONDecodeError:
        return None, start
    if isinstance(payload, dict):
        return payload, start + consumed
    return None, start


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Parse <<<TOOL>>> blocks and common model variants like [TOOL_CALLS]fs_write{...}."""
    calls: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(payload: dict[str, Any]) -> None:
        name = str(payload.get("name", "")).strip()
        if not name:
            return
        key = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if key in seen:
            return
        seen.add(key)
        calls.append(payload)

    pos = 0
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
            payload, _ = _decode_json_object(raw, 0)
            payload = payload or None
        if isinstance(payload, dict):
            _add(payload)

    # Alternate: [TOOL_CALLS]fs_write{...}[TOOL_CALLS]fs_read{...}
    for match in _ALT_TOOL_HEAD.finditer(text):
        tool_name = match.group(1).strip()
        payload, _ = _decode_json_object(text, match.end())
        if not payload:
            continue
        payload.setdefault("name", tool_name)
        # Some models put the tool name only in the prefix.
        if str(payload.get("name", "")).lower() in {"", "tool"}:
            payload["name"] = tool_name
        _add(payload)

    return calls


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

    # Strip [TOOL_CALLS]name{json}
    while True:
        match = _ALT_TOOL_HEAD.search(cleaned)
        if not match:
            break
        payload, end = _decode_json_object(cleaned, match.end())
        if payload is None:
            cleaned = cleaned[: match.start()] + cleaned[match.end() :]
            continue
        cleaned = (cleaned[: match.start()] + cleaned[end:]).strip()

    cleaned = _DONE_MARK.sub("", cleaned)
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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
    provider: str = "local",
    auth_mode: str = "api_key",
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
    format_nudge_used = False

    user_message = (
        f"{message}\n\n"
        "(Reminder: fs_list/fs_read before fixes. Use ONLY <<<TOOL>>> JSON <<<END_TOOL>>> "
        "blocks — never [TOOL_CALLS]. For Vite apps create missing src/index.css etc. "
        "Then shell_bg npm run dev and open_url when asked to launch.)"
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
            provider=provider,
            auth_mode=auth_mode,
        )
        calls = parse_tool_calls(last_raw)
        visible = strip_tool_markup(last_raw)
        if visible:
            announces.append(visible)
            if on_announce:
                on_announce(visible)

        if (
            not calls
            and not format_nudge_used
            and ("[TOOL_CALLS]" in last_raw or "fs_write" in last_raw or "fs_read" in last_raw)
        ):
            # Parsed nothing useful — force a format retry once.
            format_nudge_used = True
            working_history.append({"role": "user", "content": user_message})
            working_history.append({"role": "assistant", "content": last_raw})
            user_message = (
                "Your previous tool markup was not executable. "
                "Retry NOW using ONLY this format (one or more blocks):\n"
                "<<<TOOL>>>\n"
                '{"name":"fs_write","path":"src/index.css","content":"body{}"}\n'
                "<<<END_TOOL>>>\n"
                "First fs_list '.', then fs_read failing files, then fs_write fixes."
            )
            continue

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
            # Cap huge fs_read dumps in the action log, keep full text for the model.
            shown = result.output[:800]
            line = f"{status}: {label} — {shown}"
            actions.append(line)
            results.append(f"{status}: {label} — {result.output[:4000]}")
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
            + "\nContinue with more tools if needed. Announce briefly. "
            "Use <<<TOOL>>> JSON <<<END_TOOL>>> only. "
            "When the app runs, shell_bg then open_url, then <<<DONE>>>."
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
