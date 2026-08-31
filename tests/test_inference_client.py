"""OpenAI-compatible inference client tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from akomagni.inference.client import (
    InferenceClientError,
    api_base_url,
    chat_completion,
    check_health,
)


def test_api_base_url():
    assert api_base_url(host="127.0.0.1", port=8787) == "http://127.0.0.1:8787/v1"


def test_check_health_online():
    health_payload = json.dumps({"status": "ok"}).encode()
    models_payload = json.dumps({"data": [{"id": "local-model"}]}).encode()

    def fake_urlopen(request, timeout=30.0):
        url = request.full_url
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        if url.endswith("/health"):
            mock_response.read.return_value = health_payload
        else:
            mock_response.read.return_value = models_payload
        return mock_response

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status = check_health()
    assert status.online is True
    assert status.models == ["local-model"]


def test_check_health_models_only():
    models_payload = json.dumps({"data": [{"id": "local-model"}]}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = models_payload
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    def fake_urlopen(request, timeout=30.0):
        if request.full_url.endswith("/health"):
            raise OSError("refused")
        return mock_response

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status = check_health()
    assert status.online is True
    assert status.models == ["local-model"]


def test_check_health_offline():
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        status = check_health()
    assert status.online is False
    assert status.error is not None


def test_chat_completion_success():
    payload = json.dumps({"choices": [{"message": {"content": "Hello from Akomagni"}}]}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_response):
        reply = chat_completion("Hi", model="local")
    assert reply == "Hello from Akomagni"


def test_chat_completion_with_system_prompt():
    payload = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
        reply = chat_completion("Hi", system_prompt="You are helpful.")
    assert reply == "OK"
    sent = json.loads(mock_open.call_args[0][0].data.decode())
    assert sent["messages"][0]["role"] == "system"


def test_request_json_http_error():
    import urllib.error

    from akomagni.inference.client import _request_json

    mock_exc = urllib.error.HTTPError("http://x", 500, "err", {}, None)
    mock_exc.read = MagicMock(return_value=b"server error")
    with (
        patch("urllib.request.urlopen", side_effect=mock_exc),
        pytest.raises(InferenceClientError, match="HTTP 500"),
    ):
        _request_json("http://127.0.0.1:8787/health")


def test_chat_completion_bad_response():
    payload = json.dumps({"unexpected": True}).encode()
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    with (
        patch("urllib.request.urlopen", return_value=mock_response),
        pytest.raises(InferenceClientError),
    ):
        chat_completion("Hi")
