"""Interactive cloud provider connection for Akomagni."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from akomagni.core.config import load_config
from akomagni.inference.client import check_health_from_config
from akomagni.inference.endpoint import RODIUM_DEFAULT_BASE_URL
from akomagni.inference.providers import apply_provider_preset

PROVIDER_ALIASES = {
    "rodium": "rodium",
    "foundry": "azure",
    "azure": "azure",
    "local": "local",
}

RODIUM_DEFAULT_URL = RODIUM_DEFAULT_BASE_URL
FOUNDRY_URL_HINT = "https://YOUR-RESOURCE.openai.azure.com/openai/v1/"


class ConnectError(RuntimeError):
    """Raised when provider connection fails."""


@dataclass(frozen=True)
class ConnectResult:
    provider: str
    base_url: str
    api_key_saved: bool
    online: bool
    models: list[str] | None = None
    error: str | None = None


def normalize_provider(name: str) -> str:
    key = name.strip().lower()
    if key not in PROVIDER_ALIASES:
        allowed = ", ".join(sorted({"rodium", "foundry", "local"}))
        raise ConnectError(f"Unknown provider '{name}' (use: {allowed})")
    return PROVIDER_ALIASES[key]


def _merge_provider_credentials(
    cfg: dict[str, Any],
    provider: str,
    *,
    base_url: str | None,
    api_key: str | None,
) -> dict[str, Any]:
    merged = apply_provider_preset(cfg, provider, azure_base_url=base_url)
    providers = dict(merged.get("providers") or {})
    block = dict(providers.get(provider) or {})

    if base_url:
        block["base_url"] = base_url.rstrip("/")
    if api_key:
        block["api_key"] = api_key

    providers[provider] = block
    merged["providers"] = providers
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    from akomagni.core import config as config_mod

    config_mod.CONFIG_PATH.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def sync_vscode_settings(
    workspace: Path | None,
    *,
    provider: str,
    base_url: str,
    api_key: str | None,
    model: str | None = None,
) -> Path | None:
    """Write VS Code settings for the Akomagni Chat extension."""
    root = (workspace or Path.cwd()).resolve()
    if not root.is_dir():
        return None
    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings_path = vscode_dir / "settings.json"
    payload: dict[str, Any] = {}
    if settings_path.is_file():
        with settings_path.open(encoding="utf-8") as handle:
            try:
                loaded = json.loads(handle.read())
            except json.JSONDecodeError:
                loaded = {}
            payload = loaded if isinstance(loaded, dict) else {}

    payload["akomagni.provider"] = provider
    payload["akomagni.baseUrl"] = base_url
    if api_key:
        payload["akomagni.apiKey"] = api_key
    if model:
        payload["akomagni.model"] = model

    settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return settings_path


def connect_provider(
    provider_name: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    workspace: Path | None = None,
    sync_ide: bool = True,
) -> ConnectResult:
    """Connect *provider_name* and persist credentials to Akomagni config."""
    provider = normalize_provider(provider_name)

    if provider == "local":
        cfg = apply_provider_preset(load_config(), "local")
        save_config(cfg)
        return ConnectResult(
            provider="local",
            base_url="http://127.0.0.1:8787/v1",
            api_key_saved=False,
            online=False,
        )

    if provider == "rodium":
        url = (base_url or RODIUM_DEFAULT_URL).strip().rstrip("/")
    else:
        url = (base_url or "").strip().rstrip("/")
        if not url:
            raise ConnectError(f"Foundry URL required. Example: {FOUNDRY_URL_HINT}")
        if not url.endswith("/v1"):
            if url.endswith("/openai"):
                url = f"{url}/v1"
            elif "/openai/" not in url:
                url = f"{url.rstrip('/')}/openai/v1"

    if not api_key or not api_key.strip():
        raise ConnectError("API key is required")

    cfg = _merge_provider_credentials(
        load_config(),
        provider,
        base_url=url,
        api_key=api_key.strip(),
    )
    save_config(cfg)

    if sync_ide:
        prov_block = (cfg.get("providers") or {}).get(provider) or {}
        models = prov_block.get("models") or prov_block.get("deployments") or {}
        model = str(next(iter(models.values()))) if isinstance(models, dict) and models else None
        sync_vscode_settings(
            workspace,
            provider=provider,
            base_url=url,
            api_key=api_key.strip(),
            model=model,
        )

    status = check_health_from_config(cfg)
    return ConnectResult(
        provider=provider,
        base_url=url,
        api_key_saved=True,
        online=status.online,
        models=status.models,
        error=status.error,
    )
