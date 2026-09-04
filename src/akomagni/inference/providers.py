"""Provider presets for Rodium AI and Azure AI Foundry."""

from __future__ import annotations

from typing import Any

from akomagni.inference.endpoint import (
    AZURE_DEFAULT_MODELS,
    RODIUM_DEFAULT_BASE_URL,
    RODIUM_DEFAULT_MODELS,
)

FOUNDRY_TOOLKIT_EXTENSION = "ms-windows-ai-studio.windows-ai-studio"
FOUNDRY_TOOLKIT_NAME = "Microsoft Foundry Toolkit"
AKOMAGNI_CHAT_EXTENSION = "Akomagni.akomagni"
AKOMAGNI_CHAT_NAME = "Akomagni"


def rodium_provider_block(*, api_key_env: str = "RODIUMAI_API_KEY") -> dict[str, Any]:
    return {
        "base_url": RODIUM_DEFAULT_BASE_URL,
        "api_key_env": api_key_env,
        "models": dict(RODIUM_DEFAULT_MODELS),
    }


def azure_provider_block(
    *,
    base_url: str,
    api_key_env: str = "AZURE_OPENAI_API_KEY",
    deployments: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "base_url": base_url.rstrip("/"),
        "api_key_env": api_key_env,
        "deployments": deployments or dict(AZURE_DEFAULT_MODELS),
    }


def apply_provider_preset(
    cfg: dict[str, Any],
    provider: str,
    *,
    azure_base_url: str | None = None,
) -> dict[str, Any]:
    """Return a merged config with *provider* activated."""
    merged = {**cfg}
    inference = {**(merged.get("inference") or {}), "provider": provider}
    providers = {**(merged.get("providers") or {})}

    if provider == "rodium":
        providers["rodium"] = {**rodium_provider_block(), **(providers.get("rodium") or {})}
    elif provider == "azure":
        base = azure_base_url or (providers.get("azure") or {}).get("base_url") or ""
        providers["azure"] = {
            **azure_provider_block(base_url=str(base)),
            **(providers.get("azure") or {}),
        }
    elif provider == "local":
        pass
    else:
        msg = f"Unknown provider: {provider} (use: local, rodium, azure)"
        raise ValueError(msg)

    merged["inference"] = inference
    merged["providers"] = providers
    return merged
