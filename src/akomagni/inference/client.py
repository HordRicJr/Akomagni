"""OpenAI-compatible HTTP client for local llama-server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InferenceClientError(RuntimeError):
    """Raised when the inference API is unreachable or returns an error."""


@dataclass(frozen=True)
class InferenceStatus:
    online: bool
    base_url: str
    health_url: str | None = None
    models: list[str] | None = None
    error: str | None = None


def api_base_url(*, host: str = "127.0.0.1", port: int = 8787) -> str:
    return f"http://{host}:{port}/v1"


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)  # nosec B310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise InferenceClientError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise InferenceClientError(str(exc)) from exc


def check_health(*, host: str = "127.0.0.1", port: int = 8787) -> InferenceStatus:
    """Probe llama-server health and list available models."""
    base = f"http://{host}:{port}"
    base_v1 = api_base_url(host=host, port=port)
    online = False
    health_url: str | None = None
    models: list[str] | None = None

    try:
        _request_json(f"{base}/health", timeout=3.0)
        online = True
        health_url = f"{base}/health"
    except InferenceClientError:
        pass

    try:
        data = _request_json(f"{base_v1}/models", timeout=3.0)
        online = True
        if health_url is None:
            health_url = f"{base_v1}/models"
        if isinstance(data, dict):
            model_ids = [
                str(item["id"])
                for item in data.get("data", [])
                if isinstance(item, dict) and item.get("id")
            ]
            if model_ids:
                models = model_ids
    except InferenceClientError:
        pass

    if online:
        return InferenceStatus(
            online=True,
            base_url=base_v1,
            health_url=health_url,
            models=models,
        )
    return InferenceStatus(
        online=False,
        base_url=base_v1,
        error="Inference server offline — run: akomagni serve",
    )


def chat_completion(
    message: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
    system_prompt: str | None = None,
    timeout: float = 120.0,
) -> str:
    """Send a chat completion request to /v1/chat/completions."""
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})

    payload: dict[str, Any] = {
        "messages": messages,
        "stream": False,
    }
    if model:
        payload["model"] = model

    url = f"{api_base_url(host=host, port=port)}/chat/completions"
    data = _request_json(url, method="POST", payload=payload, timeout=timeout)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InferenceClientError(f"Unexpected API response: {data!r}") from exc
