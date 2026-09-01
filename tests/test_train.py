"""Tests for Akomagni Train scaffold."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.train.lora import TrainError, build_train_plan

runner = CliRunner()


def test_build_train_plan_requires_learnings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TrainError, match="No memory learnings"):
        build_train_plan()


def test_build_train_plan_with_project_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "note.md").write_text("Always use pytest", encoding="utf-8")
    plan = build_train_plan(base_model="qwen2.5-coder-7b")
    assert plan.base_model == "qwen2.5-coder-7b"
    assert any("learnings" in s for s in plan.dataset_sources)


def test_train_plan_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "note.md").write_text("rule", encoding="utf-8")
    result = runner.invoke(app, ["train", "plan"])
    assert result.exit_code == 0
    assert "qwen2.5-coder-7b" in result.stdout


def test_train_run_stub_exits(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "note.md").write_text("rule", encoding="utf-8")
    result = runner.invoke(app, ["train", "run"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.stdout.lower() or "LoRA" in result.stdout


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
