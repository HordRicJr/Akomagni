"""Domain → GGUF model mapping and hot-swap planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from akomagni.core.registry.catalog import resolve_catalog_name
from akomagni.core.router.domain import DomainClassification, ModelDomain, classify_domain
from akomagni.inference.client import InferenceStatus
from akomagni.inference.llama import resolve_model_path


@dataclass(frozen=True)
class DomainModelPlan:
    classification: DomainClassification
    catalog_name: str | None
    model_path: Path | None
    model_id: str | None
    skip_inference: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ModelSwapPlan:
    needs_swap: bool
    current_model: str | None
    target_model: str | None
    target_path: Path | None
    hint: str = ""


def default_domain_catalog(domain: ModelDomain, config: dict) -> str | None:
    """Resolve configured catalog name for *domain*."""
    router = config.get("router") or {}
    domains = router.get("domains") or {}
    value = domains.get(domain.value)
    if value is None or str(value).strip().lower() in {"", "none", "null"}:
        return None
    return str(value).strip()


def resolve_domain_model(
    message: str,
    *,
    config: dict,
    models_dir: Path,
) -> DomainModelPlan:
    """Classify message and resolve a local GGUF model for inference."""
    classification = classify_domain(message)
    if classification.domain is ModelDomain.IMAGE:
        return DomainModelPlan(
            classification=classification,
            catalog_name=None,
            model_path=None,
            model_id=None,
            skip_inference=True,
            reason="image domain uses a separate pipeline (not text GGUF)",
        )

    catalog_name = default_domain_catalog(classification.domain, config)
    if not catalog_name:
        fallback = (config.get("inference") or {}).get("default_model")
        catalog_name = str(fallback) if fallback else None

    if not catalog_name:
        return DomainModelPlan(
            classification=classification,
            catalog_name=None,
            model_path=None,
            model_id=None,
            reason="no catalog mapping for domain",
        )

    entry = resolve_catalog_name(catalog_name)
    resolved_name = entry.name if entry else catalog_name
    model_path = resolve_model_path(resolved_name, models_dir=models_dir)
    if model_path is None and entry:
        model_path = resolve_model_path(entry.filename, models_dir=models_dir)

    model_id = model_path.name if model_path else resolved_name
    return DomainModelPlan(
        classification=classification,
        catalog_name=resolved_name,
        model_path=model_path,
        model_id=model_id,
        reason=f"domain={classification.domain.value}",
    )


def _normalize_model_name(value: str) -> str:
    return Path(value).name.lower().removesuffix(".gguf")


def models_match(current: str | None, target: str | None) -> bool:
    """Return whether *current* loaded model matches *target*."""
    if not current or not target:
        return False
    left = _normalize_model_name(current)
    right = _normalize_model_name(target)
    return left == right or left in right or right in left


def plan_model_swap(
    *,
    status: InferenceStatus,
    target_path: Path | None,
    target_model_id: str | None,
) -> ModelSwapPlan:
    """Compare running inference worker with the desired domain model."""
    current = status.models[0] if status.models else None
    target = target_model_id or (target_path.name if target_path else None)
    if not status.online:
        return ModelSwapPlan(
            needs_swap=False,
            current_model=current,
            target_model=target,
            target_path=target_path,
            hint="Inference offline — run: akomagni serve",
        )
    if target_path is None:
        return ModelSwapPlan(
            needs_swap=False,
            current_model=current,
            target_model=target,
            target_path=None,
            hint="Target model not downloaded — run: akomagni model pull <name>",
        )
    if models_match(current, target):
        return ModelSwapPlan(
            needs_swap=False,
            current_model=current,
            target_model=target,
            target_path=target_path,
            hint="Model already loaded",
        )
    return ModelSwapPlan(
        needs_swap=True,
        current_model=current,
        target_model=target,
        target_path=target_path,
        hint=(
            f"Hot-swap required: loaded `{current}` → `{target}`. "
            f"Run: akomagni inference swap {target_path.stem}"
        ),
    )
