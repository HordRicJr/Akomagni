"""CI and engineering config smoke tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_files_exist():
    workflows = ROOT / ".github" / "workflows"
    names = {path.name for path in workflows.glob("*.yml")}
    assert names == {"quality.yml", "test.yml", "security.yml", "pages.yml"}


def test_dependabot_config_exists():
    path = ROOT / ".github" / "dependabot.yml"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in text
    assert "package-ecosystem: github-actions" in text


def test_branch_protection_scripts_exist():
    assert (ROOT / "scripts" / "apply-branch-protection.sh").is_file()
    assert (ROOT / "scripts" / "apply-branch-protection.ps1").is_file()


def test_enable_github_pages_scripts_exist():
    assert (ROOT / "scripts" / "enable-github-pages.sh").is_file()
    assert (ROOT / "scripts" / "enable-github-pages.ps1").is_file()
