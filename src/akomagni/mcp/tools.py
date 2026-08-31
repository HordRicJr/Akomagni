"""Sandboxed fs, shell, and git tools for MCP agent mode."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from akomagni.mcp.approval import PendingRequest, queue_request
from akomagni.mcp.sandbox import SandboxError, resolve_path

_DESTRUCTIVE_SHELL = re.compile(
    r"(?:^|\s)(?:rm\s+-rf|rm\s+-r|rm\s+-f|\brm\s+\S|del\s+/|rmdir\s+/s|"
    r"Remove-Item\s+.*-Recurse|git\s+push|git\s+reset\s+--hard|"
    r"git\s+clean\s+-[a-z]*f|git\s+branch\s+-D|format\s+[a-z]:|shutdown\b)",
    re.IGNORECASE,
)


class ToolError(RuntimeError):
    """Raised when a tool call fails."""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str
    pending: PendingRequest | None = None


class AgentTools:
    """Execute agent tools inside a workspace sandbox."""

    def __init__(
        self,
        workspace: Path,
        *,
        auto_approve: bool = False,
        shell_timeout: int = 30,
    ) -> None:
        self.workspace = workspace.resolve()
        self.auto_approve = auto_approve
        self.shell_timeout = shell_timeout

    def _maybe_queue(
        self,
        tool: str,
        summary: str,
        payload: dict[str, object],
        *,
        approved: bool,
        executor,
    ) -> ToolResult:
        if approved or self.auto_approve:
            return executor()
        pending = queue_request(tool, summary, payload, workspace=self.workspace)
        return ToolResult(
            ok=False,
            output=(
                f"Approval required for destructive operation. "
                f"Run: akomagni mcp approve {pending.request_id}"
            ),
            pending=pending,
        )

    def fs_read(self, path: str) -> ToolResult:
        try:
            target = resolve_path(path, self.workspace)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc))
        if not target.is_file():
            return ToolResult(ok=False, output=f"file not found: {path}")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(ok=False, output=f"not a UTF-8 text file: {path}")
        return ToolResult(ok=True, output=content)

    def fs_write(self, path: str, content: str, *, approved: bool = False) -> ToolResult:
        try:
            target = resolve_path(path, self.workspace)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc))

        def _write() -> ToolResult:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(ok=True, output=f"wrote {len(content)} bytes to {path}")

        if target.exists():
            return self._maybe_queue(
                "fs_write",
                f"overwrite file {path}",
                {"path": path, "content": content},
                approved=approved,
                executor=_write,
            )
        return _write()

    def fs_list(self, path: str = ".") -> ToolResult:
        try:
            target = resolve_path(path, self.workspace)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc))
        if not target.is_dir():
            return ToolResult(ok=False, output=f"not a directory: {path}")
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"{'[dir]' if entry.is_dir() else '[file]'} {entry.name}" for entry in entries]
        return ToolResult(ok=True, output="\n".join(lines) if lines else "(empty)")

    def fs_delete(self, path: str, *, approved: bool = False) -> ToolResult:
        try:
            target = resolve_path(path, self.workspace)
        except SandboxError as exc:
            return ToolResult(ok=False, output=str(exc))
        if not target.exists():
            return ToolResult(ok=False, output=f"path not found: {path}")

        def _delete() -> ToolResult:
            if target.is_dir():
                target.rmdir()
            else:
                target.unlink()
            return ToolResult(ok=True, output=f"deleted {path}")

        return self._maybe_queue(
            "fs_delete",
            f"delete {path}",
            {"path": path},
            approved=approved,
            executor=_delete,
        )

    def shell_run(
        self, command: str, *, cwd: str | None = None, approved: bool = False
    ) -> ToolResult:
        command = command.strip()
        if not command:
            return ToolResult(ok=False, output="command is required")
        workdir = self.workspace
        if cwd:
            try:
                workdir = resolve_path(cwd, self.workspace)
            except SandboxError as exc:
                return ToolResult(ok=False, output=str(exc))
        if not workdir.is_dir():
            return ToolResult(ok=False, output=f"working directory not found: {cwd or '.'}")

        def _run() -> ToolResult:
            try:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=self.shell_timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ToolResult(ok=False, output=f"command timed out after {self.shell_timeout}s")
            output = (completed.stdout or "") + (completed.stderr or "")
            if completed.returncode != 0:
                return ToolResult(
                    ok=False,
                    output=f"exit {completed.returncode}\n{output}".strip(),
                )
            return ToolResult(ok=True, output=output.strip() or "(no output)")

        if _DESTRUCTIVE_SHELL.search(command):
            return self._maybe_queue(
                "shell_run",
                f"shell: {command[:120]}",
                {"command": command, "cwd": cwd},
                approved=approved,
                executor=_run,
            )
        return _run()

    def _git(
        self, args: list[str], *, approved: bool = False, destructive: bool = False
    ) -> ToolResult:
        def _run() -> ToolResult:
            try:
                completed = subprocess.run(
                    ["git", *args],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=self.shell_timeout,
                    check=False,
                )
            except FileNotFoundError:
                return ToolResult(ok=False, output="git executable not found")
            except subprocess.TimeoutExpired:
                return ToolResult(ok=False, output=f"git timed out after {self.shell_timeout}s")
            output = (completed.stdout or "") + (completed.stderr or "")
            if completed.returncode != 0:
                return ToolResult(
                    ok=False,
                    output=f"exit {completed.returncode}\n{output}".strip(),
                )
            return ToolResult(ok=True, output=output.strip() or "(no output)")

        summary = f"git {' '.join(args)}"
        if destructive:
            return self._maybe_queue(
                "git",
                summary,
                {"args": args},
                approved=approved,
                executor=_run,
            )
        return _run()

    def git_status(self) -> ToolResult:
        return self._git(["status", "--short", "--branch"])

    def git_diff(self, ref: str = "") -> ToolResult:
        args = ["diff"]
        if ref.strip():
            args.append(ref.strip())
        return self._git(args)

    def git_log(self, limit: int = 10) -> ToolResult:
        count = max(1, min(limit, 50))
        return self._git(["log", f"-{count}", "--oneline"])

    def git_push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        approved: bool = False,
    ) -> ToolResult:
        args = ["push", remote]
        if branch:
            args.append(branch)
        return self._git(args, approved=approved, destructive=True)

    def execute_pending(self, request: PendingRequest) -> ToolResult:
        """Run a previously approved destructive operation."""
        tool = request.tool
        payload = request.payload
        if tool == "fs_delete":
            return self.fs_delete(str(payload["path"]), approved=True)
        if tool == "fs_write":
            return self.fs_write(
                str(payload["path"]),
                str(payload["content"]),
                approved=True,
            )
        if tool == "shell_run":
            return self.shell_run(
                str(payload["command"]),
                cwd=str(payload["cwd"]) if payload.get("cwd") else None,
                approved=True,
            )
        if tool == "git":
            args = [str(part) for part in payload.get("args", [])]
            return self._git(args, approved=True, destructive=True)
        raise ToolError(f"unknown pending tool: {tool}")
