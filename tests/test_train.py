"""Tests for Akomagni Train (dataset export + bundle)."""

from __future__ import annotations

import json

import pytest
import yaml
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.train.lora import (
    TrainError,
    build_train_plan,
    export_jsonl,
    prepare_train_bundle,
)

runner = CliRunner()


def _seed_learnings(tmp_path) -> None:
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "note.md").write_text(
        "# Pytest rule\n\nAlways use pytest for Python tests.\n", encoding="utf-8"
    )


def test_build_train_plan_requires_learnings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TrainError, match="No memory learnings"):
        build_train_plan()


def test_build_train_plan_with_project_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="qwen2.5-coder-7b")
    assert plan.base_model == "qwen2.5-coder-7b"
    assert any("learnings" in s for s in plan.dataset_sources)


def test_export_jsonl_writes_chat_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan()
    dataset_path, count = export_jsonl(plan)
    assert count == 1
    assert dataset_path.is_file()
    row = json.loads(dataset_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["messages"][0]["role"] == "user"
    assert "Pytest rule" in row["messages"][0]["content"]
    assert "pytest" in row["messages"][1]["content"].lower()


def test_prepare_train_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan()
    bundle = prepare_train_bundle(plan)
    assert bundle.example_count == 1
    assert bundle.dataset_path.is_file()
    assert bundle.config_path.is_file()
    assert bundle.readme_path.is_file()
    config = yaml.safe_load(bundle.config_path.read_text(encoding="utf-8"))
    assert config["base_model"] == plan.base_model
    assert config["method"] == "qlora"


def test_train_plan_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "plan"])
    assert result.exit_code == 0
    assert "qwen2.5-coder-7b" in result.stdout
    assert "Examples" in result.stdout


def test_train_export_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "export"])
    assert result.exit_code == 0
    assert "Exported" in result.stdout


def test_train_bundle_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "bundle"])
    assert result.exit_code == 0
    assert "Train bundle ready" in result.stdout
    assert (tmp_path / ".akomagni" / "train" / "output" / "dataset.jsonl").is_file()


def test_train_run_exports_bundle(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "run"])
    assert result.exit_code == 1
    assert "bundle exported" in result.stdout.lower() or "Training bundle" in result.stdout
    assert (tmp_path / ".akomagni" / "train" / "output" / "train.yaml").is_file()


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
