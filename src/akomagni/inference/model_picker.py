"""Interactive Rodium model selection (Auto + catalogue)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from akomagni.inference.connect import save_config
from akomagni.inference.rodium_router import (
    RODIUM_TIER_CANDIDATES,
    fetch_rodium_catalogue,
    resolve_rodium_model,
)

AUTO_VALUE = "auto"

# Strong multi-vendor picks (not mini/lite) for pinned use.
RECOMMENDED_PINNED: tuple[tuple[str, str], ...] = (
    ("anthropic/claude-sonnet-4-6", "Claude Sonnet 4.6 — coding & product"),
    ("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro — reasoning"),
    ("openai/gpt-5.4", "GPT-5.4 — general strong"),
    ("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro — coding value"),
    ("anthropic/claude-opus-4-6", "Claude Opus 4.6 — hardest tasks"),
    ("openai/gpt-5.3-codex", "GPT-5.3 Codex — coding"),
    ("mistral/devstral-2-123b", "Devstral 2 — coding"),
    ("google/gemini-3.1-flash-image", "Gemini Flash Image — posters / ads"),
    ("google/gemini-3-pro-image", "Gemini Pro Image — high-end creatives"),
    ("openai/gpt-image-1.5", "GPT Image 1.5 — image / URL"),
)

PromptFn = Callable[[str], str]


def _is_image_model_id(model_id: str) -> bool:
    lower = model_id.lower()
    return any(tok in lower for tok in ("image", "imagen", "gpt-image", "flux", "sdxl"))


def _is_embedding_or_audio(model_id: str) -> bool:
    lower = model_id.lower()
    return any(
        tok in lower
        for tok in (
            "embedding",
            "transcribe",
            "tts",
            "realtime",
            "audio",
            "sora",
            "veo-",
            "voxtral",
        )
    )


def cloud_model_mode(config: dict[str, Any]) -> str:
    inf = config.get("inference") or {}
    mode = str(inf.get("cloud_model_mode") or "auto").lower()
    return "pinned" if mode == "pinned" else "auto"


def pinned_model(config: dict[str, Any]) -> str | None:
    inf = config.get("inference") or {}
    raw = inf.get("pinned_model")
    if raw and str(raw).strip() and str(raw).strip().lower() != AUTO_VALUE:
        return str(raw).strip()
    return None


def apply_model_choice(choice: str, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist Auto or a pinned catalogue id into config."""
    from akomagni.core.config import load_config

    cfg = dict(config or load_config())
    inference = dict(cfg.get("inference") or {})
    cleaned = (choice or AUTO_VALUE).strip()
    if cleaned.lower() == AUTO_VALUE or cleaned == "":
        inference["cloud_model_mode"] = "auto"
        inference["pinned_model"] = None
    else:
        inference["cloud_model_mode"] = "pinned"
        inference["pinned_model"] = cleaned
    cfg["inference"] = inference
    save_config(cfg)
    return cfg


def describe_model_selection(config: dict[str, Any]) -> str:
    if cloud_model_mode(config) == "pinned" and pinned_model(config):
        return f"Pinned · {pinned_model(config)}"
    return "Auto · best model per task"


def build_model_choices(
    *,
    catalogue: list[dict[str, Any]] | None = None,
) -> list[tuple[str, str]]:
    """Return (value, label) rows: Auto, recommended, then live catalogue."""
    rows: list[tuple[str, str]] = [
        (AUTO_VALUE, "Auto — pick by task (code / design / text / image)"),
    ]
    seen = {AUTO_VALUE}
    available_ids = {
        str(item.get("id"))
        for item in (catalogue or [])
        if isinstance(item, dict) and item.get("id")
    }

    for model_id, label in RECOMMENDED_PINNED:
        if available_ids and model_id not in available_ids:
            continue
        rows.append((model_id, label))
        seen.add(model_id)

    for item in catalogue or []:
        model_id = str(item.get("id") or "")
        if not model_id or model_id in seen or _is_embedding_or_audio(model_id):
            continue
        if model_id.startswith("rodium/") and model_id not in {"rodiumai/smart"}:
            continue
        status = str(item.get("rodiumai_status") or "available").lower()
        if status not in {"available", "active", ""}:
            continue
        name = str(item.get("name") or model_id)
        kind = "image" if _is_image_model_id(model_id) else "chat"
        rows.append((model_id, f"{name} · {kind}"))
        seen.add(model_id)
        if len(rows) >= 80:
            break

    # Ensure static quality image fallbacks appear even offline.
    if not catalogue:
        for model_id in RODIUM_TIER_CANDIDATES["image"][:4]:
            if model_id not in seen:
                rows.append((model_id, f"{model_id} · image"))
                seen.add(model_id)
    return rows


def resolve_session_cloud_model(
    domain: str,
    *,
    message: str = "",
    config: dict[str, Any],
    base_url: str | None = None,
    api_key: str | None = None,
) -> str:
    """Resolve model for this turn: pinned override or Auto router."""
    providers = config.get("providers") or {}
    rodium = providers.get("rodium") or {}
    models = rodium.get("models") if isinstance(rodium.get("models"), dict) else None

    pinned = pinned_model(config)
    if cloud_model_mode(config) == "pinned" and pinned:
        if domain == "image" and not _is_image_model_id(pinned):
            return resolve_rodium_model(
                "image",
                message=message,
                config_models=models,
                base_url=base_url,
                api_key=api_key,
                use_live_catalogue=bool(base_url),
            )
        return pinned

    return resolve_rodium_model(
        domain,
        message=message,
        config_models=models,
        base_url=base_url,
        api_key=api_key,
        use_live_catalogue=bool(base_url),
    )


def fetch_choices_for_config(config: dict[str, Any]) -> list[tuple[str, str]]:
    providers = config.get("providers") or {}
    rodium = providers.get("rodium") or {}
    base_url = str(rodium.get("base_url") or "https://api.rodiumai.io/v1")
    api_key = rodium.get("api_key")
    if isinstance(api_key, str):
        key = api_key
    else:
        import os

        key = os.environ.get(str(rodium.get("api_key_env") or "RODIUMAI_API_KEY"))
    try:
        catalogue = fetch_rodium_catalogue(base_url=base_url, api_key=key)
    except OSError:
        catalogue = []
    return build_model_choices(catalogue=catalogue)


def interactive_pick_model(
    *,
    choices: list[tuple[str, str]] | None = None,
    config: dict[str, Any] | None = None,
    prompt: PromptFn | None = None,
) -> str:
    """Show a dropdown-style list. Space or Enter confirms (questionary).

    Falls back to a numbered prompt when questionary/TTY is unavailable.
    """
    from akomagni.core.config import load_config

    cfg = config or load_config()
    options = choices or fetch_choices_for_config(cfg)
    current = pinned_model(cfg) if cloud_model_mode(cfg) == "pinned" else AUTO_VALUE
    default = current if any(v == current for v, _ in options) else AUTO_VALUE

    try:
        import questionary
        from questionary import Choice
    except ImportError:  # pragma: no cover - optional UI dep always installed in prod
        questionary = None  # type: ignore[assignment]
    else:  # pragma: no cover - requires interactive TTY
        q_choices = [Choice(title=label, value=value) for value, label in options]
        try:
            result = questionary.select(
                "Rodium model  (↑↓ move · Space/Enter confirm)",
                choices=q_choices,
                default=default,
                qmark="✦",
                pointer="›",
            ).ask()
        except Exception:
            result = None
        if result:
            apply_model_choice(str(result), config=cfg)
            return str(result)
        if result is None and prompt is None:
            return default

    # Numbered fallback (CI / non-TTY).
    ask = prompt or input
    print("Rodium models:")
    for idx, (value, label) in enumerate(options[:40], start=1):
        mark = "*" if value == default else " "
        print(f"  {mark} {idx}. {label}")
    raw = ask(f"Choose number [{default}]").strip()
    if not raw:
        apply_model_choice(default, config=cfg)
        return default
    if raw.lower() == AUTO_VALUE or raw == "0":
        apply_model_choice(AUTO_VALUE, config=cfg)
        return AUTO_VALUE
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(options):
            value = options[index][0]
            apply_model_choice(value, config=cfg)
            return value
    # Allow pasting a catalogue id directly.
    if "/" in raw:
        apply_model_choice(raw, config=cfg)
        return raw
    apply_model_choice(default, config=cfg)
    return default
