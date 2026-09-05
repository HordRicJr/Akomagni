"""Tests for multi-provider Rodium economic routing."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from akomagni.inference.rodium_router import (
    _model_cost_score,
    _parse_price,
    default_rodium_models_map,
    domain_tier,
    fetch_coding_catalogue,
    fetch_rodium_catalogue,
    pick_tier_model,
    resolve_rodium_model,
)


def test_domain_tiers_are_economical_by_default():
    assert domain_tier("text") == "economy"
    assert domain_tier("code") == "coding"
    assert domain_tier("design") == "balanced"
    assert domain_tier("image") == "image"


def test_complex_text_escalates_to_strong():
    assert domain_tier("text", message="Please write the full architecture PRD") == "strong"


def test_design_architecture_escalates_to_strong():
    assert domain_tier("design", message="system design and PRD for the product") == "strong"


def test_parse_price_and_cost_score_edges():
    assert _parse_price(None) is None
    assert _parse_price("nope") is None
    assert _parse_price("12.5") == 12.5
    assert _model_cost_score({"rodiumai_pricing": {}}) == 1e18
    assert _model_cost_score({"rodiumai_pricing": {"per_image": "2"}}) == 2000.0


def test_static_picks_are_multi_provider():
    text = pick_tier_model("economy")
    code = pick_tier_model("coding")
    design = pick_tier_model("balanced")
    image = pick_tier_model("image")
    assert text.startswith(("google/", "anthropic/", "deepseek/"))
    assert code == "rodiumai/smart"
    assert design.startswith(("anthropic/", "google/", "openai/"))
    assert image.startswith(("google/", "openai/"))


def test_resolve_remaps_legacy_basic_without_network():
    model = resolve_rodium_model(
        "text",
        config_models={"text": "rodium/basic"},
        use_live_catalogue=False,
    )
    assert model == "google/gemini-3.1-flash-lite-preview"


def test_resolve_keeps_explicit_catalogue_id():
    model = resolve_rodium_model(
        "design",
        config_models={"design": "anthropic/claude-sonnet-4-6"},
        use_live_catalogue=False,
    )
    assert model == "anthropic/claude-sonnet-4-6"


def test_live_catalogue_picks_cheapest_text():
    catalogue = [
        {
            "id": "openai/gpt-4o",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "1822", "output_per_1m": "7288"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
            "rodiumai_tier": {"quality": "high"},
        },
        {
            "id": "google/gemini-3.1-flash-lite-preview",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "182", "output_per_1m": "1093"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
            "rodiumai_tier": {"quality": "basic"},
        },
        {
            "id": "anthropic/claude-fable-5",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "7288", "output_per_1m": "36439"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
            "rodiumai_tier": {"quality": "max"},
        },
    ]
    assert pick_tier_model("economy", catalogue=catalogue) == "google/gemini-3.1-flash-lite-preview"
    assert pick_tier_model("strong", catalogue=catalogue) == "anthropic/claude-fable-5"


def test_pick_image_and_coding_from_catalogue():
    catalogue = [
        {
            "id": "openai/gpt-image-1",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"per_image": "50"},
            "rodiumai_capabilities": {"output_modalities": ["image"]},
        },
        {
            "id": "google/gemini-3.1-flash-image",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"per_image": "10"},
            "rodiumai_capabilities": {"output_modalities": ["image"]},
        },
        {
            "id": "rodiumai/smart",
            "rodiumai_status": "available",
            "rodiumai_pricing": {},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
        },
    ]
    assert pick_tier_model("image", catalogue=catalogue) == "google/gemini-3.1-flash-image"
    assert pick_tier_model("coding", catalogue=catalogue) == "rodiumai/smart"


def test_fetch_catalogue_uses_cache():
    import akomagni.inference.rodium_router as rr

    rr._catalogue_cache["models"] = None
    rr._catalogue_cache["ts"] = 0.0
    payload = {
        "data": [
            {
                "id": "google/gemini-3.1-flash-lite-preview",
                "rodiumai_status": "available",
                "rodiumai_pricing": {"input_per_1m": "1", "output_per_1m": "1"},
                "rodiumai_capabilities": {"output_modalities": ["text"]},
            }
        ]
    }
    with patch("akomagni.inference.rodium_router._fetch_json", return_value=payload):
        rows = fetch_rodium_catalogue(base_url="https://api.rodiumai.io/v1", api_key="rd_sk_x")
        assert rows[0]["id"].startswith("google/")
        with patch("akomagni.inference.rodium_router._fetch_json", side_effect=RuntimeError("no")):
            again = fetch_rodium_catalogue(base_url="https://api.rodiumai.io/v1", api_key="rd_sk_x")
            assert again[0]["id"].startswith("google/")


def test_fetch_coding_catalogue_and_resolve_live():
    coding = {
        "data": [
            {
                "id": "deepseek/deepseek-coder",
                "rodiumai_status": "available",
                "rodiumai_pricing": {"input_per_1m": "10", "output_per_1m": "10"},
                "rodiumai_capabilities": {"output_modalities": ["text"]},
            }
        ]
    }
    with patch("akomagni.inference.rodium_router._fetch_json", return_value=coding):
        rows = fetch_coding_catalogue(base_url="https://api.rodiumai.io/v1")
        assert rows[0]["id"] == "deepseek/deepseek-coder"
    with (
        patch("akomagni.inference.rodium_router.fetch_rodium_catalogue", return_value=[]),
        patch(
            "akomagni.inference.rodium_router.fetch_coding_catalogue",
            return_value=coding["data"],
        ),
    ):
        model = resolve_rodium_model(
            "code",
            base_url="https://api.rodiumai.io/v1",
            api_key="rd_sk_x",
            use_live_catalogue=True,
        )
        assert model == "rodiumai/smart"


def test_fetch_json_and_error_paths():
    import akomagni.inference.rodium_router as rr

    rr._catalogue_cache["models"] = [{"id": "cached/model"}]
    rr._catalogue_cache["ts"] = 0.0
    with patch(
        "akomagni.inference.rodium_router._fetch_json",
        side_effect=urllib.error.URLError("down"),
    ):
        assert fetch_rodium_catalogue(
            base_url="https://api.rodiumai.io/v1",
            api_key="rd_sk_x",
            force=True,
        ) == [{"id": "cached/model"}]
        assert fetch_coding_catalogue(base_url="https://api.rodiumai.io/v1") == []

    payload = json.dumps({"ok": True}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp):
        data = rr._fetch_json("https://api.rodiumai.io/v1/models", api_key="rd_sk_x")
        assert data == {"ok": True}


def test_coding_without_smart_picks_cheapest_coder():
    catalogue = [
        {
            "id": "openai/gpt-4o",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "100", "output_per_1m": "100"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
            "rodiumai_description": "general chat",
        }
    ]
    coding = [
        {
            "id": "deepseek/deepseek-coder",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "5", "output_per_1m": "5"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
        },
        {
            "id": "anthropic/claude-sonnet-4-6",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "50", "output_per_1m": "50"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
        },
    ]
    assert (
        pick_tier_model("coding", catalogue=catalogue, coding_catalogue=coding)
        == "deepseek/deepseek-coder"
    )


def test_economy_falls_back_to_global_cheapest():
    catalogue = [
        {
            "id": "vendor/cheap-chat",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": "1", "output_per_1m": "1"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
        },
        {
            "id": "vendor/image-only",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"per_image": "1"},
            "rodiumai_capabilities": {"output_modalities": ["image"]},
        },
    ]
    assert pick_tier_model("economy", catalogue=catalogue) == "vendor/cheap-chat"


def test_balanced_picks_mid_quality_pack():
    catalogue = [
        {
            "id": f"vendor/m{i}",
            "rodiumai_status": "available",
            "rodiumai_pricing": {"input_per_1m": str(i), "output_per_1m": "1"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
            "rodiumai_tier": {"quality": q},
        }
        for i, q in enumerate(("max", "high", "pro", "basic", "fast"), start=1)
    ]
    picked = pick_tier_model("balanced", catalogue=catalogue)
    assert picked.startswith("vendor/")


def test_legacy_rodium_slash_profile_remaps():
    model = resolve_rodium_model(
        "text",
        config_models={"text": "rodium/auto"},
        use_live_catalogue=False,
    )
    assert model.startswith(("google/", "anthropic/", "deepseek/"))


def test_default_rodium_models_map_keys():
    mapping = default_rodium_models_map()
    assert set(mapping) == {"text", "design", "code", "image"}
    assert mapping["code"] == "rodiumai/smart"


def test_image_empty_catalogue_uses_static():
    assert pick_tier_model("image", catalogue=[]).startswith("google/")


def test_pick_cheapest_none_when_unavailable():
    catalogue = [
        {
            "id": "vendor/down",
            "rodiumai_status": "offline",
            "rodiumai_pricing": {"input_per_1m": "1", "output_per_1m": "1"},
            "rodiumai_capabilities": {"output_modalities": ["text"]},
        }
    ]
    # No available text → static economy candidate
    assert pick_tier_model("economy", catalogue=catalogue).startswith(
        ("google/", "anthropic/", "deepseek/")
    )
