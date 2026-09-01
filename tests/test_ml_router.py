"""Tests for ML intent router."""

from __future__ import annotations

from unittest.mock import patch

from akomagni.flow.intent import classify_message
from akomagni.flow.ml_router import classify_via_ml, classify_with_router


def test_classify_with_router_heuristic_mode():
    decision = classify_with_router("implement login API", mode="heuristic")
    heuristic = classify_message("implement login API")
    assert decision.agent_id == heuristic.agent_id
    assert decision.skill == heuristic.skill


def test_classify_with_router_ml_fallback_when_offline():
    with patch("akomagni.inference.client.check_health") as mock_health:
        mock_health.return_value = type("S", (), {"online": False})()
        decision = classify_with_router("implement login API", mode="ml")
    assert decision.agent_id == "bmad-agent-dev"


def test_classify_via_ml_parses_json():
    fake_reply = '{"agent_id": "bmad-agent-dev", "confidence": 0.9, "reason": "code task"}'
    with (
        patch("akomagni.inference.client.check_health") as mock_health,
        patch("akomagni.inference.client.chat_completion", return_value=fake_reply),
    ):
        mock_health.return_value = type("S", (), {"online": True})()
        decision = classify_via_ml("fix the auth bug")
    assert decision is not None
    assert decision.agent_id == "bmad-agent-dev"
    assert decision.confidence == 0.9


def test_classify_via_ml_invalid_agent_returns_none():
    fake_reply = '{"agent_id": "unknown-agent", "confidence": 0.9}'
    with (
        patch("akomagni.inference.client.check_health") as mock_health,
        patch("akomagni.inference.client.chat_completion", return_value=fake_reply),
    ):
        mock_health.return_value = type("S", (), {"online": True})()
        assert classify_via_ml("hello") is None


def test_classify_via_ml_invalid_json_returns_none():
    with (
        patch("akomagni.inference.client.check_health") as mock_health,
        patch("akomagni.inference.client.chat_completion", return_value="not json"),
    ):
        mock_health.return_value = type("S", (), {"online": True})()
        assert classify_via_ml("hello") is None


def test_classify_with_router_auto_uses_ml_when_online():
    fake_reply = '{"agent_id": "bmad-agent-pm", "confidence": 0.88, "reason": "spec"}'
    with (
        patch("akomagni.inference.client.check_health") as mock_health,
        patch("akomagni.inference.client.chat_completion", return_value=fake_reply),
    ):
        mock_health.return_value = type("S", (), {"online": True})()
        decision = classify_with_router("write a PRD for auth", mode="auto")
    assert decision.agent_id == "bmad-agent-pm"


def test_parse_ml_response():
    from akomagni.flow.ml_router import _parse_ml_response

    assert _parse_ml_response('prefix {"agent_id": "akomagni", "confidence": 0.5} suffix') is not None
