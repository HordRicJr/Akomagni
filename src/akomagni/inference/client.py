"""OpenAI-compatible HTTP client for local llama-server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
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
    provider: str = "local"


def api_base_url(*, host: str = "127.0.0.1", port: int = 8787) -> str:
    return f"http://{host}:{port}/v1"


def _auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
    api_key: str | None = None,
) -> Any:
    data = None
    headers = {"Accept": "application/json", **_auth_headers(api_key)}
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


def check_health(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    base_url: str | None = None,
    api_key: str | None = None,
    provider: str = "local",
) -> InferenceStatus:
    """Probe an OpenAI-compatible /v1 API (local llama-server or cloud)."""
    base_v1 = (base_url or api_base_url(host=host, port=port)).rstrip("/")
    base = base_v1.removesuffix("/v1")
    online = False
    health_url: str | None = None
    models: list[str] | None = None

    if provider == "local":
        try:
            _request_json(f"{base}/health", timeout=3.0)
            online = True
            health_url = f"{base}/health"
        except InferenceClientError:
            pass

    try:
        data = _request_json(f"{base_v1}/models", timeout=8.0, api_key=api_key)
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
            provider=provider,
        )
    offline_hint = "Inference server offline — run: akomagni serve"
    if provider == "rodium":
        offline_hint = "Rodium AI offline — check RODIUMAI_API_KEY and network"
    elif provider == "azure":
        offline_hint = "Azure Foundry offline — check AZURE_OPENAI_API_KEY and base_url"
    return InferenceStatus(
        online=False,
        base_url=base_v1,
        error=offline_hint,
        provider=provider,
    )


def check_health_from_config(config: dict | None = None) -> InferenceStatus:
    """Probe the configured inference provider."""
    from akomagni.inference.endpoint import resolve_inference_endpoint

    endpoint = resolve_inference_endpoint(config)
    if endpoint.is_local:
        base = endpoint.base_url.rstrip("/")
        host_port = base.removeprefix("http://").removeprefix("https://").split("/")[0]
        host, _, port_str = host_port.partition(":")
        port = int(port_str or 8787)
        return check_health(host=host, port=port, provider="local")
    return check_health(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        provider=endpoint.provider,
    )


def chat_completion(
    message: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    base_url: str | None = None,
    api_key: str | None = None,
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

    root = (base_url or api_base_url(host=host, port=port)).rstrip("/")
    url = f"{root}/chat/completions"
    data = _request_json(url, method="POST", payload=payload, timeout=timeout, api_key=api_key)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise InferenceClientError(f"Unexpected API response: {data!r}") from exc


@dataclass(frozen=True)
class ImageArtifact:
    """Result of a cloud image generation call."""

    model: str
    url: str | None = None
    b64_json: str | None = None
    local_path: Path | None = None

    def summary(self) -> str:
        if self.local_path is not None:
            return f"Image generated ({self.model})\nSaved: {self.local_path}"
        if self.url:
            return f"Image generated ({self.model})\nURL: {self.url}"
        return f"Image generated ({self.model}) — awaiting save path"


def image_generation(
    prompt: str,
    *,
    base_url: str,
    api_key: str | None = None,
    model: str = "google/gemini-3.1-flash-image",
    size: str = "1024x1024",
    timeout: float = 180.0,
) -> ImageArtifact:
    """Call OpenAI-compatible ``/v1/images/generations`` (Rodium image guide)."""
    root = base_url.rstrip("/")
    url = f"{root}/images/generations"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if model.startswith("openai/"):
        payload["response_format"] = "url"
    data = _request_json(url, method="POST", payload=payload, timeout=timeout, api_key=api_key)
    if not isinstance(data, dict):
        raise InferenceClientError(f"Unexpected image response: {data!r}")
    items = data.get("data") or []
    if not items:
        raise InferenceClientError(f"No image data in response: {data!r}")
    first = items[0] if isinstance(items[0], dict) else {}
    remote_url = first.get("url")
    if remote_url:
        return ImageArtifact(model=model, url=str(remote_url))
    raw_b64 = first.get("b64_json")
    if raw_b64:
        return ImageArtifact(model=model, b64_json=str(raw_b64))
    raise InferenceClientError(f"Unexpected image payload: {first!r}")


def _normalize_image_b64(raw: str) -> str:
    """Strip data-URL prefix / whitespace from provider ``b64_json`` payloads."""
    text = (raw or "").strip()
    if text.lower().startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    return "".join(text.split())


def _write_bytes_chunked(dest: Path, data: bytes, *, chunk_size: int = 8 * 1024 * 1024) -> None:
    """Write *data* in chunks — Windows can raise Errno 22 on huge single writes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        if len(data) <= chunk_size:
            handle.write(data)
            return
        for offset in range(0, len(data), chunk_size):
            handle.write(data[offset : offset + chunk_size])


def save_image_artifact(artifact: ImageArtifact, destination: Path) -> Path:
    """Write *artifact* to *destination* (file or directory). Returns final file path."""
    import base64
    import binascii
    from datetime import datetime

    dest = destination.expanduser()
    if dest.exists() and dest.is_dir():
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        dest = dest / f"akomagni-{stamp}.png"
    elif dest.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        dest = dest / f"akomagni-{stamp}.png"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)

    if artifact.b64_json is not None:
        payload = _normalize_image_b64(artifact.b64_json)
        # Some gateways put a temporary HTTPS URL in the b64 field.
        if payload.lower().startswith(("http://", "https://")):
            artifact = ImageArtifact(model=artifact.model, url=payload)
        else:
            try:
                pixels = base64.b64decode(payload, validate=False)
            except (binascii.Error, ValueError) as exc:
                raise InferenceClientError(f"Could not decode image base64: {exc}") from exc
            if not pixels:
                raise InferenceClientError("Could not decode image base64: empty payload")
            try:
                _write_bytes_chunked(dest, pixels)
            except OSError as exc:
                raise InferenceClientError(f"Could not write image file: {exc}") from exc
            return dest.resolve()

    if artifact.url:
        request = urllib.request.Request(
            artifact.url,
            headers={"User-Agent": "akomagni/0.3"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # nosec B310
                _write_bytes_chunked(dest, response.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise InferenceClientError(f"Could not download image URL: {exc}") from exc
        return dest.resolve()

    if artifact.local_path and artifact.local_path.is_file():
        _write_bytes_chunked(dest, artifact.local_path.read_bytes())
        return dest.resolve()

    raise InferenceClientError("Image has no URL or pixel data to save")


def default_image_save_path(*, project_root: Path | None = None) -> Path:
    """Sensible default: current project (or cwd) / generated image file."""
    from datetime import datetime

    root = project_root or Path.cwd()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return (root / f"akomagni-affiche-{stamp}.png").resolve()
