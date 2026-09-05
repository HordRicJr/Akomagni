"""Tests for the shipped BMAD kernel."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.bmad_kernel import (
    changelog_highlights,
    ensure_bmad_kernel,
    find_shipped_bmad_core,
    read_package_version,
)
from akomagni.core.project import skill_search_roots


def _make_kernel(root: Path, *, skills: int = 2) -> Path:
    (root / "_bmad" / "scripts").mkdir(parents=True)
    (root / "_bmad" / "scripts" / "render_skill.py").write_text("# stub\n", encoding="utf-8")
    skills_dir = root / ".agents" / "skills"
    skills_dir.mkdir(parents=True)
    for i in range(skills):
        skill = skills_dir / f"bmad-demo-{i}"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            f"---\nname: bmad-demo-{i}\ndescription: demo\n---\n",
            encoding="utf-8",
        )
    return root


def test_find_shipped_bmad_core_from_install(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    kernel = _make_kernel(install / "bmad-core")
    monkeypatch.setattr(
        "akomagni.core.update.find_install_root",
        lambda: install,
    )
    monkeypatch.setattr(
        "akomagni.core.update.default_install_dir",
        lambda: install,
    )
    monkeypatch.setattr("akomagni.core.bmad_kernel.DATA_DIR", tmp_path / "data")
    assert find_shipped_bmad_core() == kernel.resolve()


def test_ensure_bmad_kernel_persists_config(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    _make_kernel(install / "bmad-core", skills=3)
    home = tmp_path / "data"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.bmad_kernel.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    monkeypatch.setattr("akomagni.core.update.find_install_root", lambda: install)
    monkeypatch.setattr("akomagni.core.update.default_install_dir", lambda: install)

    info = ensure_bmad_kernel(persist=True)
    assert info is not None
    assert info.skill_count == 3
    from akomagni.core.config import load_config

    cfg = load_config()
    assert Path(cfg["skills"]["bmad_project_root"]).resolve() == (install / "bmad-core").resolve()
    roots = skill_search_roots()
    assert any(r.name == "skills" and "bmad-core" in str(r) for r in roots)


def test_changelog_highlights(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [0.3.0] - 2026-09-05\n\n"
        "### Added\n\n- **BMAD kernel**: shipped\n- Other feature\n\n"
        "## [0.1.0] - 2026-08-29\n\n- Old\n",
        encoding="utf-8",
    )
    items = changelog_highlights(tmp_path, max_items=5)
    assert any("BMAD kernel" in i for i in items)
    assert len(items) <= 5


def test_read_package_version(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "akomagni"\nversion = "0.3.0"\n',
        encoding="utf-8",
    )
    assert read_package_version(tmp_path) == "0.3.0"


def test_ensure_skips_persist(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    _make_kernel(install / "bmad-core", skills=1)
    monkeypatch.setattr("akomagni.core.update.find_install_root", lambda: install)
    monkeypatch.setattr("akomagni.core.update.default_install_dir", lambda: install)
    monkeypatch.setattr("akomagni.core.bmad_kernel.DATA_DIR", tmp_path / "data")
    info = ensure_bmad_kernel(persist=False)
    assert info is not None
    assert info.skill_count == 1


def test_ensure_none_without_kernel(tmp_path, monkeypatch):
    monkeypatch.setattr("akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: None)
    assert ensure_bmad_kernel() is None


def test_changelog_missing_file(tmp_path):
    assert changelog_highlights(tmp_path) == []


def test_read_package_version_fallback(monkeypatch):
    from akomagni import __version__

    assert read_package_version(None) == __version__


def test_resolve_uses_kernel(tmp_path, monkeypatch):
    from akomagni.core.project import resolve_bmad_project_root

    kernel = _make_kernel(tmp_path / "bmad-core")
    monkeypatch.setattr("akomagni.core.project.find_project_root", lambda start=None: None)
    monkeypatch.setattr("akomagni.core.project.configured_bmad_root", lambda: None)
    monkeypatch.setattr("akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: kernel)
    monkeypatch.chdir(tmp_path)
    assert resolve_bmad_project_root() == kernel.resolve()


def test_count_skills_empty_root(tmp_path):
    from akomagni.core.bmad_kernel import count_kernel_skills

    (tmp_path / "_bmad").mkdir()
    assert count_kernel_skills(tmp_path) == 0


def test_skill_search_roots_skips_missing_kernel(tmp_path, monkeypatch):
    home = tmp_path / "data"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    monkeypatch.setattr("akomagni.core.bmad_kernel.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: None)
    monkeypatch.setattr("akomagni.core.bmad_kernel.ensure_bmad_kernel", lambda **_: None)
    monkeypatch.setattr("akomagni.skills.link.extra_skill_roots", lambda config=None: [])
    monkeypatch.chdir(tmp_path)
    assert skill_search_roots() == []


def test_run_update_reports_version_and_kernel(tmp_path, monkeypatch):
    from akomagni.core.update import run_update

    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text(
        '[project]\nname="akomagni"\nversion="0.3.0"\n',
        encoding="utf-8",
    )
    (install / "CHANGELOG.md").write_text(
        "## [0.3.0]\n\n- **BMAD kernel**: auto\n",
        encoding="utf-8",
    )
    (install / ".git").mkdir()
    _make_kernel(install / "bmad-core", skills=2)
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    (scripts / "akomagni.exe").write_text("new", encoding="utf-8")

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

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "abc123\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")

    result = run_update(install_dir=install, bin_dir=tmp_path / "bin")
    assert result.current_version == "0.3.0"
    assert result.bmad_skill_count == 2
    assert any("BMAD" in h for h in result.highlights)
