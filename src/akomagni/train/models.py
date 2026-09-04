"""Map Akomagni GGUF catalog names to Hugging Face Transformers IDs for training."""

from __future__ import annotations

from akomagni.core.registry.catalog import resolve_catalog_name
from akomagni.train.lora import TrainError

# Catalog entries are GGUF-only; training needs the Transformers weights.
TRAIN_HF_MODELS: dict[str, str] = {
    "phi-3.5-mini": "microsoft/Phi-3.5-mini-instruct",
    "llama-3.2-3b": "meta-llama/Llama-3.2-3B-Instruct",
    "qwen2.5-coder-7b": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "llama-3.1-8b": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}

# Models that typically need a GPU for practical fine-tuning.
_GPU_RECOMMENDED: frozenset[str] = frozenset({"qwen2.5-coder-7b", "llama-3.1-8b"})


def resolve_hf_train_model(name: str) -> str:
    """Resolve a catalog name (or HF id) to a Transformers repo id."""
    raw = name.strip()
    if not raw:
        raise TrainError("Base model name is empty.")

    key = raw.lower().replace("_", "-")
    entry = resolve_catalog_name(raw)
    if entry is not None:
        key = entry.name

    if key in TRAIN_HF_MODELS:
        return TRAIN_HF_MODELS[key]

    # Allow passing a full HF id directly (org/name).
    if "/" in raw and not raw.lower().endswith(".gguf"):
        return raw

    known = ", ".join(sorted(TRAIN_HF_MODELS))
    raise TrainError(
        f"No Transformers base mapping for '{name}'. "
        f"Use a catalog model ({known}) or pass an HF repo id like org/model."
    )


def requires_gpu(catalog_name: str) -> bool:
    """Return True when the catalog model is too large for practical CPU training."""
    entry = resolve_catalog_name(catalog_name)
    key = entry.name if entry else catalog_name.strip().lower().replace("_", "-")
    return key in _GPU_RECOMMENDED
