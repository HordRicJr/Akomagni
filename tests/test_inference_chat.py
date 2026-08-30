"""Tests for inference chat wiring."""

from __future__ import annotations

from unittest.mock import patch

from akomagni.flow.intent import classify_message
from akomagni.inference.chat import build_flow_system_prompt, try_chat_with_inference
from akomagni.inference.client import InferenceStatus


def test_build_flow_system_prompt():
    decision = classify_message("implement login API")
    prompt = build_flow_system_prompt(decision)
    assert decision.agent_id in prompt
    assert decision.skill in prompt


def test_try_chat_with_inference_offline():
    decision = classify_message("hello")
    with patch(
        "akomagni.inference.chat.check_health",
        return_value=InferenceStatus(online=False, base_url="http://127.0.0.1:8787/v1"),
    ):
        assert try_chat_with_inference("hello", decision) is None


def test_try_chat_with_inference_online():
    decision = classify_message("implement login API")
    with (
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


def test_try_chat_with_inference_image_domain_skips():
    decision = classify_message("génère un logo")
    with patch(
        "akomagni.inference.chat.check_health",
        return_value=InferenceStatus(
            online=True, base_url="http://127.0.0.1:8787/v1", models=["m"]
        ),
    ):
        assert try_chat_with_inference("génère un logo", decision) is None


def test_try_chat_with_inference_auto_swap(tmp_path, monkeypatch):
    model = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    model.write_text("gguf", encoding="utf-8")
    monkeypatch.setattr("akomagni.inference.chat.MODELS_DIR", tmp_path)
    decision = classify_message("implement login API")
    statuses = [
        InferenceStatus(
            online=True,
            base_url="http://127.0.0.1:8787/v1",
            models=["phi-3.5-mini-instruct-q4.gguf"],
        ),
        InferenceStatus(
            online=True,
            base_url="http://127.0.0.1:8787/v1",
            models=[model.name],
        ),
    ]
    from akomagni.inference.worker import HotSwapResult

    with (
        patch("akomagni.inference.chat.check_health", side_effect=statuses),
        patch(
            "akomagni.inference.worker.hot_swap_model",
            return_value=HotSwapResult(swapped=True, model_path=model, message="ok"),
        ),
        patch("akomagni.inference.chat.chat_completion", return_value="done"),
    ):
        reply = try_chat_with_inference("implement login", decision, auto_swap=True)
    assert reply == "done"
