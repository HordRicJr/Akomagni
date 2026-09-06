"""Persisted CLI chat + workflow session context under ``.akomagni/workflow``."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from akomagni.flow.state import load_state, workflow_dir

_USER_BLOCK = re.compile(
    r"## User message\s*\n+(.*?)(?=\n## |\Z)",
    re.DOTALL | re.IGNORECASE,
)


def chat_history_path(project_root: Path) -> Path:
    return workflow_dir(project_root, discover=False) / "chat_history.json"


def load_chat_history(project_root: Path | None, *, limit: int = 24) -> list[dict[str, str]]:
    if project_root is None:
        return []
    path = chat_history_path(project_root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out[-limit:]


def save_chat_history(project_root: Path | None, messages: list[dict[str, str]]) -> None:
    if project_root is None:
        return
    path = chat_history_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in {"user", "assistant"} and str(m.get("content", "")).strip()
    ]
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_session_user_messages(project_root: Path, *, limit: int = 16) -> list[str]:
    """User turns recorded in Flow session markdown (oldest → newest)."""
    sessions = workflow_dir(project_root, discover=False) / "sessions"
    if not sessions.is_dir():
        return []
    files = sorted(sessions.glob("*.md"), key=lambda p: p.name)
    messages: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        match = _USER_BLOCK.search(text)
        if not match:
            continue
        body = match.group(1).strip()
        if body:
            messages.append(body)
    return messages[-limit:]


def prior_workflow_context(project_root: Path | None, *, max_chars: int = 6000) -> str:
    """Text block so the model resumes from ``.akomagni`` instead of re-asking."""
    if project_root is None:
        return ""
    root = project_root.resolve()
    state = load_state(root, discover=False)
    lines: list[str] = [
        "### Prior workflow context (from .akomagni — do NOT restart discovery)",
        f"Project: {root}",
        f"phase: {state.get('phase', 'n/a')}",
        f"active_skill: {state.get('active_skill', 'n/a')}",
        f"gates: {state.get('gates') or {}}",
        f"completed: {state.get('completed') or []}",
    ]
    turns = extract_session_user_messages(root)
    if turns:
        lines.append("Prior user messages (chronological):")
        for i, turn in enumerate(turns, 1):
            lines.append(f"{i}. {turn}")
    else:
        lines.append("No prior session user messages found.")
    lines.append(
        "If brainstorm already captured goals/constraints above, continue the app "
        "(build/files) instead of asking the same discovery questions again."
    )
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[:max_chars] + "\n…[truncated]"
    return text


def restore_sticky_skill(project_root: Path | None) -> str | None:
    """Active skill from workflow state, if it is a real BMAD/GDS skill."""
    if project_root is None:
        return None
    state = load_state(project_root, discover=False)
    skill = str(state.get("active_skill") or "").strip()
    if not skill or skill in {"chat", "image-pipeline"}:
        return None
    return skill


def is_resume_continue(message: str) -> bool:
    """True when the user wants to pick up existing work, not restart brainstorm."""
    from akomagni.inference.agent_loop import is_code_work_request

    if is_code_work_request(message):
        return True
    lowered = message.lower().strip()
    signals = (
        "on continue",
        "continuons",
        "continue l'app",
        "continue l app",
        "continue the app",
        "continue l'appli",
        "reprend",
        "on reprend",
        "reprends",
        "where we left",
        "où on en était",
        "ou on en etait",
        "keep going",
        "finis l'app",
        "finis l app",
        "termine l'app",
        "termine l app",
        "finish the app",
        "on reprend l",
        "reprendre l",
        "continue mon",
        "continue notre",
    )
    return any(s in lowered for s in signals)


def workflow_snapshot(project_root: Path | None) -> dict[str, Any]:
    if project_root is None:
        return {}
    return load_state(project_root, discover=False)
