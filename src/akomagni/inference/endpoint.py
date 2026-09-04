"""Resolve inference endpoints from Akomagni config (local, Rodium, Azure)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from akomagni.core.config import load_config
from akomagni.inference.client import api_base_url

RODIUM_DEFAULT_BASE_URL = "https://api.rodiumai.io/v1"
RODIUM_DEFAULT_MODELS = {
    "code": "rodium/pro",
    "design": "rodium/pro",
    "text": "rodium/fast",
}
AZURE_DEFAULT_MODELS = {
    "code": "gpt-4o",
    "design": "gpt-4o",
    "text": "gpt-4o-mini",
}


@dataclass(frozen=True)
class InferenceEndpoint:
    """OpenAI-compatible API endpoint."""

    provider: str
    base_url: str
    api_key: str | None = None
    is_local: bool = False


def _resolve_api_key(*, env_var: str | None, inline: str | None = None) -> str | None:
    if inline and str(inline).strip():
        return str(inline).strip()
    if env_var:
        value = os.environ.get(env_var)
        if value and value.strip():
            return value.strip()
    return None


def resolve_inference_endpoint(config: dict[str, Any] | None = None) -> InferenceEndpoint:
    """Build an endpoint from ``config.inference`` and ``config.providers``."""
    cfg = config or load_config()
    inf = cfg.get("inference") or {}
    provider = str(inf.get("provider", "local")).lower()
    providers = cfg.get("providers") or {}

    if provider == "rodium":
        prov = providers.get("rodium") or {}
        base = str(prov.get("base_url") or RODIUM_DEFAULT_BASE_URL).rstrip("/")
        key = _resolve_api_key(
            env_var=str(prov.get("api_key_env") or "RODIUMAI_API_KEY"),
            inline=prov.get("api_key"),
        )
        return InferenceEndpoint(provider="rodium", base_url=base, api_key=key)

    if provider == "azure":
        prov = providers.get("azure") or {}
        base = str(prov.get("base_url") or "").rstrip("/")
        key = _resolve_api_key(
            env_var=str(prov.get("api_key_env") or "AZURE_OPENAI_API_KEY"),
            inline=prov.get("api_key"),
        )
        return InferenceEndpoint(provider="azure", base_url=base, api_key=key)

    host = str(inf.get("host", "127.0.0.1"))
    port = int(inf.get("port", 8787))
    return InferenceEndpoint(
        provider="local",
        base_url=api_base_url(host=host, port=port),
        is_local=True,
    )


def cloud_model_for_domain(domain: str, *, config: dict[str, Any] | None = None) -> str | None:
    """Return a cloud model/deployment id for *domain* when provider is not local."""
    cfg = config or load_config()
    inf = cfg.get("inference") or {}
    provider = str(inf.get("provider", "local")).lower()
    if provider == "local":
        return None

    providers = cfg.get("providers") or {}
    prov = providers.get(provider) or {}
    models = prov.get("models") or prov.get("deployments") or {}
    if provider == "rodium" and not models:
        models = RODIUM_DEFAULT_MODELS
    if provider == "azure" and not models:
        models = AZURE_DEFAULT_MODELS

    value = models.get(domain) or prov.get("default_model")
    if value is None or str(value).strip().lower() in {"", "none", "null"}:
        return None
    return str(value).strip()


def provider_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize the active inference provider for CLI/doctor."""
    endpoint = resolve_inference_endpoint(config)
    cfg = config or load_config()
    inf = cfg.get("inference") or {}
    return {
        "provider": endpoint.provider,
        "base_url": endpoint.base_url,
        "api_key_set": bool(endpoint.api_key),
        "is_local": endpoint.is_local,
        "default_model": inf.get("default_model"),
    }
