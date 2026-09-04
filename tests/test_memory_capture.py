"""Tests for memory auto-capture with approval."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.memory.capture import (
    CaptureError,
    approve_capture,
    build_capture_text,
    list_pending,
    maybe_prompt_capture,
    propose_capture,
    reject_capture,
)

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


def test_build_capture_text():
    text = build_capture_text("How do I test?", "Use pytest with fixtures.")
    assert "How do I test?" in text
    assert "Use pytest" in text


def test_build_capture_text_empty_raises():
    with pytest.raises(CaptureError, match="required"):
        build_capture_text("hello", "   ")


def test_propose_approve_reject_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = propose_capture(
        "Prefer JWT for API auth",
        "Store tokens in httpOnly cookies.",
    )
    pending = list_pending()
    assert len(pending) == 1
    assert pending[0].capture_id == proposal.capture_id

    saved = approve_capture(proposal.capture_id)
    assert saved.is_file()
    assert "JWT" in saved.read_text(encoding="utf-8")
    assert list_pending() == []


def test_reject_capture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = propose_capture("Question", "Answer")
    reject_capture(proposal.capture_id)
    assert list_pending() == []


def test_approve_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CaptureError, match="not found"):
        approve_capture("abcdef123456")


def test_maybe_prompt_capture_immediate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = maybe_prompt_capture("Q", "A", approved=True)
    assert saved.is_file()
    assert list_pending() == []


def test_maybe_prompt_capture_queue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = maybe_prompt_capture("Q", "A", approved=False)
    assert proposal.capture_id
    assert len(list_pending()) == 1


def test_global_pending(tmp_path, monkeypatch):
    memory = tmp_path / "central" / "memory"
    memory.mkdir(parents=True)
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", memory)
    monkeypatch.setattr("akomagni.memory.ops.MEMORY_DIR", memory)
    proposal = propose_capture("Global note", "Global answer", global_=True)
    assert len(list_pending(global_=True)) == 1
    saved = approve_capture(proposal.capture_id, global_=True)
    assert saved.is_relative_to(memory / "learnings")


def test_memory_pending_cli(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    propose_capture("CLI test question", "CLI test answer")
    result = runner.invoke(app, ["memory", "pending"])
    assert result.exit_code == 0
    assert "CLI test" in result.stdout


def test_memory_approve_cli(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = propose_capture("Approve me", "Saved content")
    result = runner.invoke(app, ["memory", "approve", proposal.capture_id])
    assert result.exit_code == 0
    assert "Approved" in result.stdout
    assert list_pending() == []


def test_memory_reject_cli(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = propose_capture("Reject me", "Discarded content")
    result = runner.invoke(app, ["memory", "reject", proposal.capture_id])
    assert result.exit_code == 0
    assert "Rejected" in result.stdout


def test_invalid_capture_id():
    with pytest.raises(CaptureError, match="invalid capture id"):
        approve_capture("bad id!")


def test_reject_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CaptureError, match="not found"):
        reject_capture("abcdef123456")


def test_approve_wraps_memory_error(tmp_path, monkeypatch):
    from akomagni.memory.ops import MemoryError as OpsMemoryError

    monkeypatch.chdir(tmp_path)
    proposal = propose_capture("Question", "Answer")

    def boom(*_args, **_kwargs):
        raise OpsMemoryError("disk full")

    monkeypatch.setattr("akomagni.memory.capture.add_memory", boom)
    with pytest.raises(CaptureError, match="disk full"):
        approve_capture(proposal.capture_id)


def test_memory_pending_empty_cli(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["memory", "pending"])
    assert result.exit_code == 0
    assert "No pending captures" in result.stdout


def test_memory_approve_error_cli(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["memory", "approve", "abcdef123456"])
    assert result.exit_code == 1
    assert "Error" in result.stdout


def test_run_cli_auto_capture_save(akomagni_home, tmp_path, monkeypatch):
    from akomagni.flow.intent import RouteDecision
    from akomagni.inference.client import InferenceStatus

    monkeypatch.chdir(tmp_path)
    cfg_path = akomagni_home / "config.yaml"
    cfg_path.write_text(
        "memory:\n  auto_capture: true\n  capture_global: false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "akomagni.cli.main.check_health_from_config",
        lambda *_args, **_kwargs: InferenceStatus(
            online=True,
            base_url="http://127.0.0.1:8787/v1",
            models=["local"],
        ),
    )
    monkeypatch.setattr(
        "akomagni.cli.main.try_chat_with_inference",
        lambda *_args, **_kwargs: "Use pytest fixtures for testing.",
    )
    decision = RouteDecision(
        agent_id="bmad-agent-dev",
        skill="bmad-dev-story",
        confidence=0.9,
        badge="🛠️ Dev",
        hint="Implement the story.",
    )
    monkeypatch.setattr("akomagni.cli.main.route_message", lambda *_a, **_k: decision)

    result = runner.invoke(
        app,
        ["run", "cli", "--no-setup", "--no-invoke", "--inference"],
        input="How do I test?\ny\n",
    )
    assert result.exit_code == 0
    assert "Saved to memory" in result.stdout


def test_pending_json_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proposal = propose_capture("Roundtrip", "Works")
    pending_dir = tmp_path / ".akomagni" / "memory" / "pending"
    payload = json.loads((pending_dir / f"{proposal.capture_id}.json").read_text(encoding="utf-8"))
    assert payload["capture_id"] == proposal.capture_id
    assert payload["global"] is False
