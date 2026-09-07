"""Microsoft Foundry / Azure OpenAI v1 helpers.

Aligned with:
https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints
https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

FOUNDRY_URL_HINT = "https://YOUR-RESOURCE.openai.azure.com/openai/v1/"
FOUNDRY_URL_HINT_SERVICES = "https://YOUR-RESOURCE.services.ai.azure.com/openai/v1/"
FOUNDRY_DOCS_URL = "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints"

# Env vars documented by Microsoft / Akomagni
AZURE_API_KEY_ENV = "AZURE_OPENAI_API_KEY"
AZURE_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
AZURE_INFERENCE_CREDENTIAL_ENV = "AZURE_INFERENCE_CREDENTIAL"
AZURE_AUTH_ENV = "AZURE_OPENAI_AUTH"
ENTRA_SCOPE = "https://ai.azure.com/.default"

_TRAILING_ROUTE_RE = re.compile(
    r"/(?:chat/completions|completions|responses|models|embeddings)/?$",
    re.IGNORECASE,
)


class FoundryUrlError(ValueError):
    """Invalid or unsupported Foundry endpoint URL."""


def is_foundry_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host.endswith(".openai.azure.com") or host.endswith(".services.ai.azure.com")


def is_foundry_project_path(path: str) -> bool:
    return "/api/projects/" in (path or "").lower()


def normalize_foundry_base_url(raw: str) -> str:
    """Normalize a Foundry / Azure OpenAI URL to an OpenAI-compatible ``…/openai/v1`` root.

    Accepts:
    - ``https://<res>.openai.azure.com``
    - ``https://<res>.openai.azure.com/openai/v1``
    - ``https://<res>.services.ai.azure.com``
    - ``https://<res>.services.ai.azure.com/openai/v1``
    - ``https://<res>.services.ai.azure.com/api/projects/<project>``
      → ``…/api/projects/<project>/openai/v1`` (project-scoped OpenAI route)

    Raises FoundryUrlError when the URL cannot be normalized safely.
    """
    text = (raw or "").strip()
    if not text:
        raise FoundryUrlError(
            f"Foundry URL required. Examples: {FOUNDRY_URL_HINT} or {FOUNDRY_URL_HINT_SERVICES}"
        )

    if "://" not in text:
        text = f"https://{text}"

    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise FoundryUrlError(f"Foundry URL must be https://… (got scheme {parsed.scheme!r})")
    if not parsed.netloc:
        raise FoundryUrlError(f"Foundry URL missing host. Example: {FOUNDRY_URL_HINT}")

    path = parsed.path or ""
    path = _TRAILING_ROUTE_RE.sub("", path).rstrip("/")

    # Collapse accidental double openai/v1 segments
    while "/openai/v1/openai/v1" in path.lower():
        path = re.sub(r"(?i)/openai/v1/openai/v1", "/openai/v1", path)

    lower_path = path.lower()
    host = parsed.netloc.lower()

    if lower_path.endswith("/openai/v1"):
        normalized_path = path
    elif lower_path.endswith("/openai"):
        normalized_path = f"{path}/v1"
    elif is_foundry_project_path(path):
        # Project endpoint serves OpenAI routes under {project}/openai/v1
        if "/openai/" in lower_path:
            # e.g. …/api/projects/foo/openai → add /v1
            if not lower_path.endswith("/v1"):
                normalized_path = f"{path.rstrip('/')}/v1" if lower_path.endswith("/openai") else f"{path}/openai/v1"
            else:
                normalized_path = path
        else:
            normalized_path = f"{path}/openai/v1"
    elif is_foundry_host(host) or "azure.com" in host:
        if "/openai/" not in lower_path:
            normalized_path = f"{path}/openai/v1" if path else "/openai/v1"
        elif lower_path.endswith("/v1"):
            normalized_path = path
        else:
            normalized_path = f"{path.rstrip('/')}/openai/v1"
    else:
        # Non-Azure host: only append /openai/v1 when clearly Azure-shaped; else require explicit path
        raise FoundryUrlError(
            "Unrecognized Foundry host. Use "
            f"{FOUNDRY_URL_HINT} or {FOUNDRY_URL_HINT_SERVICES} "
            f"(docs: {FOUNDRY_DOCS_URL})"
        )

    # Clean path
    normalized_path = re.sub(r"/{2,}", "/", normalized_path)
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"

    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}".rstrip("/")


def foundry_auth_headers(
    credential: str | None,
    *,
    auth_mode: str = "api_key",
) -> dict[str, str]:
    """Build HTTP headers for Foundry / Azure OpenAI v1.

    - API key: send both ``Authorization: Bearer`` and ``api-key`` (Microsoft accepts either).
    - Entra: send only ``Authorization: Bearer <token>`` (no api-key header).
    """
    if not credential or not str(credential).strip():
        return {}
    token = str(credential).strip()
    mode = (auth_mode or "api_key").strip().lower()
    if mode in {"entra", "aad", "token", "bearer_token"}:
        return {"Authorization": f"Bearer {token}"}
    return {
        "Authorization": f"Bearer {token}",
        "api-key": token,
    }


def resolve_azure_auth_mode(provider_block: dict[str, Any] | None = None) -> str:
    """Resolve auth mode. Default for Foundry is Entra when no API key is configured."""
    block = provider_block or {}
    raw = str(block.get("auth") or os.environ.get(AZURE_AUTH_ENV) or "").strip().lower()
    if raw in {"entra", "aad", "token", "bearer_token", "microsoft_entra"}:
        return "entra"
    if raw in {"api_key", "key"}:
        return "api_key"
    # Implicit: prefer Entra unless a key is already available
    if resolve_azure_api_key(block):
        return "api_key"
    return "entra"


def get_foundry_entra_token(*, scope: str = ENTRA_SCOPE) -> str:
    """Fetch a Microsoft Entra access token for Foundry (requires azure-identity)."""
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover - optional dep
        raise RuntimeError(
            "Entra authentication requires azure-identity. "
            "Install with: pip install azure-identity"
        ) from exc

    credential = DefaultAzureCredential()
    token = credential.get_token(scope)
    if not token or not token.token:
        raise RuntimeError("Failed to obtain Entra token for Foundry (empty token)")
    return token.token


def resolve_azure_api_key(provider_block: dict[str, Any] | None = None) -> str | None:
    """Resolve API key from inline config or env (AZURE_OPENAI_API_KEY / AZURE_INFERENCE_CREDENTIAL)."""
    block = provider_block or {}
    inline = block.get("api_key")
    if inline and str(inline).strip():
        return str(inline).strip()

    env_var = str(block.get("api_key_env") or AZURE_API_KEY_ENV).strip() or AZURE_API_KEY_ENV
    for name in (env_var, AZURE_API_KEY_ENV, AZURE_INFERENCE_CREDENTIAL_ENV):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_azure_endpoint_url(provider_block: dict[str, Any] | None = None) -> str:
    """Resolve and normalize Azure/Foundry base URL from config or AZURE_OPENAI_ENDPOINT."""
    block = provider_block or {}
    raw = str(block.get("base_url") or "").strip()
    if not raw:
        raw = str(os.environ.get(AZURE_ENDPOINT_ENV) or "").strip()
    if not raw:
        return ""
    return normalize_foundry_base_url(raw)


def deployments_from_models(models: list[str] | None) -> dict[str, str] | None:
    """Pick sensible code/design/text deployment names from a /models listing."""
    if not models:
        return None
    cleaned = [str(m).strip() for m in models if str(m).strip()]
    if not cleaned:
        return None

    preferred_code = (
        "gpt-4.1",
        "gpt-4o",
        "gpt-4",
        "gpt-35-turbo",
        "gpt-3.5",
    )

    def _pick(needles: tuple[str, ...], *, allow_mini: bool) -> str:
        for needle in needles:
            exact = next((m for m in cleaned if m.lower() == needle), None)
            if exact:
                return exact
            hits = [m for m in cleaned if needle in m.lower()]
            if not allow_mini:
                hits = [m for m in hits if "mini" not in m.lower() and "nano" not in m.lower()] or hits
            if hits:
                return hits[0]
        return cleaned[0]

    pick = _pick(preferred_code, allow_mini=False)
    text_pick = next(
        (m for m in cleaned if any(x in m.lower() for x in ("mini", "nano", "small"))),
        pick,
    )
    return {"code": pick, "design": pick, "text": text_pick}


def project_endpoint_note(url: str) -> str | None:
    """Optional user-facing note when a project-scoped endpoint is used."""
    if is_foundry_project_path(urlparse(url).path):
        return (
            "Using Foundry project OpenAI route (…/api/projects/<name>/openai/v1). "
            "This is for model inference only — project connections/agents need the Foundry SDK."
        )
    return None
