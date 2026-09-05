"""Prefer shipped kernel skills over later linked trees."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.project import skill_search_roots
from akomagni.skills.discovery import SkillInfo, discover_skills
from akomagni.skills.invoke import build_skill_cli_guidance


def _skill(root: Path, skill_id: str, marker: str) -> Path:
    skill = root / skill_id
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: {marker}\n---\n# {marker}\n",
        encoding="utf-8",
    )
    return skill


def test_discover_prefers_first_root(tmp_path, monkeypatch):
    kernel_skills = tmp_path / "kernel" / ".agents" / "skills"
    money_skills = tmp_path / "money" / ".claude" / "skills"
    _skill(kernel_skills, "bmad-brainstorming", "from-kernel")
    _skill(money_skills, "bmad-brainstorming", "from-money")

    monkeypatch.setattr(
        "akomagni.skills.discovery.skill_search_roots",
        lambda _project_root=None: [kernel_skills, money_skills],
    )
    monkeypatch.setattr("akomagni.skills.discovery.find_project_root", lambda: None)
    found = discover_skills()
    assert found["bmad-brainstorming"].description == "from-kernel"
    assert "kernel" in str(found["bmad-brainstorming"].path)


def test_build_skill_cli_guidance_reads_skill_md(tmp_path):
    skill_dir = _skill(tmp_path, "bmad-brainstorming", "brainstorm-me")
    info = SkillInfo(
        skill_id="bmad-brainstorming",
        name="bmad-brainstorming",
        description="x",
        path=skill_dir,
    )
    text = build_skill_cli_guidance(info)
    assert "brainstorm-me" in text
    assert "bmad-brainstorming" in text


def test_skill_search_roots_lists_kernel_before_extras(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    kernel = install / "bmad-core"
    (kernel / "_bmad").mkdir(parents=True)
    skills = kernel / ".agents" / "skills"
    _skill(skills, "bmad-brainstorming", "kernel")
    extra = tmp_path / "extra"
    _skill(extra, "bmad-brainstorming", "extra")

    home = tmp_path / "data"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    monkeypatch.setattr("akomagni.core.bmad_kernel.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.update.find_install_root", lambda: install)
    monkeypatch.setattr("akomagni.core.update.default_install_dir", lambda: install)
    monkeypatch.setattr(
        "akomagni.skills.link.extra_skill_roots",
        lambda config=None: [extra],
    )
    monkeypatch.chdir(tmp_path)

    roots = skill_search_roots()
    assert roots[0] == skills.resolve()
    assert extra.resolve() in roots
    assert roots.index(skills.resolve()) < roots.index(extra.resolve())
