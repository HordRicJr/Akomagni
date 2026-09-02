"""Tests for Akomagni self-update."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.core.update import UpdateError, find_install_root, run_update

runner = CliRunner()


def test_find_install_root_from_venv_layout(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    venv_bin = install / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    fake_python = venv_bin / "python"
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr("akomagni.core.update.sys.executable", str(fake_python))
    assert find_install_root() == install


def test_run_update_git_pull_and_pip(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    (scripts / "akomagni.exe").write_text("", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        if cmd[:4] == ["git", "-C", str(install), "rev-parse"]:

            class Ref:
                returncode = 0
                stdout = "abc123\n" if len(calls) == 1 else "def456\n"
                stderr = ""

            return Ref()
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")

    result = run_update(install_dir=install, bin_dir=tmp_path / "bin")
    assert result.previous_ref == "abc123"
    assert result.current_ref == "def456"
    assert any("pull" in " ".join(c) for c in calls)
    assert any("pip" in " ".join(c) and "install" in " ".join(c) for c in calls)
    assert (tmp_path / "bin" / "akomagni.exe").is_file()


def test_run_update_requires_git(tmp_path):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    with pytest.raises(UpdateError, match="No git checkout"):
        run_update(install_dir=install)


def test_update_cli_success(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    from akomagni.core.update import UpdateResult

    monkeypatch.setattr(
        "akomagni.core.update.run_update",
        lambda **kwargs: UpdateResult(
            install_dir=install,
            bin_path=install / "bin" / "akomagni.exe",
            previous_ref="aaa",
            current_ref="bbb",
        ),
    )
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "updated" in result.stdout.lower() or "mis à jour" in result.stdout.lower()
