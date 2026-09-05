"""Tests for Rodium interactive model picker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from akomagni.flow.intent import classify_message
from akomagni.inference.chat import try_chat_with_inference
from akomagni.inference.client import InferenceClientError, InferenceStatus
from akomagni.inference.model_picker import (
    AUTO_VALUE,
    apply_model_choice,
    build_model_choices,
    describe_model_selection,
    resolve_session_cloud_model,
)


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    import akomagni.core.config as config_mod

    home = tmp_path / "akomagni"
    home.mkdir()
    monkeypatch.setattr(config_mod, "DATA_DIR", home)
    monkeypatch.setattr(config_mod, "CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr(config_mod, "MEMORY_DIR", home / "memory")
    monkeypatch.setattr(config_mod, "MODELS_DIR", home / "models")
    config_mod.ensure_default_config()
    return home


def test_build_choices_starts_with_auto():
    rows = build_model_choices(catalogue=[])
    assert rows[0][0] == AUTO_VALUE
    assert any(v.startswith("anthropic/") for v, _ in rows)


def test_build_choices_filters_embeddings():
    catalogue = [
        {"id": "openai/gpt-5.4", "rodiumai_status": "available", "name": "GPT-5.4"},
        {
            "id": "openai/text-embedding-3-large",
            "rodiumai_status": "available",
            "name": "Embed",
        },
        {
            "id": "google/gemini-3.1-flash-image",
            "rodiumai_status": "available",
            "name": "Flash Image",
        },
    ]
    rows = build_model_choices(catalogue=catalogue)
    ids = [v for v, _ in rows]
    assert "openai/gpt-5.4" in ids
    assert "google/gemini-3.1-flash-image" in ids
    assert "openai/text-embedding-3-large" not in ids


def test_apply_and_resolve_pinned(akomagni_home):
    cfg = apply_model_choice("anthropic/claude-sonnet-4-6")
    assert describe_model_selection(cfg).startswith("Pinned")
    model = resolve_session_cloud_model(
        "code",
        message="implement auth",
        config=cfg,
        base_url=None,
        api_key=None,
    )
    assert model == "anthropic/claude-sonnet-4-6"


def test_pinned_text_still_routes_image(akomagni_home):
    cfg = apply_model_choice("anthropic/claude-sonnet-4-6")
    model = resolve_session_cloud_model(
        "image",
        message="affiche publicitaire",
        config=cfg,
        base_url=None,
        api_key=None,
    )
    assert "image" in model or model.startswith(("google/", "openai/gpt-image"))


def test_auto_mode_uses_router(akomagni_home):
    cfg = apply_model_choice("auto")
    assert "Auto" in describe_model_selection(cfg)
    model = resolve_session_cloud_model(
        "text",
        message="hello",
        config=cfg,
        base_url=None,
        api_key=None,
    )
    assert "/" in model


def test_interactive_pick_numbered_fallback(akomagni_home):
    from akomagni.inference.model_picker import interactive_pick_model

    answers = iter(["2"])
    chosen = interactive_pick_model(
        choices=[
            ("auto", "Auto"),
            ("anthropic/claude-sonnet-4-6", "Sonnet"),
        ],
        prompt=lambda _msg: next(answers),
    )
    assert chosen == "anthropic/claude-sonnet-4-6"


def test_interactive_pick_empty_and_invalid(akomagni_home):
    from akomagni.inference.model_picker import interactive_pick_model

    chosen = interactive_pick_model(
        choices=[("auto", "Auto"), ("anthropic/claude-sonnet-4-6", "Sonnet")],
        prompt=lambda _msg: "",
    )
    assert chosen == "auto"

    chosen2 = interactive_pick_model(
        choices=[("auto", "Auto"), ("anthropic/claude-sonnet-4-6", "Sonnet")],
        prompt=lambda _msg: "999",
    )
    assert chosen2 == "auto"


def test_image_artifact_summary_pending():
    from akomagni.inference.client import ImageArtifact

    art = ImageArtifact(model="m", b64_json="aa")
    assert "awaiting" in art.summary().lower() or "Image generated" in art.summary()


def test_save_image_url_download_failure(tmp_path):
    import urllib.error

    from akomagni.inference.client import ImageArtifact, InferenceClientError, save_image_artifact

    art = ImageArtifact(model="m", url="https://cdn.example/x.png")
    with (
        patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
        pytest.raises(InferenceClientError, match="download"),
    ):
        save_image_artifact(art, tmp_path / "x.png")


def test_try_chat_cloud_image_all_models_fail():
    from akomagni.core.router.domain import DomainClassification, ModelDomain
    from akomagni.core.router.swap import DomainModelPlan, ModelSwapPlan
    from akomagni.inference.chat import InferenceChatPlan
    from akomagni.inference.endpoint import InferenceEndpoint

    decision = classify_message("génère une affiche")
    plan = InferenceChatPlan(
        domain_plan=DomainModelPlan(
            classification=DomainClassification(ModelDomain.IMAGE, 0.9, "image"),
            catalog_name="google/gemini-3-pro-image",
            model_path=None,
            model_id="google/gemini-3-pro-image",
            skip_inference=False,
            reason="cloud image",
        ),
        swap_plan=ModelSwapPlan(
            needs_swap=False, current_model=None, target_model=None, target_path=None
        ),
        model_id="google/gemini-3-pro-image",
    )
    with (
        patch(
            "akomagni.inference.chat.resolve_inference_endpoint",
            return_value=InferenceEndpoint(
                provider="rodium",
                base_url="https://api.rodiumai.io/v1",
                api_key="rd_sk_x",
                is_local=False,
            ),
        ),
        patch("akomagni.inference.chat.plan_inference_chat", return_value=plan),
        patch(
            "akomagni.inference.chat.check_health_from_config",
            return_value=InferenceStatus(
                online=True,
                base_url="https://api.rodiumai.io/v1",
                models=["google/gemini-3-pro-image"],
                provider="rodium",
            ),
        ),
        patch(
            "akomagni.inference.client.image_generation",
            side_effect=InferenceClientError("denied"),
        ),
        patch(
            "akomagni.inference.rodium_router.image_model_candidates",
            return_value=["google/gemini-3-pro-image"],
        ),
    ):
        out = try_chat_with_inference("génère une affiche", decision)
    assert isinstance(out, str)
    assert "failed" in out.lower()


def test_pinned_image_model_kept_for_image(akomagni_home):
    cfg = apply_model_choice("google/gemini-3-pro-image")
    model = resolve_session_cloud_model(
        "image",
        message="poster",
        config=cfg,
        base_url=None,
        api_key=None,
    )
    assert model == "google/gemini-3-pro-image"


def test_fetch_choices_for_config_offline(akomagni_home, monkeypatch):
    from akomagni.core.config import load_config
    from akomagni.inference import model_picker as mp

    monkeypatch.setattr(mp, "fetch_rodium_catalogue", lambda **_k: (_ for _ in ()).throw(OSError()))
    rows = mp.fetch_choices_for_config(load_config())
    assert rows[0][0] == "auto"


def test_build_skips_unavailable_and_caps():
    catalogue = [
        {"id": "vendor/down", "rodiumai_status": "offline", "name": "Down"},
        {"id": "vendor/ok", "rodiumai_status": "active", "name": "OK"},
    ]
    rows = build_model_choices(catalogue=catalogue)
    ids = [v for v, _ in rows]
    assert "vendor/down" not in ids
    assert "vendor/ok" in ids


def test_fetch_choices_uses_env_key(akomagni_home, monkeypatch):
    from akomagni.core.config import load_config
    from akomagni.inference import model_picker as mp
    from akomagni.inference.connect import save_config as sc

    cfg = load_config()
    cfg["providers"] = {
        "rodium": {"base_url": "https://api.rodiumai.io/v1", "api_key_env": "RODIUMAI_API_KEY"}
    }
    sc(cfg)
    monkeypatch.setenv("RODIUMAI_API_KEY", "rd_sk_env")
    monkeypatch.setattr(
        mp,
        "fetch_rodium_catalogue",
        lambda **kwargs: (
            [{"id": "openai/gpt-5.4", "rodiumai_status": "available", "name": "GPT"}]
            if kwargs.get("api_key") == "rd_sk_env"
            else []
        ),
    )
    rows = mp.fetch_choices_for_config(load_config())
    assert any(v == "openai/gpt-5.4" for v, _ in rows)


def test_save_image_mkdir_destination(tmp_path):
    from akomagni.inference.client import ImageArtifact, save_image_artifact

    art = ImageArtifact(model="m", b64_json="aaaa")
    out = save_image_artifact(art, tmp_path / "exports")
    assert out.exists()
    assert out.parent.name == "exports"


def test_save_image_b64_decode_error(tmp_path):
    from akomagni.inference.client import ImageArtifact, InferenceClientError, save_image_artifact

    art = ImageArtifact(model="m", b64_json="")
    with pytest.raises(InferenceClientError, match="decode|empty"):
        save_image_artifact(art, tmp_path / "bad.png")


def test_save_image_strips_data_url_and_writes(tmp_path):
    import base64

    from akomagni.inference.client import ImageArtifact, save_image_artifact

    raw = base64.b64encode(b"\x89PNG-demo").decode()
    art = ImageArtifact(model="m", b64_json=f"data:image/png;base64,{raw}")
    out = save_image_artifact(art, tmp_path / "poster.png")
    assert out.read_bytes() == b"\x89PNG-demo"


def test_write_bytes_chunked_large(tmp_path):
    from akomagni.inference.client import _write_bytes_chunked

    dest = tmp_path / "big.bin"
    payload = b"x" * (9 * 1024 * 1024)
    _write_bytes_chunked(dest, payload, chunk_size=1024 * 1024)
    assert dest.stat().st_size == len(payload)
