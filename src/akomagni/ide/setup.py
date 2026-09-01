"""Generate MCP configuration for Cursor / VS Code while the native IDE is in progress."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


class IdeSetupError(RuntimeError):
    """Raised when IDE/MCP setup cannot complete."""


@dataclass(frozen=True)
class IdeSetupResult:
    """Paths written during IDE/MCP setup."""

    workspace: Path
    cursor_config: Path
    vscode_config: Path
    akomagni_command: str


def resolve_akomagni_command() -> str:
    """Prefer the akomagni executable on PATH."""
    return shutil.which("akomagni") or "akomagni"


def build_mcp_config(
    workspace: Path,
    *,
    akomagni_command: str | None = None,
) -> dict:
    """Build Cursor-compatible MCP server config for Akomagni agent tools."""
    command = akomagni_command or resolve_akomagni_command()
    workspace_arg = str(workspace.resolve())
    return {
        "mcpServers": {
            "akomagni": {
                "command": command,
                "args": ["mcp", "serve", "--workspace", workspace_arg],
            }
        }
    }


def write_cursor_mcp_config(
    workspace: Path | None = None,
    *,
    overwrite: bool = False,
    akomagni_command: str | None = None,
) -> IdeSetupResult:
    """Write `.cursor/mcp.json` and `.vscode/mcp.json` for the workspace."""
    root = (workspace or Path.cwd()).resolve()
    if not root.is_dir():
        raise IdeSetupError(f"workspace does not exist: {root}")

    command = akomagni_command or resolve_akomagni_command()
    payload = build_mcp_config(root, akomagni_command=command)
    text = json.dumps(payload, indent=2) + "\n"

    cursor_dir = root / ".cursor"
    vscode_dir = root / ".vscode"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    vscode_dir.mkdir(parents=True, exist_ok=True)

    cursor_config = cursor_dir / "mcp.json"
    vscode_config = vscode_dir / "mcp.json"

    for path in (cursor_config, vscode_config):
        if path.exists() and not overwrite:
            raise IdeSetupError(
                f"{path} already exists — re-run with --force to overwrite, or merge manually."
            )

    cursor_config.write_text(text, encoding="utf-8")
    vscode_config.write_text(text, encoding="utf-8")

    return IdeSetupResult(
        workspace=root,
        cursor_config=cursor_config,
        vscode_config=vscode_config,
        akomagni_command=command,
    )


def ide_status(workspace: Path | None = None) -> dict[str, object]:
    """Summarize IDE/MCP readiness for the current workspace."""
    root = (workspace or Path.cwd()).resolve()
    cursor_config = root / ".cursor" / "mcp.json"
    vscode_config = root / ".vscode" / "mcp.json"

    agent_installed = True
    try:
        import mcp  # noqa: F401
    except ImportError:
        agent_installed = False

    return {
        "workspace": str(root),
        "cursor_config": cursor_config.exists(),
        "vscode_config": vscode_config.exists(),
        "agent_extra_installed": agent_installed,
        "akomagni_command": resolve_akomagni_command(),
        "native_ide": "planned-v1.0",
    }
