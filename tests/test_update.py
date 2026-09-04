"""Tests for Akomagni self-update."""

from __future__ import annotations

import shutil

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
    (scripts / "akomagni.exe").write_text("new", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        if len(cmd) >= 4 and cmd[1] == "-C" and cmd[3] == "rev-parse":

            class Ref:
                returncode = 0
                stdout = "abc123\n" if len(calls) == 1 else "def456\n"
                stderr = ""

            return Ref()
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    existing = bin_dir / "akomagni.exe"
    existing.write_text("old", encoding="utf-8")

    result = run_update(install_dir=install, bin_dir=bin_dir)
    assert result.previous_ref == "abc123"
    assert result.current_ref == "def456"
    assert any("pull" in " ".join(c) for c in calls)
    assert any("pip" in " ".join(c) and "install" in " ".join(c) for c in calls)
    assert (bin_dir / "akomagni.exe").read_text(encoding="utf-8") == "new"
    assert not (bin_dir / "akomagni.exe.new").exists()


def test_install_cli_binary_windows_rename_locked(tmp_path, monkeypatch):
    from akomagni.core.update import _install_cli_binary

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    source = tmp_path / "akomagni.exe"
    source.write_text("v2", encoding="utf-8")
    dest = tmp_path / "bin" / "akomagni.exe"
    dest.parent.mkdir()
    dest.write_text("v1", encoding="utf-8")

    _install_cli_binary(source, dest)
    assert dest.read_text(encoding="utf-8") == "v2"


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


def test_default_install_dir_unix(monkeypatch):
    from akomagni.core.update import default_install_dir

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Linux")
    assert default_install_dir().as_posix().endswith(".local/share/akomagni")


def test_default_install_dir_windows_without_localappdata(monkeypatch):
    from akomagni.core.update import default_install_dir

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    path = default_install_dir()
    assert path.as_posix().endswith("AppData/Local/akomagni")


def test_find_install_root_from_scripts(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    fake = scripts / "python.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr("akomagni.core.update.sys.executable", str(fake))
    assert find_install_root() == install


def test_find_install_root_none(tmp_path, monkeypatch):
    monkeypatch.setattr("akomagni.core.update.sys.executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr("akomagni.core.update.default_install_dir", lambda: tmp_path / "missing")
    assert find_install_root() is None


def test_git_exe_missing(monkeypatch):
    from akomagni.core.update import _git_exe

    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: None)
    with pytest.raises(UpdateError, match="git is required"):
        _git_exe()


def test_git_ref_unknown(tmp_path, monkeypatch):
    from akomagni.core.update import _git_ref

    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: "git")

    def fake_run(_cmd, **_kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "fail"

        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    assert _git_ref(tmp_path) == "unknown"


def test_install_cli_binary_linux(tmp_path, monkeypatch):
    from akomagni.core.update import _install_cli_binary

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Linux")
    source = tmp_path / "akomagni"
    source.write_text("bin", encoding="utf-8")
    dest = tmp_path / "user-bin" / "akomagni"
    dest.parent.mkdir()
    dest.write_text("old", encoding="utf-8")
    _install_cli_binary(source, dest)
    assert dest.is_symlink()


def test_install_cli_binary_windows_fallback_copy(tmp_path, monkeypatch):
    from akomagni.core.update import _install_cli_binary

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    source = tmp_path / "akomagni.exe"
    source.write_text("v2", encoding="utf-8")
    dest = tmp_path / "bin" / "akomagni.exe"
    dest.parent.mkdir()
    dest.write_text("v1", encoding="utf-8")
    backup = dest.with_name("akomagni.exe.old")
    backup.write_text("stale", encoding="utf-8")

    def boom_replace(_src, _dst):
        raise OSError("locked")

    monkeypatch.setattr("akomagni.core.update.os.replace", boom_replace)
    _install_cli_binary(source, dest)
    assert dest.read_text(encoding="utf-8") == "v2"


def test_install_cli_binary_windows_locked_raises(tmp_path, monkeypatch):
    from akomagni.core.update import _install_cli_binary

    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    source = tmp_path / "akomagni.exe"
    source.write_text("v2", encoding="utf-8")
    dest = tmp_path / "bin" / "akomagni.exe"
    dest.parent.mkdir()
    dest.write_text("v1", encoding="utf-8")

    def boom_replace(_src, _dst):
        raise OSError("locked")

    calls = {"n": 0}
    real_copy2 = shutil.copy2

    def selective_copy2(src, dst, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_copy2(src, dst, *args, **kwargs)
        raise OSError("still locked")

    monkeypatch.setattr("akomagni.core.update.os.replace", boom_replace)
    monkeypatch.setattr("akomagni.core.update.shutil.copy2", selective_copy2)
    with pytest.raises(UpdateError, match="Cannot replace"):
        _install_cli_binary(source, dest)


def test_run_update_windows_shim_lock_is_soft(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    (scripts / "akomagni.exe").write_text("x", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "abc\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None)
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "akomagni.core.update._install_cli_binary",
        lambda *_a, **_k: (_ for _ in ()).throw(UpdateError("locked shim")),
    )
    result = run_update(install_dir=install, bin_dir=tmp_path / "bin")
    assert result.current_ref == "abc"


def test_run_update_oserror_on_binary_install(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    venv_bin = install / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("", encoding="utf-8")
    (venv_bin / "akomagni").write_text("x", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "abc\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "akomagni.core.update._install_cli_binary",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(UpdateError, match="Failed to install CLI binary"):
        run_update(install_dir=install, bin_dir=tmp_path / "bin")


def test_run_update_pip_upgrade_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    (scripts / "akomagni.exe").write_text("x", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        if "pip" in cmd and "-U" in cmd:
            Result.returncode = 1
            Result.stderr = "pip boom"
            return Result()
        if "rev-parse" in cmd:
            Result.stdout = "abc\n"
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    with pytest.raises(UpdateError, match="pip upgrade failed"):
        run_update(install_dir=install)


def test_run_update_deps_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")
    (scripts / "akomagni.exe").write_text("x", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        if (
            "pip" in cmd
            and "install" in cmd
            and "--upgrade" in cmd
            and "-e" not in cmd
            and "-U" not in cmd
        ):
            Result.returncode = 1
            Result.stderr = "deps fail"
            return Result()
        if "rev-parse" in cmd:
            Result.stdout = "abc\n"
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    with pytest.raises(UpdateError, match="dependency install failed"):
        run_update(install_dir=install)


def test_run_update_missing_root(monkeypatch):
    monkeypatch.setattr("akomagni.core.update.find_install_root", lambda: None)
    with pytest.raises(UpdateError, match="Cannot locate"):
        run_update()
