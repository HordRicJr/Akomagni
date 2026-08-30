"""Memory auto-capture with user approval."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from akomagni.memory.ops import MemoryError, add_memory

_CAPTURE_ID_RE = re.compile(r"^[a-f0-9-]{8,36}$", re.IGNORECASE)


class CaptureError(ValueError):
    """Raised when a capture operation cannot complete."""


@dataclass(frozen=True)
class CaptureProposal:
    capture_id: str
    user_message: str
    assistant_reply: str
    suggested_text: str
    suggested_title: str
    created_at: str
    global_: bool


def _pending_dir(*, global_: bool, project_root: Path | None = None) -> Path:
    if global_:
        from akomagni.core.config import MEMORY_DIR

        base = MEMORY_DIR
    else:
        root = project_root or Path.cwd()
        base = root / ".akomagni" / "memory"
    directory = base / "pending"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _proposal_path(capture_id: str, *, global_: bool, project_root: Path | None = None) -> Path:
    if not _CAPTURE_ID_RE.match(capture_id):
        raise CaptureError(f"invalid capture id: {capture_id}")
    return _pending_dir(global_=global_, project_root=project_root) / f"{capture_id}.json"


def _title_from_message(message: str) -> str:
    first = message.strip().splitlines()[0]
    return first[:80] if first else "Captured learning"


def build_capture_text(user_message: str, assistant_reply: str) -> str:
    """Format a learning note from a user/assistant exchange."""
    user = user_message.strip()
    reply = assistant_reply.strip()
    if not user or not reply:
        raise CaptureError("user message and assistant reply are required")
    return f"## Context\n\nUser asked:\n\n{user}\n\n## Learning\n\n{reply}\n"


def propose_capture(
    user_message: str,
    assistant_reply: str,
    *,
    global_: bool = False,
    project_root: Path | None = None,
) -> CaptureProposal:
    """Create a pending capture awaiting approval."""
    suggested_text = build_capture_text(user_message, assistant_reply)
    capture_id = uuid4().hex[:12]
    proposal = CaptureProposal(
        capture_id=capture_id,
        user_message=user_message.strip(),
        assistant_reply=assistant_reply.strip(),
        suggested_text=suggested_text,
        suggested_title=_title_from_message(user_message),
        created_at=datetime.now(UTC).isoformat(),
        global_=global_,
    )
    path = _proposal_path(capture_id, global_=global_, project_root=project_root)
    path.write_text(
        json.dumps(
            {
                "capture_id": proposal.capture_id,
                "user_message": proposal.user_message,
                "assistant_reply": proposal.assistant_reply,
                "suggested_text": proposal.suggested_text,
                "suggested_title": proposal.suggested_title,
                "created_at": proposal.created_at,
                "global": proposal.global_,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return proposal


def list_pending(
    *, global_: bool = False, project_root: Path | None = None
) -> list[CaptureProposal]:
    """List pending capture proposals."""
    directory = _pending_dir(global_=global_, project_root=project_root)
    proposals: list[CaptureProposal] = []
    for path in sorted(directory.glob("*.json")):
        proposals.append(_load_proposal(path))
    return proposals


def _load_proposal(path: Path) -> CaptureProposal:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CaptureProposal(
        capture_id=str(data["capture_id"]),
        user_message=str(data["user_message"]),
        assistant_reply=str(data["assistant_reply"]),
        suggested_text=str(data["suggested_text"]),
        suggested_title=str(data.get("suggested_title", "Captured learning")),
        created_at=str(data.get("created_at", "")),
        global_=bool(data.get("global", False)),
    )


def approve_capture(
    capture_id: str,
    *,
    global_: bool = False,
    project_root: Path | None = None,
    title: str | None = None,
) -> Path:
    """Approve a pending capture and persist it as a learning."""
    path = _proposal_path(capture_id, global_=global_, project_root=project_root)
    if not path.is_file():
        raise CaptureError(f"pending capture not found: {capture_id}")
    proposal = _load_proposal(path)
    try:
        saved = add_memory(
            proposal.suggested_text,
            global_=proposal.global_,
            title=title or proposal.suggested_title,
            project_root=project_root,
        )
    except MemoryError as exc:
        raise CaptureError(str(exc)) from exc
    path.unlink()
    return saved


def reject_capture(
    capture_id: str,
    *,
    global_: bool = False,
    project_root: Path | None = None,
) -> None:
    """Discard a pending capture without saving."""
    path = _proposal_path(capture_id, global_=global_, project_root=project_root)
    if not path.is_file():
        raise CaptureError(f"pending capture not found: {capture_id}")
    path.unlink()


def maybe_prompt_capture(
    user_message: str,
    assistant_reply: str,
    *,
    global_: bool = False,
    project_root: Path | None = None,
    approved: bool,
) -> CaptureProposal | Path | None:
    """Save immediately when approved, otherwise queue for later review."""
    if approved:
        text = build_capture_text(user_message, assistant_reply)
        return add_memory(
            text,
            global_=global_,
            title=_title_from_message(user_message),
            project_root=project_root,
        )
    return propose_capture(
        user_message,
        assistant_reply,
        global_=global_,
        project_root=project_root,
    )
