"""Hugging Face GGUF model catalog for akomagni model pull."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCatalogEntry:
    """A downloadable GGUF model entry."""

    name: str
    repo_id: str
    filename: str
    profile: str
    description: str = ""


CATALOG: dict[str, ModelCatalogEntry] = {
    "phi-3.5-mini": ModelCatalogEntry(
        name="phi-3.5-mini",
        repo_id="bartowski/Phi-3.5-mini-instruct-GGUF",
        filename="Phi-3.5-mini-instruct-Q4_K_M.gguf",
        profile="light",
        description="Phi-3.5 Mini Instruct Q4_K_M — léger, rapide CPU/GPU",
    ),
    "llama-3.2-3b": ModelCatalogEntry(
        name="llama-3.2-3b",
        repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
        filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        profile="light",
        description="Llama 3.2 3B Instruct Q4_K_M",
    ),
    "qwen2.5-coder-7b": ModelCatalogEntry(
        name="qwen2.5-coder-7b",
        repo_id="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        filename="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        profile="standard",
        description="Qwen 2.5 Coder 7B — excellent pour le code",
    ),
    "llama-3.1-8b": ModelCatalogEntry(
        name="llama-3.1-8b",
        repo_id="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        filename="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        profile="standard",
        description="Llama 3.1 8B Instruct Q4_K_M",
    ),
}


def resolve_catalog_name(name: str) -> ModelCatalogEntry | None:
    """Resolve a catalog name (case-insensitive, aliases)."""
    key = name.strip().lower().replace("_", "-")
    if key in CATALOG:
        return CATALOG[key]
    aliases = {
        "phi-3.5-mini": "phi-3.5-mini",
        "phi-3.5": "phi-3.5-mini",
        "qwen2.5-coder-7b": "qwen2.5-coder-7b",
        "qwen-coder-7b": "qwen2.5-coder-7b",
        "llama-3.2-3b": "llama-3.2-3b",
        "llama-3.1-8b": "llama-3.1-8b",
    }
    resolved = aliases.get(key)
    if resolved:
        return CATALOG[resolved]
    for entry in CATALOG.values():
        if entry.name == key:
            return entry
    return None


def list_catalog() -> list[ModelCatalogEntry]:
    return list(CATALOG.values())
