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
        patch("akomagni.inference.chat.chat_completion", return_value="Use JWT tokens."),
    ):
        reply = try_chat_with_inference("implement login", decision)
    assert reply == "Use JWT tokens."
