"""Extra coverage for connect, endpoint, update, and CLI paths (PR #78)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.core.update import (
    UpdateError,
    default_bin_dir,
    default_install_dir,
    find_install_root,
    run_update,
)
from akomagni.inference.connect import (
    ConnectError,
    connect_provider,
    sync_vscode_settings,
)
from akomagni.inference.endpoint import (
    cloud_model_for_domain,
    provider_status,
    resolve_inference_endpoint,
)
from akomagni.inference.providers import apply_provider_preset

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


def test_connect_provider_local(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = connect_provider("local", sync_ide=False)
    assert result.provider == "local"
    assert result.api_key_saved is False


def test_connect_provider_requires_api_key(akomagni_home):
    runner.invoke(app, ["config", "init"])
    with pytest.raises(ConnectError, match="API key"):
        connect_provider("rodium", base_url="https://api.rodiumai.io/v1", api_key="")


def test_connect_azure_normalizes_openai_url(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    status = SimpleNamespace(online=True, models=["gpt-4o"], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    result = connect_provider(
        "azure",
        base_url="https://myresource.openai.azure.com/openai",
        api_key="azure-key",
        workspace=tmp_path,
    )
    assert result.base_url.endswith("/openai/v1")
    assert result.api_key_saved is True


def test_connect_azure_appends_v1_suffix(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    status = SimpleNamespace(online=False, models=[], error="offline")
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    result = connect_provider(
        "foundry",
        base_url="https://myresource.openai.azure.com",
        api_key="azure-key",
        workspace=tmp_path,
    )
    assert "/openai/v1" in result.base_url


def test_connect_azure_requires_url(akomagni_home):
    runner.invoke(app, ["config", "init"])
    with pytest.raises(ConnectError, match="Foundry URL"):
        connect_provider("azure", api_key="key")


def test_sync_vscode_settings_invalid_json(tmp_path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    settings = vscode / "settings.json"
    settings.write_text("{not-json", encoding="utf-8")
    path = sync_vscode_settings(
        tmp_path,
        provider="rodium",
        base_url="https://api.rodiumai.io/v1",
        api_key="rd_sk_test",
        model="openai/gpt-4o",
    )
    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["akomagni.provider"] == "rodium"


def test_sync_vscode_settings_non_dict_payload(tmp_path):
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    settings = vscode / "settings.json"
    settings.write_text('["array"]', encoding="utf-8")
    path = sync_vscode_settings(
        tmp_path,
        provider="local",
        base_url="http://127.0.0.1:8787/v1",
        api_key=None,
    )
    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["akomagni.provider"] == "local"


def test_sync_vscode_settings_missing_workspace(tmp_path):
    missing = tmp_path / "missing"
    assert (
        sync_vscode_settings(missing, provider="local", base_url="http://x", api_key=None) is None
    )


def test_resolve_azure_endpoint_inline_key():
    cfg = apply_provider_preset(
        {"version": 1},
        "azure",
        azure_base_url="https://res.openai.azure.com/openai/v1/",
    )
    cfg["providers"]["azure"]["api_key"] = "inline-key"
    endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.provider == "azure"
    assert endpoint.api_key == "inline-key"


def test_cloud_model_for_domain_azure_defaults():
    cfg = apply_provider_preset(
        {"version": 1},
        "azure",
        azure_base_url="https://res.openai.azure.com/openai/v1/",
    )
    model = cloud_model_for_domain("design", config=cfg)
    assert model == "gpt-4o"


def test_cloud_model_for_domain_local_returns_none():
    cfg = apply_provider_preset({"version": 1}, "local")
    assert cloud_model_for_domain("code", config=cfg) is None


def test_provider_status_summary():
    cfg = apply_provider_preset({"version": 1}, "rodium")
    status = provider_status(cfg)
    assert status["provider"] == "rodium"
    assert status["is_local"] is False


def test_apply_provider_preset_azure_with_base_url():
    cfg = apply_provider_preset(
        {"version": 1},
        "azure",
        azure_base_url="https://res.openai.azure.com/openai/v1/",
    )
    assert cfg["providers"]["azure"]["base_url"].endswith("/v1")


def test_connect_cli_local(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["connect", "local"])
    assert result.exit_code == 0
    assert "local" in result.stdout.lower()


def test_connect_cli_azure_with_url(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.chdir(tmp_path)
    status = SimpleNamespace(online=True, models=[], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    with patch("typer.prompt", return_value="azure-key"):
        result = runner.invoke(
            app,
            [
                "connect",
                "foundry",
                "https://res.openai.azure.com/openai/v1/",
            ],
        )
    assert result.exit_code == 0
    assert "Connected" in result.stdout or "Saved credentials" in result.stdout


def test_connect_cli_offline_warning(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.chdir(tmp_path)
    status = SimpleNamespace(online=False, models=[], error="timeout")
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    with patch("typer.prompt", side_effect=["https://api.rodiumai.io/v1", "rd_sk_test"]):
        result = runner.invoke(app, ["connect", "rodium"])
    assert result.exit_code == 0
    assert "Saved credentials" in result.stdout


def test_flow_route_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["flow", "route", "implement login", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "agent_id" in payload
    assert "skill" in payload


def test_config_provider_azure(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(
        app,
        [
            "config",
            "provider",
            "azure",
            "--base-url",
            "https://res.openai.azure.com/openai/v1/",
        ],
    )
    assert result.exit_code == 0
    show = runner.invoke(app, ["config", "show"])
    assert "azure" in show.stdout


def test_ide_open_launches_vscode(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    fake_code = tmp_path / "code.cmd"
    fake_code.write_text("", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("shutil.which", lambda name: str(fake_code) if name == "code" else None)
    monkeypatch.setattr("subprocess.run", fake_run)
    result = runner.invoke(app, ["ide", "open"])
    assert result.exit_code == 0
    assert any(str(root) in " ".join(map(str, c)) for c in calls)


def test_ide_open_missing_vscode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    result = runner.invoke(app, ["ide", "open"])
    assert result.exit_code != 0


def test_ide_setup_unknown_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ide", "setup", "--provider", "nope"])
    assert result.exit_code != 0


def test_default_install_dir_windows(monkeypatch):
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\me\\AppData\\Local")
    assert default_install_dir().as_posix().endswith("akomagni")


def test_default_bin_dir():
    path = default_bin_dir()
    assert path.name == "bin"


def test_find_install_root_default_dir(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    monkeypatch.setattr("akomagni.core.update.default_install_dir", lambda: install)
    monkeypatch.setattr(
        "akomagni.core.update.sys.executable",
        str(tmp_path / "other" / "python.exe"),
    )
    assert find_install_root() == install


def test_run_update_git_missing(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: None if name == "git" else name
    )
    with pytest.raises(UpdateError, match="git is required"):
        run_update(install_dir=install)


def test_run_update_git_pull_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: "/usr/bin/git")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "fetch failed"

        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    with pytest.raises(UpdateError, match="git fetch failed"):
        run_update(install_dir=install)


def test_run_update_checkout_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: "git")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "abc\n"
            stderr = ""

        if "fetch" in cmd:
            return Result()
        if "checkout" in cmd:
            Result.returncode = 1
            Result.stderr = "checkout failed"
            return Result()
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    with pytest.raises(UpdateError, match="git checkout"):
        run_update(install_dir=install)


def test_run_update_reset_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: "git")

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "abc\n"
            stderr = ""

        if "reset" in cmd:
            Result.returncode = 1
            Result.stderr = "reset failed"
            return Result()
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    with pytest.raises(UpdateError, match="git reset failed"):
        run_update(install_dir=install)


def test_run_update_linux_symlink(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    bin_dir = install / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_text("", encoding="utf-8")
    (bin_dir / "akomagni").write_text("", encoding="utf-8")
    dest_bin = tmp_path / "user-bin"
    dest_bin.mkdir()
    existing = dest_bin / "akomagni"
    existing.write_text("old", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = "abc\n"
            stderr = ""

        if "rev-parse" in cmd:
            Result.stdout = "abc\n" if len(calls) == 1 else "def\n"
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr("akomagni.core.update.shutil.which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Linux")

    result = run_update(install_dir=install, bin_dir=dest_bin)
    assert result.current_ref == "def"
    assert (dest_bin / "akomagni").is_symlink()


def test_connect_cli_empty_api_key(akomagni_home, monkeypatch):
    runner.invoke(app, ["config", "init"])
    with patch("typer.prompt", side_effect=["https://api.rodiumai.io/v1", "   "]):
        result = runner.invoke(app, ["connect", "rodium"])
    assert result.exit_code != 0


def test_connect_cli_no_sync(akomagni_home, tmp_path, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.chdir(tmp_path)
    status = SimpleNamespace(online=True, models=[], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    with patch("typer.prompt", side_effect=["https://api.rodiumai.io/v1", "rd_sk_test"]):
        result = runner.invoke(app, ["connect", "rodium", "--no-sync"])
    assert result.exit_code == 0
    assert not (tmp_path / ".vscode" / "settings.json").exists()


def test_extras_alias_success(monkeypatch):
    class Result:
        returncode = 0

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())
    result = runner.invoke(app, ["extras", "dev"])
    assert result.exit_code == 0


def test_run_update_pip_install_failure(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")

    call_count = {"n": 0}

    def fake_run(cmd, **kwargs):
        call_count["n"] += 1

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        if "pip" in cmd and "install" in cmd and "-e" in cmd:
            Result.returncode = 1
            Result.stderr = "pip failed"
            return Result()
        if "rev-parse" in cmd:
            Result.stdout = "abc\n"
        return Result()

    monkeypatch.setattr("akomagni.core.update.subprocess.run", fake_run)
    monkeypatch.setattr(
        "akomagni.core.update.shutil.which", lambda name: "git" if name == "git" else None
    )
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    with pytest.raises(UpdateError, match="pip install failed"):
        run_update(install_dir=install)


def test_connect_cli_unknown_provider(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["connect", "unknown-provider"])
    assert result.exit_code != 0


def test_config_provider_unknown(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "provider", "invalid"])
    assert result.exit_code != 0


def test_connect_cli_connect_error(akomagni_home, monkeypatch):
    runner.invoke(app, ["config", "init"])
    monkeypatch.setattr(
        "akomagni.inference.connect.connect_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectError("boom")),
    )
    with patch("typer.prompt", side_effect=["https://api.rodiumai.io/v1", "rd_sk_test"]):
        result = runner.invoke(app, ["connect", "rodium"])
    assert result.exit_code != 0
    assert "boom" in result.stdout


def test_run_update_missing_binary_after_pip(tmp_path, monkeypatch):
    install = tmp_path / "akomagni"
    install.mkdir()
    (install / "pyproject.toml").write_text("[project]\nname='akomagni'\n", encoding="utf-8")
    (install / ".git").mkdir()
    scripts = install / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")

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
    monkeypatch.setattr("akomagni.core.update.platform.system", lambda: "Windows")
    with pytest.raises(UpdateError, match="Missing CLI binary"):
        run_update(install_dir=install)
