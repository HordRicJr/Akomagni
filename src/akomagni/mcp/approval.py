"""Approval queue for destructive MCP agent operations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_REQUEST_ID_RE = re.compile(r"^[a-f0-9-]{8,36}$", re.IGNORECASE)


class ApprovalError(ValueError):
    """Raised when an approval operation cannot complete."""


@dataclass(frozen=True)
class PendingRequest:
    request_id: str
    tool: str
    summary: str
    payload: dict[str, object]
    created_at: str


def _pending_dir(workspace: Path) -> Path:
    directory = workspace / ".akomagni" / "mcp" / "pending"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _request_path(request_id: str, workspace: Path) -> Path:
    if not _REQUEST_ID_RE.match(request_id):
        raise ApprovalError(f"invalid request id: {request_id}")
    return _pending_dir(workspace) / f"{request_id}.json"


def queue_request(
    tool: str,
    summary: str,
    payload: dict[str, object],
    *,
    workspace: Path,
) -> PendingRequest:
    """Queue a destructive tool call for user approval."""
    request_id = uuid4().hex[:12]
    request = PendingRequest(
        request_id=request_id,
        tool=tool,
        summary=summary,
        payload=payload,
        created_at=datetime.now(UTC).isoformat(),
    )
    path = _request_path(request_id, workspace)
    path.write_text(
        json.dumps(
            {
                "request_id": request.request_id,
                "tool": request.tool,
                "summary": request.summary,
                "payload": request.payload,
                "created_at": request.created_at,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return request


def list_pending(*, workspace: Path) -> list[PendingRequest]:
    """List queued destructive operations."""
    directory = _pending_dir(workspace)
    requests: list[PendingRequest] = []
    for path in sorted(directory.glob("*.json")):
        requests.append(_load_request(path))
    return requests


def _load_request(path: Path) -> PendingRequest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PendingRequest(
        request_id=str(data["request_id"]),
        tool=str(data["tool"]),
        summary=str(data["summary"]),
        payload=dict(data.get("payload", {})),
        created_at=str(data.get("created_at", "")),
    )


def pop_request(request_id: str, *, workspace: Path) -> PendingRequest:
    """Load and remove a pending request."""
    path = _request_path(request_id, workspace)
    if not path.is_file():
        raise ApprovalError(f"pending request not found: {request_id}")
    request = _load_request(path)
    path.unlink()
    return request


def reject_request(request_id: str, *, workspace: Path) -> None:
    """Discard a pending request without executing it."""
    path = _request_path(request_id, workspace)
    if not path.is_file():
        raise ApprovalError(f"pending request not found: {request_id}")
    path.unlink()
