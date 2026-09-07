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
from akomagni.inference.foundry import (
    FOUNDRY_URL_HINT,
    FOUNDRY_URL_HINT_SERVICES,
    FoundryUrlError,
    deployments_from_models,
    normalize_foundry_base_url,
    project_endpoint_note,
)
from akomagni.inference.providers import apply_provider_preset

PROVIDER_ALIASES = {
    "rodium": "rodium",
    "foundry": "azure",
    "azure": "azure",
    "local": "local",
}

RODIUM_DEFAULT_URL = RODIUM_DEFAULT_BASE_URL

# Re-export for CLI/docs
__all__ = [
    "PROVIDER_ALIASES",
    "RODIUM_DEFAULT_URL",
    "FOUNDRY_URL_HINT",
    "FOUNDRY_URL_HINT_SERVICES",
    "ConnectError",
    "ConnectResult",
    "normalize_provider",
    "connect_provider",
    "sync_vscode_settings",
    "save_config",
]


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
    note: str | None = None


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
    auth: str | None = None,
) -> dict[str, Any]:
    merged = apply_provider_preset(cfg, provider, azure_base_url=base_url)
    providers = dict(merged.get("providers") or {})
    block = dict(providers.get(provider) or {})

    if base_url:
        block["base_url"] = base_url.rstrip("/")
    if api_key:
        block["api_key"] = api_key
    if auth:
        block["auth"] = auth

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
    auth: str | None = None,
    on_progress: Any | None = None,
    skip_entra_setup: bool = False,
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

    # Foundry defaults to Entra unless an API key is explicitly provided.
    raw_auth = (auth or "").strip().lower()
    if provider == "azure":
        if raw_auth in {"api_key", "key"}:
            auth_mode = "api_key"
        elif raw_auth in {"entra", "aad", "token", "bearer_token"}:
            auth_mode = "entra"
        elif api_key and str(api_key).strip():
            auth_mode = "api_key"
        else:
            auth_mode = "entra"
    else:
        auth_mode = "api_key"

    if provider == "rodium":
        url = (base_url or RODIUM_DEFAULT_URL).strip().rstrip("/")
    else:
        try:
            url = normalize_foundry_base_url(base_url or "")
        except FoundryUrlError as exc:
            raise ConnectError(str(exc)) from exc

    setup_notes: list[str] = []
    if provider == "azure" and auth_mode == "entra" and not skip_entra_setup:
        from akomagni.inference.foundry_bootstrap import ensure_foundry_entra

        setup = ensure_foundry_entra(login_if_needed=True, on_progress=on_progress)
        setup_notes.extend(setup.messages)
        if not setup.ok:
            raise ConnectError(
                setup.error
                or "Foundry Entra setup failed. Pass an API key or fix Azure login."
            )

    if auth_mode == "api_key" and (not api_key or not api_key.strip()):
        raise ConnectError("API key is required for key-based Foundry auth")

    cfg = _merge_provider_credentials(
        load_config(),
        provider,
        base_url=url,
        api_key=api_key.strip() if api_key and auth_mode == "api_key" else None,
        auth=auth_mode if provider == "azure" else None,
    )
    if provider == "azure" and auth_mode == "entra":
        providers = dict(cfg.get("providers") or {})
        block = dict(providers.get("azure") or {})
        block["auth"] = "entra"
        block.pop("api_key", None)
        providers["azure"] = block
        cfg["providers"] = providers

    save_config(cfg)

    status = check_health_from_config(cfg)

    # Seed deployments from live /models when Foundry reports them
    if provider == "azure" and status.models:
        mapped = deployments_from_models(status.models)
        if mapped:
            providers = dict(cfg.get("providers") or {})
            block = dict(providers.get("azure") or {})
            block["deployments"] = mapped
            providers["azure"] = block
            cfg["providers"] = providers
            save_config(cfg)

    if sync_ide:
        prov_block = (cfg.get("providers") or {}).get(provider) or {}
        models = prov_block.get("models") or prov_block.get("deployments") or {}
        model = str(next(iter(models.values()))) if isinstance(models, dict) and models else None
        if status.models:
            model = status.models[0]
        sync_vscode_settings(
            workspace,
            provider=provider,
            base_url=url,
            api_key=api_key.strip() if api_key and auth_mode == "api_key" else None,
            model=model,
        )

    note = project_endpoint_note(url) if provider == "azure" else None
    if setup_notes and note:
        note = f"{note}\n" + "\n".join(setup_notes[-3:])
    elif setup_notes:
        note = "\n".join(setup_notes[-3:])

    return ConnectResult(
        provider=provider,
        base_url=url,
        api_key_saved=bool(api_key and auth_mode == "api_key"),
        online=status.online,
        models=status.models,
        error=status.error,
        note=note,
    )
