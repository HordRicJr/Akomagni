"""Tests for Foundry Entra bootstrap (azure-identity + az login)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.inference.connect import ConnectError, connect_provider
from akomagni.inference.foundry import resolve_azure_auth_mode
from akomagni.inference.foundry_bootstrap import (
    EntraSetupResult,
    _pip_install_azure_identity,
    az_account_logged_in,
    azure_identity_available,
    ensure_foundry_entra,
    find_az_cli,
    install_azure_identity_background,
    run_az_login,
    verify_entra_token,
)


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


def test_default_auth_mode_is_entra_without_key(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_AUTH", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_INFERENCE_CREDENTIAL", raising=False)
    assert resolve_azure_auth_mode({}) == "entra"


def test_auth_mode_api_key_when_key_present(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_AUTH", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret")
    assert resolve_azure_auth_mode({}) == "api_key"


def test_azure_identity_available_true_false():
    with patch(
        "akomagni.inference.foundry_bootstrap.importlib.import_module",
        side_effect=ImportError("no"),
    ):
        assert azure_identity_available() is False
    with patch(
        "akomagni.inference.foundry_bootstrap.importlib.import_module", return_value=object()
    ):
        assert azure_identity_available() is True


def test_find_az_cli(monkeypatch):
    monkeypatch.setattr(
        "akomagni.inference.foundry_bootstrap.shutil.which",
        lambda name: "C:/az.cmd" if name == "az" else None,
    )
    assert find_az_cli() == "C:/az.cmd"


def test_pip_install_azure_identity_success():
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with (
        patch("akomagni.inference.foundry_bootstrap.subprocess.run", return_value=completed),
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=True),
    ):
        ok, detail = _pip_install_azure_identity(timeout=5)
    assert ok is True
    assert "ready" in detail


def test_pip_install_azure_identity_failure():
    completed = SimpleNamespace(returncode=1, stdout="", stderr="boom")
    with patch("akomagni.inference.foundry_bootstrap.subprocess.run", return_value=completed):
        ok, detail = _pip_install_azure_identity(timeout=5)
    assert ok is False
    assert "boom" in detail


def test_pip_install_timeout():
    with patch(
        "akomagni.inference.foundry_bootstrap.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=1),
    ):
        ok, detail = _pip_install_azure_identity(timeout=1)
    assert ok is False
    assert "timed out" in detail


def test_install_azure_identity_background():
    with patch(
        "akomagni.inference.foundry_bootstrap._pip_install_azure_identity",
        return_value=(True, "azure-identity ready"),
    ):
        msgs: list[str] = []
        ok, _detail = install_azure_identity_background(on_progress=msgs.append, timeout=5)
    assert ok is True
    assert msgs


def test_az_account_logged_in_true_false():
    with patch(
        "akomagni.inference.foundry_bootstrap.subprocess.run",
        return_value=SimpleNamespace(returncode=0),
    ):
        assert az_account_logged_in(az_bin="az") is True
    with patch(
        "akomagni.inference.foundry_bootstrap.subprocess.run",
        return_value=SimpleNamespace(returncode=1),
    ):
        assert az_account_logged_in(az_bin="az") is False
    with patch(
        "akomagni.inference.foundry_bootstrap.subprocess.run",
        side_effect=OSError("no"),
    ):
        assert az_account_logged_in(az_bin="az") is False


def test_run_az_login_missing_cli():
    with patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value=None):
        ok, detail = run_az_login()
    assert ok is False
    assert "not found" in detail.lower()


def test_run_az_login_success():
    with (
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch(
            "akomagni.inference.foundry_bootstrap.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=True),
    ):
        ok, detail = run_az_login(on_progress=lambda _m: None)
    assert ok is True
    assert "ready" in detail.lower()


def test_verify_entra_token_ok_and_fail():
    with patch(
        "akomagni.inference.foundry_bootstrap.get_foundry_entra_token",
        return_value="tok",
    ):
        ok, detail = verify_entra_token()
    assert ok is True
    with patch(
        "akomagni.inference.foundry_bootstrap.get_foundry_entra_token",
        side_effect=RuntimeError("no token"),
    ):
        ok, detail = verify_entra_token()
    assert ok is False
    assert "no token" in detail


def test_ensure_foundry_entra_happy_path():
    with (
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=True),
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=True),
        patch("akomagni.inference.foundry_bootstrap.verify_entra_token", return_value=(True, "ok")),
    ):
        result = ensure_foundry_entra(login_if_needed=True)
    assert result.ok
    assert result.identity_installed
    assert result.az_logged_in
    assert result.token_ok


def test_ensure_foundry_entra_installs_identity_then_logs_in():
    with (
        patch(
            "akomagni.inference.foundry_bootstrap.azure_identity_available",
            side_effect=[False, True, True],
        ),
        patch(
            "akomagni.inference.foundry_bootstrap.install_azure_identity_background",
            return_value=(True, "azure-identity ready"),
        ) as install,
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=False),
        patch(
            "akomagni.inference.foundry_bootstrap.run_az_login",
            return_value=(True, "Azure CLI session ready"),
        ) as login,
        patch(
            "akomagni.inference.foundry_bootstrap.verify_entra_token", return_value=(True, "tok")
        ),
    ):
        result = ensure_foundry_entra(login_if_needed=True)
    assert result.ok
    install.assert_called_once()
    login.assert_called_once()


def test_ensure_foundry_entra_install_fails():
    with (
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=False),
        patch(
            "akomagni.inference.foundry_bootstrap.install_azure_identity_background",
            return_value=(False, "pip boom"),
        ),
    ):
        result = ensure_foundry_entra(login_if_needed=False)
    assert result.ok is False
    assert "azure-identity" in (result.error or "")


def test_ensure_foundry_entra_no_az_cli_still_tries_token():
    with (
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=True),
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value=None),
        patch("akomagni.inference.foundry_bootstrap.verify_entra_token", return_value=(True, "ok")),
    ):
        result = ensure_foundry_entra(login_if_needed=True)
    assert result.ok is True
    assert result.az_available is False


def test_ensure_foundry_entra_login_skipped():
    with (
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=True),
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=False),
        patch(
            "akomagni.inference.foundry_bootstrap.verify_entra_token", return_value=(False, "no")
        ),
    ):
        result = ensure_foundry_entra(login_if_needed=False)
    assert result.token_ok is False
    assert result.error


def test_connect_foundry_entra_runs_bootstrap(akomagni_home, monkeypatch):
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    status = SimpleNamespace(online=True, models=["gpt-4o"], error=None)
    monkeypatch.setattr(
        "akomagni.inference.connect.check_health_from_config",
        lambda _cfg: status,
    )
    setup = EntraSetupResult(
        identity_installed=True,
        az_available=True,
        az_logged_in=True,
        token_ok=True,
        messages=["azure-identity ready", "Entra token acquired"],
    )
    with patch(
        "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
        return_value=setup,
    ) as mocked:
        result = connect_provider(
            "foundry",
            base_url="https://my.openai.azure.com",
            auth="entra",
            sync_ide=False,
        )
    mocked.assert_called_once()
    assert result.online is True
    assert result.api_key_saved is False


def test_connect_foundry_entra_failure_raises(akomagni_home, monkeypatch):
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    setup = EntraSetupResult(
        identity_installed=False,
        token_ok=False,
        error="Could not install azure-identity: boom",
        messages=["boom"],
    )
    with (
        patch(
            "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
            return_value=setup,
        ),
        pytest.raises(ConnectError, match="azure-identity"),
    ):
        connect_provider(
            "foundry",
            base_url="https://my.openai.azure.com",
            auth="entra",
            sync_ide=False,
        )


def test_resolve_azure_endpoint_entra_path(monkeypatch):
    from akomagni.inference.endpoint import resolve_inference_endpoint

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    cfg = {
        "version": 1,
        "inference": {"provider": "azure"},
        "providers": {
            "azure": {
                "base_url": "https://my.openai.azure.com/openai/v1",
                "auth": "entra",
            }
        },
    }
    with patch(
        "akomagni.inference.endpoint.get_foundry_entra_token",
        return_value="entra-tok",
    ):
        endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.auth_mode == "entra"
    assert endpoint.api_key == "entra-tok"


def test_resolve_azure_endpoint_entra_bootstrap_retry(monkeypatch):
    from akomagni.inference.endpoint import resolve_inference_endpoint

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    cfg = {
        "version": 1,
        "inference": {"provider": "azure"},
        "providers": {
            "azure": {
                "base_url": "https://my.openai.azure.com/openai/v1",
                "auth": "entra",
            }
        },
    }
    setup = EntraSetupResult(token_ok=True, identity_installed=True, messages=[])
    with (
        patch(
            "akomagni.inference.endpoint.get_foundry_entra_token",
            side_effect=[RuntimeError("missing"), "tok2"],
        ),
        patch(
            "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
            return_value=setup,
        ),
    ):
        endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.api_key == "tok2"


def test_pip_install_not_importable_after_ok_exit():
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with (
        patch("akomagni.inference.foundry_bootstrap.subprocess.run", return_value=completed),
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=False),
    ):
        ok, detail = _pip_install_azure_identity(timeout=5)
    assert ok is False
    assert "not importable" in detail


def test_run_az_login_nonzero_exit():
    with (
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch(
            "akomagni.inference.foundry_bootstrap.subprocess.run",
            return_value=SimpleNamespace(returncode=2),
        ),
    ):
        ok, detail = run_az_login()
    assert ok is False
    assert "2" in detail


def test_run_az_login_timeout():
    with (
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch(
            "akomagni.inference.foundry_bootstrap.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="az", timeout=1),
        ),
    ):
        ok, detail = run_az_login(timeout=1)
    assert ok is False
    assert "timed out" in detail


def test_ensure_foundry_entra_login_warns_then_token_ok():
    with (
        patch("akomagni.inference.foundry_bootstrap.azure_identity_available", return_value=True),
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=False),
        patch(
            "akomagni.inference.foundry_bootstrap.run_az_login",
            return_value=(False, "cancelled"),
        ),
        patch("akomagni.inference.foundry_bootstrap.verify_entra_token", return_value=(True, "ok")),
    ):
        result = ensure_foundry_entra(login_if_needed=True)
    assert result.ok is True
    assert result.az_logged_in is False


def test_extras_foundry_cli(akomagni_home):
    runner = CliRunner()
    setup = EntraSetupResult(
        identity_installed=True,
        az_available=True,
        az_logged_in=True,
        token_ok=True,
        messages=["ready"],
    )
    with patch(
        "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
        return_value=setup,
    ):
        result = runner.invoke(app, ["extras", "foundry"])
    assert result.exit_code == 0
    assert "Entra" in result.stdout or "Foundry" in result.stdout


def test_az_account_logged_in_no_binary():
    with patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value=None):
        assert az_account_logged_in() is False


def test_verify_entra_token_empty_string():
    with patch(
        "akomagni.inference.foundry_bootstrap.get_foundry_entra_token",
        return_value="",
    ):
        ok, detail = verify_entra_token()
    assert ok is False
    assert "empty" in detail.lower()


def test_pip_install_oserror():
    with patch(
        "akomagni.inference.foundry_bootstrap.subprocess.run",
        side_effect=OSError("pip missing"),
    ):
        ok, detail = _pip_install_azure_identity(timeout=5)
    assert ok is False
    assert "pip" in detail.lower()


def test_run_az_login_oserror():
    with (
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch(
            "akomagni.inference.foundry_bootstrap.subprocess.run",
            side_effect=OSError("az broken"),
        ),
    ):
        ok, _detail = run_az_login()
    assert ok is False


def test_run_az_login_finished_but_not_logged_in():
    with (
        patch("akomagni.inference.foundry_bootstrap.find_az_cli", return_value="az"),
        patch(
            "akomagni.inference.foundry_bootstrap.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ),
        patch("akomagni.inference.foundry_bootstrap.az_account_logged_in", return_value=False),
    ):
        ok, detail = run_az_login()
    assert ok is False
    assert "no account" in detail.lower()


def test_extras_foundry_cli_failure(akomagni_home):
    runner = CliRunner()
    setup = EntraSetupResult(token_ok=False, error="no az", messages=[])
    with patch(
        "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
        return_value=setup,
    ):
        result = runner.invoke(app, ["config", "extras", "foundry"])
    assert result.exit_code != 0


def test_config_provider_azure_entra_bootstrap(akomagni_home):
    runner = CliRunner()
    runner.invoke(app, ["config", "init"])
    setup = EntraSetupResult(
        identity_installed=True,
        token_ok=True,
        az_logged_in=True,
        messages=["ok"],
    )
    with patch(
        "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
        return_value=setup,
    ):
        result = runner.invoke(
            app,
            [
                "config",
                "provider",
                "azure",
                "--base-url",
                "https://my.openai.azure.com",
            ],
        )
    assert result.exit_code == 0
    assert "azure" in result.stdout.lower() or "Entra" in result.stdout


def test_resolve_azure_api_key_mode_and_status(monkeypatch):
    from akomagni.inference.endpoint import (
        cloud_model_for_domain,
        provider_status,
        resolve_inference_endpoint,
    )

    monkeypatch.delenv("AZURE_OPENAI_AUTH", raising=False)
    cfg = {
        "version": 1,
        "inference": {"provider": "azure", "default_model": "gpt-4o"},
        "providers": {
            "azure": {
                "base_url": "https://my.openai.azure.com/openai/v1",
                "api_key": "secret-key",
                "auth": "api_key",
                "deployments": {"code": "gpt-4o", "design": "gpt-4o", "text": "gpt-4o-mini"},
            }
        },
    }
    endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.provider == "azure"
    assert endpoint.api_key == "secret-key"
    assert endpoint.auth_mode == "api_key"
    assert cloud_model_for_domain("code", config=cfg) == "gpt-4o"
    assert cloud_model_for_domain("text", config=cfg) == "gpt-4o-mini"
    status = provider_status(cfg)
    assert status["auth_mode"] == "api_key"
    assert status["api_key_set"] is True


def test_resolve_azure_entra_returns_none_when_bootstrap_fails(monkeypatch):
    from akomagni.inference.endpoint import resolve_inference_endpoint

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    cfg = {
        "version": 1,
        "inference": {"provider": "azure"},
        "providers": {
            "azure": {
                "base_url": "https://my.openai.azure.com/openai/v1",
                "auth": "entra",
            }
        },
    }
    setup = EntraSetupResult(token_ok=False, error="fail", messages=[])
    with (
        patch(
            "akomagni.inference.endpoint.get_foundry_entra_token",
            side_effect=RuntimeError("no"),
        ),
        patch(
            "akomagni.inference.foundry_bootstrap.ensure_foundry_entra",
            return_value=setup,
        ),
    ):
        endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.auth_mode == "entra"
    assert endpoint.api_key is None


def test_resolve_azure_endpoint_from_env_only(monkeypatch):
    from akomagni.inference.endpoint import resolve_inference_endpoint

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("AZURE_OPENAI_AUTH", "api_key")
    cfg = {
        "version": 1,
        "inference": {"provider": "azure"},
        "providers": {"azure": {}},
    }
    endpoint = resolve_inference_endpoint(cfg)
    assert endpoint.base_url.endswith("/openai/v1")
    assert endpoint.api_key == "env-key"


def test_check_health_azure_offline_hint():
    from akomagni.inference.client import InferenceClientError, check_health

    with patch(
        "akomagni.inference.client._request_json",
        side_effect=InferenceClientError("down"),
    ):
        status = check_health(
            base_url="https://my.openai.azure.com/openai/v1",
            api_key="k",
            provider="azure",
            auth_mode="api_key",
        )
    assert status.online is False
    assert "Foundry" in (status.error or "")
