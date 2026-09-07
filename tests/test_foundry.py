"""Tests for Microsoft Foundry URL / auth helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from akomagni.inference.foundry import (
    FoundryUrlError,
    deployments_from_models,
    foundry_auth_headers,
    normalize_foundry_base_url,
    project_endpoint_note,
    resolve_azure_api_key,
    resolve_azure_auth_mode,
    resolve_azure_endpoint_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://my.openai.azure.com",
            "https://my.openai.azure.com/openai/v1",
        ),
        (
            "https://my.openai.azure.com/openai",
            "https://my.openai.azure.com/openai/v1",
        ),
        (
            "https://my.openai.azure.com/openai/v1/",
            "https://my.openai.azure.com/openai/v1",
        ),
        (
            "https://my.services.ai.azure.com",
            "https://my.services.ai.azure.com/openai/v1",
        ),
        (
            "https://my.services.ai.azure.com/openai/v1",
            "https://my.services.ai.azure.com/openai/v1",
        ),
        (
            "https://my.services.ai.azure.com/api/projects/demo",
            "https://my.services.ai.azure.com/api/projects/demo/openai/v1",
        ),
        (
            "https://my.openai.azure.com/openai/v1/chat/completions",
            "https://my.openai.azure.com/openai/v1",
        ),
    ],
)
def test_normalize_foundry_base_url(raw, expected):
    assert normalize_foundry_base_url(raw) == expected


def test_normalize_rejects_unknown_host():
    with pytest.raises(FoundryUrlError, match="Unrecognized"):
        normalize_foundry_base_url("https://example.com/v1")


def test_foundry_auth_headers_api_key_dual():
    headers = foundry_auth_headers("secret", auth_mode="api_key")
    assert headers["Authorization"] == "Bearer secret"
    assert headers["api-key"] == "secret"


def test_foundry_auth_headers_entra_bearer_only():
    headers = foundry_auth_headers("tok", auth_mode="entra")
    assert headers == {"Authorization": "Bearer tok"}


def test_deployments_from_models_prefers_gpt4o():
    mapped = deployments_from_models(["other", "gpt-4o-mini", "gpt-4o"])
    assert mapped is not None
    assert mapped["code"] == "gpt-4o"
    assert mapped["text"] == "gpt-4o-mini"


def test_resolve_azure_endpoint_from_env(monkeypatch):
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://env.openai.azure.com",
    )
    assert resolve_azure_endpoint_url({}) == "https://env.openai.azure.com/openai/v1"


def test_resolve_azure_api_key_inference_credential(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_INFERENCE_CREDENTIAL", "inf-key")
    assert resolve_azure_api_key({}) == "inf-key"


def test_resolve_azure_auth_mode_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_AUTH", "entra")
    assert resolve_azure_auth_mode({}) == "entra"


def test_project_endpoint_note():
    note = project_endpoint_note(
        "https://x.services.ai.azure.com/api/projects/p/openai/v1"
    )
    assert note is not None
    assert "project" in note.lower()


def test_normalize_adds_https_and_rejects_empty():
    assert (
        normalize_foundry_base_url("my.openai.azure.com")
        == "https://my.openai.azure.com/openai/v1"
    )
    with pytest.raises(FoundryUrlError, match="required"):
        normalize_foundry_base_url("  ")


def test_foundry_auth_headers_empty():
    assert foundry_auth_headers(None) == {}
    assert foundry_auth_headers("  ") == {}


def test_deployments_from_models_empty():
    assert deployments_from_models(None) is None
    assert deployments_from_models([]) is None


def test_resolve_azure_auth_mode_explicit_api_key(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_AUTH", "api_key")
    assert resolve_azure_auth_mode({}) == "api_key"


def test_get_foundry_entra_token_missing_package():
    from akomagni.inference.foundry import get_foundry_entra_token

    with patch.dict("sys.modules", {"azure.identity": None}):
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name.startswith("azure.identity") or name == "azure.identity":
                raise ImportError("no azure")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            with pytest.raises(RuntimeError, match="azure-identity"):
                get_foundry_entra_token()


def test_normalize_project_with_openai_segment():
    assert (
        normalize_foundry_base_url(
            "https://my.services.ai.azure.com/api/projects/demo/openai"
        )
        == "https://my.services.ai.azure.com/api/projects/demo/openai/v1"
    )


def test_normalize_rejects_bad_scheme_and_host():
    with pytest.raises(FoundryUrlError, match="https"):
        normalize_foundry_base_url("ftp://my.openai.azure.com")
    with pytest.raises(FoundryUrlError, match="host"):
        normalize_foundry_base_url("https://")


def test_normalize_collapses_double_openai_v1():
    assert (
        normalize_foundry_base_url(
            "https://my.openai.azure.com/openai/v1/openai/v1"
        )
        == "https://my.openai.azure.com/openai/v1"
    )


def test_get_foundry_entra_token_empty():
    from types import SimpleNamespace

    from akomagni.inference.foundry import get_foundry_entra_token

    fake = MagicMock()
    fake.DefaultAzureCredential.return_value.get_token.return_value = SimpleNamespace(token="")
    with patch.dict("sys.modules", {"azure.identity": fake}):
        with pytest.raises(RuntimeError, match="empty"):
            get_foundry_entra_token()


def test_project_endpoint_note_none_for_resource():
    assert project_endpoint_note("https://x.openai.azure.com/openai/v1") is None


def test_client_azure_auth_headers_dual():
    from akomagni.inference.client import _auth_headers

    headers = _auth_headers("k", provider="azure", auth_mode="api_key")
    assert headers["api-key"] == "k"
    assert headers["Authorization"] == "Bearer k"
    assert _auth_headers("k", provider="rodium") == {"Authorization": "Bearer k"}
