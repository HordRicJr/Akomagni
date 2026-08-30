"""Model domain router (code, design, image, text)."""

from akomagni.core.router.domain import DomainClassification, ModelDomain, classify_domain
from akomagni.core.router.swap import (
    DomainModelPlan,
    ModelSwapPlan,
    plan_model_swap,
    resolve_domain_model,
)

__all__ = [
    "DomainClassification",
    "DomainModelPlan",
    "ModelDomain",
    "ModelSwapPlan",
    "classify_domain",
    "plan_model_swap",
    "resolve_domain_model",
]
