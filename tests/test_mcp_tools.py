"""Tests for MCP agent tools and approval flow."""

from __future__ import annotations

import os
import subprocess
import sys
import types

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.mcp.approval import (
    ApprovalError,
    PendingRequest,
    list_pending,
    pop_request,
    queue_request,
    reject_request,
)
from akomagni.mcp.sandbox import SandboxError, resolve_path, resolve_workspace
from akomagni.mcp.server import build_server
from akomagni.mcp.tools import AgentTools, ToolError

runner = CliRunner()


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    return home


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def tools(workspace):
    return AgentTools(workspace)


def test_resolve_path_blocks_traversal(workspace):
    with pytest.raises(SandboxError, match="escapes"):
        resolve_path("../outside.txt", workspace)


def test_resolve_workspace_from_config(akomagni_home, tmp_path, monkeypatch):
    custom = tmp_path / "custom-workspace"
    custom.mkdir()
    monkeypatch.setattr(
        "akomagni.core.config.load_config",
        lambda: {"mcp": {"workspace": str(custom)}},
    )
    assert resolve_workspace() == custom.resolve()


def test_resolve_workspace_project_root(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    (project / "_bmad").mkdir(parents=True)
    monkeypatch.chdir(project)
    monkeypatch.setattr("akomagni.core.config.load_config", lambda: {"mcp": {}})
    assert resolve_workspace() == project.resolve()


def test_fs_read_write_list(workspace, tools):
    result = tools.fs_write("notes.txt", "hello")
    assert result.ok
    assert tools.fs_read("notes.txt").output == "hello"
    listed = tools.fs_list(".")
    assert "[file] notes.txt" in listed.output


def test_fs_read_missing_and_binary(workspace, tools):
    assert not tools.fs_read("missing.txt").ok
    (workspace / "blob.bin").write_bytes(b"\xff\xfe")
    assert not tools.fs_read("blob.bin").ok


def test_fs_read_sandbox_error(workspace, tools):
    assert not tools.fs_read("../../outside.txt").ok


def test_fs_write_sandbox_error(workspace, tools):
    assert not tools.fs_write("../../outside.txt", "x").ok


def test_fs_list_not_directory(workspace, tools):
    (workspace / "only.txt").write_text("x", encoding="utf-8")
    assert not tools.fs_list("only.txt").ok


def test_fs_write_overwrite_requires_approval(workspace, tools):
    (workspace / "keep.txt").write_text("old", encoding="utf-8")
    result = tools.fs_write("keep.txt", "new")
    assert not result.ok
    assert result.pending is not None
    assert list_pending(workspace=workspace)
    approved = tools.fs_write("keep.txt", "new", approved=True)
    assert approved.ok
    assert (workspace / "keep.txt").read_text(encoding="utf-8") == "new"


def test_fs_delete_requires_approval(workspace, tools):
    target = workspace / "remove.txt"
    target.write_text("x", encoding="utf-8")
    result = tools.fs_delete("remove.txt")
    assert not result.ok
    assert target.is_file()
    approved = tools.fs_delete("remove.txt", approved=True)
    assert approved.ok
    assert not target.exists()


def test_fs_delete_empty_directory(workspace, tools):
    (workspace / "empty").mkdir()
    result = tools.fs_delete("empty", approved=True)
    assert result.ok
    assert not (workspace / "empty").exists()


def test_git_missing_executable(workspace, tools, monkeypatch):
    def raise_not_found(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("akomagni.mcp.tools.subprocess.run", raise_not_found)
    assert "not found" in tools.git_status().output


def test_execute_pending_fs_write(workspace, tools):
    pending = PendingRequest(
        "w1",
        "fs_write",
        "overwrite notes.txt",
        {"path": "notes.txt", "content": "updated"},
        "",
    )
    (workspace / "notes.txt").write_text("old", encoding="utf-8")
    result = tools.execute_pending(pending)
    assert result.ok
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "updated"


def test_auto_approve_runs_destructive(workspace):
    tools = AgentTools(workspace, auto_approve=True)
    (workspace / "gone.txt").write_text("x", encoding="utf-8")
    result = tools.fs_delete("gone.txt")
    assert result.ok
    assert not (workspace / "gone.txt").exists()


def test_shell_run_safe_command(workspace, tools):
    result = tools.shell_run("echo hello")
    assert result.ok
    assert "hello" in result.output


def test_shell_run_empty_and_bad_cwd(workspace, tools):
    assert not tools.shell_run("   ").ok
    assert not tools.shell_run("echo hi", cwd="../outside").ok
    assert not tools.shell_run("echo hi", cwd="missing-dir").ok


def test_shell_run_failing_command(workspace, tools):
    command = "cmd /c exit 1" if sys.platform == "win32" else "false"
    result = tools.shell_run(command)
    assert not result.ok
    assert "exit 1" in result.output


def test_shell_run_destructive_requires_approval(workspace, tools):
    result = tools.shell_run("rm -rf build")
    assert not result.ok
    assert result.pending is not None
    assert "approve" in result.output


def test_git_status_in_repo(workspace, tools):
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    result = tools.git_status()
    assert result.ok


def test_git_diff_and_log(workspace, tools):
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    (workspace / "readme.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "readme.md"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=workspace,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@e",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@e",
        },
    )
    assert tools.git_diff().ok
    assert tools.git_log(limit=1).ok


def test_git_push_requires_approval(workspace, tools):
    result = tools.git_push()
    assert not result.ok
    assert result.pending is not None


def test_execute_pending_shell_and_git(workspace, tools):
    shell_pending = PendingRequest(
        "id1",
        "shell_run",
        "shell",
        {"command": "echo approved", "cwd": None},
        "",
    )
    assert tools.execute_pending(shell_pending).ok
    git_pending = PendingRequest("id2", "git", "git push", {"args": ["push"]}, "")
    assert not tools.execute_pending(git_pending).ok


def test_execute_pending_unknown_tool(workspace, tools):
    pending = PendingRequest("id3", "unknown", "?", {}, "")
    with pytest.raises(ToolError, match="unknown"):
        tools.execute_pending(pending)


def test_queue_approve_reject_flow(workspace):
    pending = queue_request(
        "fs_delete",
        "delete temp.txt",
        {"path": "temp.txt"},
        workspace=workspace,
    )
    items = list_pending(workspace=workspace)
    assert len(items) == 1
    loaded = pop_request(pending.request_id, workspace=workspace)
    assert loaded.tool == "fs_delete"


def test_reject_request(workspace):
    pending = queue_request("git", "git push", {"args": ["push"]}, workspace=workspace)
    reject_request(pending.request_id, workspace=workspace)
    assert list_pending(workspace=workspace) == []


def test_pop_missing_raises(workspace):
    with pytest.raises(ApprovalError, match="not found"):
        pop_request("abcdef123456", workspace=workspace)


def test_mcp_pending_cli(workspace):
    queue_request("shell_run", "rm -rf tmp", {"command": "rm -rf tmp"}, workspace=workspace)
    result = runner.invoke(app, ["mcp", "pending", "--workspace", str(workspace)])
    assert result.exit_code == 0
    assert "shell_run" in result.stdout


def test_mcp_pending_empty_cli(workspace):
    result = runner.invoke(app, ["mcp", "pending", "--workspace", str(workspace)])
    assert result.exit_code == 0
    assert "No pending" in result.stdout


def test_mcp_approve_cli(workspace):
    (workspace / "gone.txt").write_text("x", encoding="utf-8")
    pending = queue_request(
        "fs_delete",
        "delete gone.txt",
        {"path": "gone.txt"},
        workspace=workspace,
    )
    result = runner.invoke(
        app,
        ["mcp", "approve", pending.request_id, "--workspace", str(workspace)],
    )
    assert result.exit_code == 0
    assert not (workspace / "gone.txt").exists()


def test_mcp_reject_cli(workspace):
    pending = queue_request(
        "fs_delete",
        "delete x",
        {"path": "x"},
        workspace=workspace,
    )
    result = runner.invoke(
        app,
        ["mcp", "reject", pending.request_id, "--workspace", str(workspace)],
    )
    assert result.exit_code == 0
    assert list_pending(workspace=workspace) == []


def test_mcp_serve_missing_dependency(akomagni_home, monkeypatch):
    monkeypatch.setattr(
        "akomagni.cli.main.run_stdio_server",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("pip install 'akomagni[agent]'")),
    )
    result = runner.invoke(app, ["mcp", "serve"])
    assert result.exit_code == 1
    assert "pip install" in result.stdout


def test_build_server_requires_mcp(workspace, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(RuntimeError, match="agent"):
        build_server(workspace)


def test_build_server_registers_tools(workspace, monkeypatch):
    captured: dict[str, object] = {}

    class FakeMCP:
        def __init__(self, name: str):
            self.name = name
            self.tools: list[str] = []

        def tool(self):
            def decorator(fn):
                self.tools.append(fn.__name__)
                captured[fn.__name__] = fn
                return fn

            return decorator

        def run(self) -> None:
            return None

    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FakeMCP
    server_mod = types.ModuleType("mcp.server")
    server_mod.fastmcp = fastmcp_mod
    mcp_mod = types.ModuleType("mcp")
    mcp_mod.server = server_mod
    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)

    server = build_server(workspace)
    assert "fs_read" in server.tools
    assert "git_push" in server.tools
    (workspace / "sample.txt").write_text("hello", encoding="utf-8")
    assert captured["fs_read"]("sample.txt") == "hello"
    assert "Approval required" in captured["fs_delete"]("sample.txt")
    assert "Approval required" in captured["shell_run"]("rm -rf build")
    assert "Approval required" in captured["git_push"]()
