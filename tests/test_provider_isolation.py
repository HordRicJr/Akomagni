"""Regression: local / Rodium / Foundry must not cross-leak models or docs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from akomagni.flow.intent import RouteDecision
from akomagni.flow.orchestrator import route_message
from akomagni.inference.chat import _azure_image_model_candidates, try_chat_with_inference
from akomagni.inference.client import InferenceClientError, InferenceStatus
from akomagni.inference.endpoint import (
    AZURE_DEFAULT_MODELS,
    InferenceEndpoint,
    cloud_model_for_domain,
    resolve_inference_endpoint,
)
from akomagni.inference.foundry import deployments_from_models
from akomagni.inference.provider_routing import (
    assert_model_fits_provider,
    image_hint_for_provider,
    is_rodium_catalogue_id,
    pick_fallback_model,
)
from akomagni.inference.providers import apply_provider_preset


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    return home


def test_catalogue_id_detection():
    assert is_rodium_catalogue_id("google/gemini-3-pro-image")
    assert is_rodium_catalogue_id("rodium/basic")
    assert not is_rodium_catalogue_id("gpt-4o")
    assert not is_rodium_catalogue_id("dall-e-3")


def test_pick_fallback_model_isolates_providers():
    mixed = ["gpt-4o", "google/gemini-2.5-flash"]
    assert pick_fallback_model("azure", mixed) == "gpt-4o"
    assert pick_fallback_model("rodium", mixed) == "google/gemini-2.5-flash"
    assert pick_fallback_model("local", mixed) == "gpt-4o"


def test_azure_rejects_catalogue_ids():
    assert assert_model_fits_provider("azure", "google/gemini-3-pro-image") is None
    assert assert_model_fits_provider("azure", "gpt-image-1") == "gpt-image-1"


def test_azure_defaults_include_image_deployment():
    assert "image" in AZURE_DEFAULT_MODELS
    assert not is_rodium_catalogue_id(AZURE_DEFAULT_MODELS["image"])


def test_deployments_from_models_maps_image():
    mapped = deployments_from_models(["gpt-4o", "gpt-4o-mini", "dall-e-3"])
    assert mapped is not None
    assert mapped["image"] == "dall-e-3"
    assert mapped["code"] == "gpt-4o"


def test_cloud_model_azure_never_returns_catalogue(akomagni_home):
    cfg = apply_provider_preset(
        {"version": 1},
        "azure",
        azure_base_url="https://res.openai.azure.com/openai/v1/",
    )
    # Poison config with a Rodium id — must be dropped.
    cfg["providers"]["azure"]["deployments"] = {
        "text": "gpt-4o-mini",
        "image": "google/gemini-3-pro-image",
    }
    assert cloud_model_for_domain("image", config=cfg) is None
    assert cloud_model_for_domain("text", config=cfg) == "gpt-4o-mini"


def test_resolve_endpoint_local_vs_rodium_vs_azure(akomagni_home, monkeypatch):
    local = apply_provider_preset({"version": 1}, "local")
    ep = resolve_inference_endpoint(local)
    assert ep.provider == "local"
    assert ep.is_local is True
    assert "127.0.0.1" in ep.base_url or "localhost" in ep.base_url

    monkeypatch.setenv("RODIUMAI_API_KEY", "rd_sk_test")
    rodium = apply_provider_preset({"version": 1}, "rodium")
    ep = resolve_inference_endpoint(rodium)
    assert ep.provider == "rodium"
    assert ep.is_local is False
    assert "rodiumai" in ep.base_url

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-key")
    azure = apply_provider_preset(
        {"version": 1},
        "azure",
        azure_base_url="https://res.openai.azure.com/openai/v1/",
    )
    azure["providers"]["azure"]["auth"] = "api_key"
    ep = resolve_inference_endpoint(azure)
    assert ep.provider == "azure"
    assert ep.is_local is False
    assert "openai.azure.com" in ep.base_url
    assert "rodium" not in ep.base_url


def test_azure_image_candidates_drop_catalogue_ids():
    cfg = {
        "providers": {
            "azure": {
                "deployments": {"image": "google/gemini-3-pro-image", "text": "gpt-4o-mini"},
            }
        }
    }
    status = InferenceStatus(
        online=True,
        base_url="https://x/openai/v1",
        models=["gpt-4o", "dall-e-3", "google/gemini-3.1-flash-image"],
        provider="azure",
    )
    rows = _azure_image_model_candidates(cfg, primary="google/foo", status=status)
    assert "dall-e-3" in rows
    assert all(not is_rodium_catalogue_id(r) for r in rows)


def test_foundry_image_never_calls_rodium_catalogue(akomagni_home):
    decision = RouteDecision(
        agent_id="bmad-agent-ux",
        skill="image-pipeline",
        confidence=0.9,
        badge="image",
        hint="image",
    )
    plan = SimpleNamespace(
        domain_plan=SimpleNamespace(
            classification=SimpleNamespace(domain=SimpleNamespace(value="image")),
            skip_inference=False,
            model_id=None,
            model_path=None,
            catalog_name=None,
        ),
        swap_plan=SimpleNamespace(needs_swap=False),
        model_id=None,
    )
    called_models: list[str] = []

    def fake_image_gen(message, **kwargs):
        called_models.append(kwargs["model"])
        raise InferenceClientError("DeploymentNotFound")

    with (
        patch(
            "akomagni.inference.chat.resolve_inference_endpoint",
            return_value=InferenceEndpoint(
                provider="azure",
                base_url="https://res.openai.azure.com/openai/v1",
                api_key="k",
                is_local=False,
            ),
        ),
        patch("akomagni.inference.chat.plan_inference_chat", return_value=plan),
        patch(
            "akomagni.inference.chat.check_health_from_config",
            return_value=InferenceStatus(
                online=True,
                base_url="https://res.openai.azure.com/openai/v1",
                models=["gpt-4o", "dall-e-3"],
                provider="azure",
            ),
        ),
        patch("akomagni.inference.client.image_generation", side_effect=fake_image_gen),
        patch(
            "akomagni.inference.rodium_router.image_model_candidates",
            side_effect=AssertionError("Rodium catalogue must not run on Foundry"),
        ),
    ):
        out = try_chat_with_inference("génère une affiche", decision)

    assert isinstance(out, str)
    assert "Foundry" in out or "foundry" in out.lower() or "deployment" in out.lower()
    assert "rodiumai.io" not in out
    assert all(not is_rodium_catalogue_id(m) for m in called_models)
    assert "dall-e-3" in called_models


def test_image_hints_are_provider_specific():
    assert "rodiumai.io" in image_hint_for_provider("rodium")
    assert "rodiumai.io" not in image_hint_for_provider("azure")
    assert "Foundry" in image_hint_for_provider("azure")
    assert "GGUF" in image_hint_for_provider("local")


def test_route_without_project_is_greenfield_brainstorm(akomagni_home):
    decision = route_message("aide-moi à créer une app budget")
    assert decision.skill == "bmad-brainstorming"
