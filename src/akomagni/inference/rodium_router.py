"""Rodium multi-provider model routing (economical + fit-for-task).

RodiumAi is a billing gateway: requests use provider-scoped catalogue ids
(``google/…``, ``anthropic/…``, ``openai/…``, ``rodiumai/smart``, …).
See https://www.rodiumai.io/docs/models and GET /v1/models.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

# Static fallbacks ordered cheapest → stronger within each tier (docs samples + guides).
RODIUM_TIER_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Light chat / brainstorm / Q&A — prefer Google Flash Lite (lowest RODI in docs sample).
    "economy": (
        "google/gemini-3.1-flash-lite-preview",
        "anthropic/claude-haiku-4-5-20251001",
        "deepseek/deepseek-chat",
    ),
    # UX copy, creative briefs, structured product writing — mid cost / solid quality.
    "balanced": (
        "anthropic/claude-haiku-4-5-20251001",
        "google/gemini-2.5-flash",
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
    ),
    # Docs: coding agents → rodiumai/smart (router picks a strong coding model).
    "coding": (
        "rodiumai/smart",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
    ),
    # Hard reasoning / long architecture — pay for quality only when needed.
    "strong": (
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-opus-4-6",
    ),
    # Image guide: Gemini Flash Image / Imagen / gpt-image (multi-vendor).
    "image": (
        "google/gemini-3.1-flash-image",
        "google/imagen-4.0-generate-001",
        "openai/gpt-image-1",
    ),
}

DOMAIN_TO_TIER: dict[str, str] = {
    "text": "economy",
    "design": "balanced",
    "code": "coding",
    "image": "image",
}

# Legacy smart-profile aliases that 404 when empty on many accounts.
RODIUM_LEGACY_ALIASES: dict[str, str] = {
    "rodium/basic": "economy",
    "rodium/auto": "economy",
    "rodium/fast": "coding",
    "rodium/pro": "balanced",
    "auto": "economy",
    "smart": "coding",
    "rodium/smart": "coding",
}

_COMPLEX_HINTS = (
    "architecture",
    "architect",
    "prd",
    "spec détaillée",
    "detailed spec",
    "deep analysis",
    "analyse approfondie",
    "migrate",
    "security audit",
)

_catalogue_cache: dict[str, Any] = {"ts": 0.0, "models": None, "coding": None}
_CACHE_TTL_SEC = 300.0


def domain_tier(domain: str, *, message: str = "") -> str:
    """Map a task domain (+ optional message hints) to a cost/quality tier."""
    tier = DOMAIN_TO_TIER.get(domain, "economy")
    lower = message.lower()
    if tier == "economy" and any(h in lower for h in _COMPLEX_HINTS):
        return "strong"
    if tier == "balanced" and any(h in lower for h in ("architecture", "prd", "system design")):
        return "strong"
    return tier


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model_cost_score(item: dict[str, Any]) -> float:
    """Lower is cheaper. Prefer input+output token rates; else per_image."""
    pricing = item.get("rodiumai_pricing") or {}
    inp = _parse_price(pricing.get("input_per_1m"))
    out = _parse_price(pricing.get("output_per_1m"))
    if inp is not None or out is not None:
        return (inp or 0.0) + (out or 0.0)
    per_image = _parse_price(pricing.get("per_image"))
    if per_image is not None:
        return per_image * 1000.0
    return 1e18


def _is_available(item: dict[str, Any]) -> bool:
    status = str(item.get("rodiumai_status") or "available").lower()
    return status in {"available", "active", ""}


def _is_text_chat_model(item: dict[str, Any]) -> bool:
    caps = item.get("rodiumai_capabilities") or {}
    outputs = caps.get("output_modalities") or ["text"]
    return "text" in outputs


def _is_image_model(item: dict[str, Any]) -> bool:
    model_id = str(item.get("id") or "").lower()
    if any(tok in model_id for tok in ("image", "imagen", "gpt-image", "flux", "sdxl")):
        return True
    caps = item.get("rodiumai_capabilities") or {}
    outputs = caps.get("output_modalities") or []
    return "image" in outputs


def _fetch_json(url: str, *, api_key: str | None, timeout: float = 12.0) -> Any:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")  # nosec B310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def fetch_rodium_catalogue(
    *,
    base_url: str,
    api_key: str | None,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Return catalogue rows from GET /v1/models (cached briefly)."""
    now = time.monotonic()
    if (
        not force
        and _catalogue_cache["models"] is not None
        and now - float(_catalogue_cache["ts"]) < _CACHE_TTL_SEC
    ):
        return list(_catalogue_cache["models"] or [])

    root = base_url.rstrip("/")
    try:
        data = _fetch_json(f"{root}/models", api_key=api_key)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return list(_catalogue_cache["models"] or [])

    rows = [
        item
        for item in (data.get("data") if isinstance(data, dict) else [])
        if isinstance(item, dict) and item.get("id")
    ]
    _catalogue_cache["models"] = rows
    _catalogue_cache["ts"] = now
    return rows


def fetch_coding_catalogue(*, base_url: str, api_key: str | None = None) -> list[dict[str, Any]]:
    """GET /v1/models/coding (public) — models tagged for coding."""
    root = base_url.rstrip("/")
    try:
        # Public endpoint; key optional.
        data = _fetch_json(f"{root}/models/coding", api_key=api_key)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return []
    return [
        item
        for item in (data.get("data") if isinstance(data, dict) else [])
        if isinstance(item, dict) and item.get("id")
    ]


def _pick_cheapest(items: list[dict[str, Any]], *, predicate) -> str | None:
    eligible = [i for i in items if _is_available(i) and predicate(i)]
    if not eligible:
        return None
    eligible.sort(key=_model_cost_score)
    return str(eligible[0]["id"])


def pick_tier_model(
    tier: str,
    *,
    catalogue: list[dict[str, Any]] | None = None,
    coding_catalogue: list[dict[str, Any]] | None = None,
) -> str:
    """Choose a catalogue id for *tier*: live cheapest when possible, else static."""
    candidates = RODIUM_TIER_CANDIDATES.get(tier, RODIUM_TIER_CANDIDATES["economy"])
    rows = catalogue or []

    if tier == "coding":
        # Prefer smart router when present (docs coding recipe).
        ids = {str(i.get("id")) for i in (rows + (coding_catalogue or []))}
        if "rodiumai/smart" in ids or not rows:
            return "rodiumai/smart"
        coding_rows = coding_catalogue or [
            i for i in rows if "code" in str(i.get("rodiumai_description") or "").lower()
        ]
        picked = _pick_cheapest(coding_rows or rows, predicate=_is_text_chat_model)
        if picked:
            return picked
        return candidates[0]

    if tier == "image":
        picked = _pick_cheapest(rows, predicate=_is_image_model) if rows else None
        if picked:
            return picked
        return candidates[0]

    # economy / balanced / strong: cheapest available among preferred vendors first,
    # else global cheapest text model under a soft price ceiling for economy.
    if rows:
        available_ids = {str(i["id"]): i for i in rows if _is_available(i)}
        if tier != "strong":
            for cand in candidates:
                if cand in available_ids and _is_text_chat_model(available_ids[cand]):
                    return cand
        if tier == "economy":
            picked = _pick_cheapest(rows, predicate=_is_text_chat_model)
            if picked:
                return picked
        if tier in {"balanced", "strong"}:
            # Prefer higher quality: sort by quality tier then cost.
            text_rows = [i for i in rows if _is_available(i) and _is_text_chat_model(i)]
            quality_rank = {"max": 0, "high": 1, "pro": 1, "basic": 2, "fast": 3}

            def _quality_key(item: dict[str, Any]) -> tuple[int, float]:
                tier_meta = item.get("rodiumai_tier") or {}
                q = str(tier_meta.get("quality") or "basic").lower()
                return (quality_rank.get(q, 5), _model_cost_score(item))

            if text_rows:
                text_rows.sort(key=_quality_key)
                # balanced: mid pack; strong: best quality first
                if tier == "strong":
                    return str(text_rows[0]["id"])
                mid = text_rows[len(text_rows) // 3] if len(text_rows) > 3 else text_rows[0]
                return str(mid["id"])

    return candidates[0]


def resolve_rodium_model(
    domain: str,
    *,
    message: str = "",
    config_models: dict[str, Any] | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    use_live_catalogue: bool = True,
) -> str:
    """Resolve the best Rodium catalogue model for *domain* (multi-provider)."""
    configured = None
    if config_models and domain in config_models:
        configured = str(config_models[domain]).strip()

    # Explicit user override that is already a real catalogue id (provider/model).
    if configured and configured not in RODIUM_LEGACY_ALIASES and "/" in configured:
        if configured.startswith("rodium/") and configured not in {"rodiumai/smart"}:
            # Legacy profiles still need remapping.
            pass
        else:
            return configured

    tier = domain_tier(domain, message=message)
    if configured in RODIUM_LEGACY_ALIASES:
        tier = RODIUM_LEGACY_ALIASES[configured]

    catalogue: list[dict[str, Any]] = []
    coding: list[dict[str, Any]] = []
    if use_live_catalogue and base_url:
        catalogue = fetch_rodium_catalogue(base_url=base_url, api_key=api_key)
        if tier == "coding":
            coding = fetch_coding_catalogue(base_url=base_url, api_key=api_key)

    return pick_tier_model(tier, catalogue=catalogue, coding_catalogue=coding)


def default_rodium_models_map() -> dict[str, str]:
    """Static default domain → model map (no network)."""
    return {
        "text": pick_tier_model("economy"),
        "design": pick_tier_model("balanced"),
        "code": pick_tier_model("coding"),
        "image": pick_tier_model("image"),
    }
