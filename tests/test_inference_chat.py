"""Tests for inference chat wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from akomagni.flow.intent import classify_message
from akomagni.inference.chat import build_flow_system_prompt, try_chat_with_inference
from akomagni.inference.client import InferenceClientError, InferenceStatus


def test_build_flow_system_prompt():
    decision = classify_message("implement login API")
    prompt = build_flow_system_prompt(decision)
    assert decision.agent_id in prompt
    assert decision.skill in prompt


def test_try_chat_with_inference_offline():
    decision = classify_message("hello")
    local_endpoint = type(
        "E",
        (),
        {
            "is_local": True,
            "base_url": "http://127.0.0.1:8787/v1",
            "api_key": None,
            "provider": "local",
        },
    )()
    with (
        patch("akomagni.inference.chat.resolve_inference_endpoint", return_value=local_endpoint),
        patch(
            "akomagni.inference.chat.check_health",
            return_value=InferenceStatus(online=False, base_url="http://127.0.0.1:8787/v1"),
        ),
    ):
        assert try_chat_with_inference("hello", decision) is None


def test_try_chat_with_inference_online(tmp_path, monkeypatch):
    decision = classify_message("implement login API")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr("akomagni.inference.chat.MODELS_DIR", tmp_path / "models")
    (tmp_path / "models").mkdir()
    local_endpoint = type(
        "E",
        (),
        {
            "is_local": True,
            "base_url": "http://127.0.0.1:8787/v1",
            "api_key": None,
            "provider": "local",
        },
    )()
    with (
        patch("akomagni.inference.chat.resolve_inference_endpoint", return_value=local_endpoint),
        patch(
            "akomagni.inference.chat.check_health",
            return_value=InferenceStatus(
                online=True,
                base_url="http://127.0.0.1:8787/v1",
                models=["local"],
            ),
        ),
        patch("akomagni.inference.chat.chat_completion", return_value="Use JWT tokens.") as chat,
    ):
        reply = try_chat_with_inference("implement login", decision)
    assert reply == "Use JWT tokens."
    assert chat.call_args.kwargs["model"] == "local"


def test_try_chat_with_inference_image_domain_skips_locally():
    from akomagni.core.router.domain import DomainClassification, ModelDomain
    from akomagni.core.router.swap import DomainModelPlan, ModelSwapPlan
    from akomagni.inference.endpoint import InferenceEndpoint

    decision = classify_message("génère un logo")
    skip_plan = DomainModelPlan(
        classification=DomainClassification(ModelDomain.IMAGE, 0.9, "image"),
        catalog_name=None,
        model_path=None,
        model_id=None,
        skip_inference=True,
        reason="local image skip",
    )
    with (
        patch(
            "akomagni.inference.chat.resolve_inference_endpoint",
            return_value=InferenceEndpoint(
                provider="local", base_url="http://127.0.0.1:8787/v1", is_local=True
            ),
        ),
        patch(
            "akomagni.inference.chat.plan_inference_chat",
            return_value=__import__(
                "akomagni.inference.chat", fromlist=["InferenceChatPlan"]
            ).InferenceChatPlan(
                domain_plan=skip_plan,
                swap_plan=ModelSwapPlan(
                    needs_swap=False,
                    current_model=None,
                    target_model=None,
                    target_path=None,
                ),
                model_id=None,
            ),
        ),
    ):
        assert try_chat_with_inference("génère un logo", decision) is None


def test_try_chat_with_inference_auto_swap(tmp_path, monkeypatch):
    model = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    model.write_text("gguf", encoding="utf-8")
    monkeypatch.setattr("akomagni.inference.chat.MODELS_DIR", tmp_path)
    decision = classify_message("implement login API")
    phi_status = InferenceStatus(
        online=True,
        base_url="http://127.0.0.1:8787/v1",
        models=["phi-3.5-mini-instruct-q4.gguf"],
    )
    ready_status = InferenceStatus(
        online=True,
        base_url="http://127.0.0.1:8787/v1",
        models=[model.name],
    )
    from akomagni.inference.worker import HotSwapResult

    with (
        patch(
            "akomagni.inference.chat.check_health",
            side_effect=[phi_status, phi_status, ready_status],
        ),
        patch(
            "akomagni.inference.worker.hot_swap_model",
            return_value=HotSwapResult(swapped=True, model_path=model, message="ok"),
        ),
        patch("akomagni.inference.chat.chat_completion", return_value="done"),
    ):
        reply = try_chat_with_inference("implement login", decision, auto_swap=True)
    assert reply == "done"


def test_try_chat_with_inference_client_error():
    decision = classify_message("implement login API")
    local_endpoint = type(
        "E",
        (),
        {
            "is_local": True,
            "base_url": "http://127.0.0.1:8787/v1",
            "api_key": None,
            "provider": "local",
        },
    )()
    with (
        patch("akomagni.inference.chat.resolve_inference_endpoint", return_value=local_endpoint),
        patch(
            "akomagni.inference.chat.check_health",
            return_value=InferenceStatus(
                online=True,
                base_url="http://127.0.0.1:8787/v1",
                models=["local"],
            ),
        ),
        patch(
            "akomagni.inference.chat.chat_completion",
            side_effect=InferenceClientError("down"),
        ),
        pytest.raises(InferenceClientError, match="down"),
    ):
        try_chat_with_inference("implement login", decision)


def test_image_generation_url_and_b64(tmp_path):
    from akomagni.inference.client import image_generation

    with patch(
        "akomagni.inference.client._request_json",
        return_value={"data": [{"url": "https://cdn.example/img.png"}]},
    ):
        out = image_generation(
            "poster",
            base_url="https://api.rodiumai.io/v1",
            api_key="rd_sk_x",
            model="openai/gpt-image-1-mini",
        )
        assert "cdn.example" in out

    # minimal valid base64 ("aa")
    with patch(
        "akomagni.inference.client._request_json",
        return_value={"data": [{"b64_json": "aaaa"}]},
    ):
        out = image_generation(
            "poster",
            base_url="https://api.rodiumai.io/v1",
            model="google/gemini-3.1-flash-lite-image",
            save_dir=tmp_path,
        )
        assert "saved locally" in out
        assert str(tmp_path) in out
        saved = list(tmp_path.glob("akomagni-*.png"))
        assert len(saved) == 1
        assert saved[0].stat().st_size > 0

    with (
        patch("akomagni.inference.client._request_json", return_value={"data": [{}]}),
        pytest.raises(InferenceClientError),
    ):
        image_generation("poster", base_url="https://api.rodiumai.io/v1")
