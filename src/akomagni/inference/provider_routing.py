"""Keep local / Hugging Face pull / Rodium / Foundry paths isolated.

Hugging Face is **not** an inference provider — ``akomagni connect hf`` only
stores a Hub token for ``akomagni model pull``. Inference backends are:

- ``local`` — llama-server GGUF (often pulled from HF)
- ``rodium`` — Rodium catalogue (``vendor/model`` ids)
- ``azure`` — Microsoft Foundry / Azure OpenAI deployment names
"""

from __future__ import annotations

from typing import Any


def is_rodium_catalogue_id(model: str | None) -> bool:
    """True for Rodium-style ids (``google/…``, ``openai/…``, ``rodium/…``)."""
    if not model:
        return False
    cleaned = str(model).strip()
    if not cleaned:
        return False
    low = cleaned.lower()
    if low.startswith(("rodium/", "rodiumai/")):
        return True
    return "/" in cleaned


def pick_fallback_model(provider: str, models: list[str] | None) -> str | None:
    """Pick a live ``/models`` id appropriate for *provider* (never cross-leak)."""
    rows = [str(m).strip() for m in (models or []) if str(m).strip()]
    if not rows:
        return None
    name = (provider or "local").strip().lower()
    if name == "rodium":
        return next(
            (m for m in rows if "/" in m and not m.startswith("rodium/")),
            rows[0],
        )
    if name == "azure":
        # Foundry deployments are usually bare names (gpt-4o), never google/…
        bare = next((m for m in rows if not is_rodium_catalogue_id(m)), None)
        return bare or rows[0]
    return rows[0]


def image_hint_for_provider(provider: str) -> str:
    """User-facing recovery text when image generation fails."""
    name = (provider or "").strip().lower()
    if name == "azure":
        return (
            "Image generation failed on Foundry — no working image deployment.\n"
            "Create/deploy gpt-image-1 or dall-e-3 on the resource, then:\n"
            "  akomagni connect foundry <url>\n"
            "Docs: https://learn.microsoft.com/azure/ai-services/openai/how-to/dall-e"
        )
    if name == "rodium":
        return (
            "Image generation failed after trying catalogue image models.\n"
            "Check RODI credits / model access "
            "(https://www.rodiumai.io/docs/guides/image-generation)."
        )
    if name == "local":
        return (
            "Local GGUF chat cannot generate images. Use Foundry with an image deployment "
            "or Rodium catalogue models:\n"
            "  akomagni connect foundry <url>\n"
            "  akomagni connect rodium"
        )
    return f"Image generation is not supported for provider={name or 'unknown'}."


def assert_model_fits_provider(provider: str, model: str | None) -> str | None:
    """Return *model* if it fits *provider*, else ``None`` (drop cross-provider ids)."""
    if not model or not str(model).strip():
        return None
    cleaned = str(model).strip()
    name = (provider or "local").strip().lower()
    if name == "azure" and is_rodium_catalogue_id(cleaned):
        return None
    if name == "rodium" and cleaned and not is_rodium_catalogue_id(cleaned):
        # Bare deployment names can still work on Rodium if listed; allow them.
        return cleaned
    return cleaned


def provider_label(provider: str) -> str:
    name = (provider or "local").strip().lower()
    return {
        "local": "local (GGUF / llama-server)",
        "rodium": "Rodium AI",
        "azure": "Microsoft Foundry",
        "hf": "Hugging Face Hub (model pull only)",
        "huggingface": "Hugging Face Hub (model pull only)",
    }.get(name, name)


def summarize_endpoint(endpoint: Any) -> str:
    """One-line debug string for CLI status banners."""
    provider = getattr(endpoint, "provider", "local")
    base = getattr(endpoint, "base_url", "")
    return f"{provider_label(provider)} → {base}"
