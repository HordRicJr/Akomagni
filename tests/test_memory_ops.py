"""Tests for memory add and promote."""

from __future__ import annotations

import pytest

from akomagni.memory.ops import MemoryError, add_memory, promote_project_memory


def test_add_memory_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = add_memory("Always use JWT for auth", title="Auth convention")
    assert path.is_file()
    assert path.parent.name == "learnings"
    assert "JWT" in path.read_text(encoding="utf-8")
    assert path.is_relative_to(tmp_path / ".akomagni" / "memory")


def test_add_memory_global(tmp_path, monkeypatch):
    memory = tmp_path / "central" / "memory"
    memory.mkdir(parents=True)
    monkeypatch.setattr("akomagni.memory.ops.MEMORY_DIR", memory)
    path = add_memory("Prefer pytest over unittest", global_=True)
    assert path.is_relative_to(memory / "learnings")


def test_add_memory_empty_raises():
    with pytest.raises(MemoryError, match="empty"):
        add_memory("   ")


def test_promote_project_memory(tmp_path, monkeypatch):
    memory = tmp_path / "central" / "memory"
    memory.mkdir(parents=True)
    monkeypatch.setattr("akomagni.memory.ops.MEMORY_DIR", memory)
    monkeypatch.chdir(tmp_path)

    proj = tmp_path / ".akomagni" / "memory"
    proj.mkdir(parents=True)
    (proj / "decisions.md").write_text("# Decisions\n\nUse FastAPI\n", encoding="utf-8")

    result = promote_project_memory()
    assert result.files_copied == 1
    assert result.destination.is_dir()
    assert (result.destination / "decisions.md").is_file()
    assert "FastAPI" in (result.destination / "decisions.md").read_text(encoding="utf-8")


def test_promote_project_memory_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(MemoryError, match="no project memory"):
        promote_project_memory()
