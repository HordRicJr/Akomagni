"""Skill link / discovery outside BMAD trees."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.core.project import skill_search_roots
from akomagni.flow.intent import classify_message
from akomagni.flow.orchestrator import _is_greenfield, route_message
from akomagni.inference.llama import resolve_model_path
from akomagni.skills.discovery import discover_skills, find_skill
from akomagni.skills.link import (
    discover_skill_sources,
    ensure_skills_linked,
    extra_skill_roots,
    register_skill_root,
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
    monkeypatch.setattr("akomagni.skills.link.SKILLS_DIR", home / "skills")
    from akomagni.core.config import ensure_default_config

    ensure_default_config()
    return home


def _make_skill(root: Path, skill_id: str) -> Path:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: test\n---\n\n# {skill_id}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_register_skill_root_makes_skills_discoverable(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "skills-src"
    _make_skill(source, "bmad-brainstorming")
    register_skill_root(source)
    assert find_skill("bmad-brainstorming") is not None
    assert source.resolve() in skill_search_roots()
    register_skill_root(source)
    assert len(extra_skill_roots()) == 1


def test_register_skill_root_errors(akomagni_home, tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        register_skill_root(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="No skills"):
        register_skill_root(empty)


def test_extra_skill_roots_skips_missing(akomagni_home):
    roots = extra_skill_roots(
        {"skills": {"extra_roots": [str(akomagni_home / "nope"), str(akomagni_home)]}}
    )
    assert roots == [akomagni_home.resolve()]


def test_ensure_skills_linked_autodetects(akomagni_home, tmp_path, monkeypatch):
    money = tmp_path / "workspace"
    (money / "_bmad").mkdir(parents=True)
    skills = money / ".agent" / "skills"
    _make_skill(skills, "bmad-brainstorming")
    apps = money / "apps"
    apps.mkdir(parents=True)
    monkeypatch.chdir(apps)
    linked = ensure_skills_linked()
    assert linked
    assert "bmad-brainstorming" in discover_skills()


def test_ensure_returns_existing_config(akomagni_home, tmp_path):
    source = tmp_path / "bundle"
    _make_skill(source, "bmad-ux")
    register_skill_root(source)
    assert ensure_skills_linked() == [source.resolve()]


def test_ensure_returns_global_skills_dir(akomagni_home, monkeypatch):
    skills_dir = akomagni_home / "skills"
    _make_skill(skills_dir, "bmad-prd")
    monkeypatch.chdir(akomagni_home)
    assert ensure_skills_linked() == [skills_dir]


def test_discover_skill_sources_empty(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert discover_skill_sources(tmp_path) == []


def test_skill_link_cli(akomagni_home, tmp_path):
    source = tmp_path / "bundle"
    _make_skill(source, "bmad-build")
    result = runner.invoke(app, ["skill", "link", str(source)])
    assert result.exit_code == 0
    assert "Linked skills" in result.stdout
    assert "bmad-build" in discover_skills()


def test_skill_link_cli_autodetect(akomagni_home, tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    source = tmp_path / ".claude" / "skills"
    _make_skill(source, "bmad-architecture")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["skill", "link"])
    assert result.exit_code == 0
    assert "bmad-architecture" in discover_skills()


def test_skill_link_cli_none_found(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["skill", "link"])
    assert result.exit_code == 1
    assert "No BMAD skills found" in result.stdout


def test_skill_list_empty(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 1
    assert "skill link" in result.stdout.lower() or "BMAD" in result.stdout


def test_skill_list_and_path_cli(akomagni_home, tmp_path):
    source = tmp_path / "bundle"
    _make_skill(source, "bmad-brainstorming")
    register_skill_root(source)
    listed = runner.invoke(app, ["skill", "list", "-f", "brainstorm"])
    assert listed.exit_code == 0
    assert "bmad-brainstorming" in listed.stdout
    path = runner.invoke(app, ["skill", "path", "bmad-brainstorming"])
    assert path.exit_code == 0
    assert "bmad-brainstorming" in path.stdout
    missing = runner.invoke(app, ["skill", "path", "nope-skill"])
    assert missing.exit_code == 1


def test_discover_sources_with_explicit_start(akomagni_home, tmp_path):
    (tmp_path / "_bmad").mkdir()
    source = tmp_path / ".agents" / "skills"
    _make_skill(source, "bmad-help")
    nested = tmp_path / "nested"
    nested.mkdir()
    found = discover_skill_sources(nested)
    assert any(p.name == "skills" for p in found)


def test_resolve_model_path_flat_file(tmp_path):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"gguf")
    assert resolve_model_path("model.gguf", models_dir=tmp_path) == gguf
    assert resolve_model_path(None, models_dir=tmp_path) == gguf
    assert resolve_model_path("x", models_dir=tmp_path / "empty") is None


def test_english_build_app_routes_brainstorm(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".akomagni" / "workflow").mkdir(parents=True)
    decision = route_message("I want to build a budget app brainstorming")
    assert decision.skill == "bmad-brainstorming"
    assert decision.greenfield is True


def test_classify_brainstorming_word():
    decision = classify_message("lets do a brainstorming session")
    assert decision.skill == "bmad-brainstorming"


def test_is_greenfield_english():
    assert _is_greenfield("I want to build an app") is True


def test_resolve_model_path_catalog_dir(tmp_path):
    model_dir = tmp_path / "phi-3.5-mini"
    model_dir.mkdir()
    gguf = model_dir / "Phi-3.5-mini-instruct-Q4_K_M.gguf"
    gguf.write_bytes(b"gguf")
    assert resolve_model_path("phi-3.5-mini", models_dir=tmp_path) == gguf
    assert resolve_model_path(str(gguf), models_dir=tmp_path) == gguf
    assert resolve_model_path("missing", models_dir=tmp_path) == gguf
