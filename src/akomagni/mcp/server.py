"""MCP stdio server exposing sandboxed agent tools."""

from __future__ import annotations

from pathlib import Path

from akomagni.mcp.sandbox import resolve_workspace
from akomagni.mcp.tools import AgentTools


def build_server(
    workspace: Path | None = None,
    *,
    auto_approve: bool = False,
    shell_timeout: int = 30,
):
    """Create a FastMCP server for agent tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP server requires the optional 'agent' extra: pip install 'akomagni[agent]'"
        ) from exc

    root = resolve_workspace(workspace)
    tools = AgentTools(root, auto_approve=auto_approve, shell_timeout=shell_timeout)
    mcp = FastMCP("Akomagni Agent Tools")

    def _text(result) -> str:
        if result.pending is not None:
            return result.output
        if not result.ok:
            return f"ERROR: {result.output}"
        return result.output

    @mcp.tool()
    def fs_read(path: str) -> str:
        """Read a UTF-8 text file inside the workspace."""
        return _text(tools.fs_read(path))

    @mcp.tool()
    def fs_write(path: str, content: str) -> str:
        """Write a UTF-8 text file inside the workspace (overwrite needs approval)."""
        return _text(tools.fs_write(path, content))

    @mcp.tool()
    def fs_list(path: str = ".") -> str:
        """List files and directories inside the workspace."""
        return _text(tools.fs_list(path))

    @mcp.tool()
    def fs_delete(path: str) -> str:
        """Delete a file or empty directory (requires approval)."""
        return _text(tools.fs_delete(path))

    @mcp.tool()
    def shell_run(command: str, cwd: str | None = None) -> str:
        """Run a shell command in the workspace (destructive commands need approval)."""
        return _text(tools.shell_run(command, cwd=cwd))

    @mcp.tool()
    def git_status() -> str:
        """Show git status for the workspace."""
        return _text(tools.git_status())

    @mcp.tool()
    def git_diff(ref: str = "") -> str:
        """Show git diff, optionally against a ref."""
        return _text(tools.git_diff(ref))

    @mcp.tool()
    def git_log(limit: int = 10) -> str:
        """Show recent git commits."""
        return _text(tools.git_log(limit))

    @mcp.tool()
    def git_push(remote: str = "origin", branch: str | None = None) -> str:
        """Push commits to a remote (requires approval)."""
        return _text(tools.git_push(remote, branch))

    return mcp


def run_stdio_server(
    workspace: Path | None = None,
    *,
    auto_approve: bool = False,
    shell_timeout: int = 30,
) -> None:
    """Run the MCP stdio server."""
    build_server(
        workspace,
        auto_approve=auto_approve,
        shell_timeout=shell_timeout,
    ).run()
