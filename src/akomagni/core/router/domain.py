"""Heuristic domain classification for model routing (v0.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

IMAGE_PATTERNS = re.compile(
    r"\b(logo|image|illustration|visuel|affiche|poster|banner|flyer|"
    r"sdxl|flux|dall[\s-]?e|midjourney|icon)\b",
    re.IGNORECASE,
)
DESIGN_PATTERNS = re.compile(
    r"\b(design|ux|ui|maquette|figma|wireframe|css|tailwind|landing page)\b",
    re.IGNORECASE,
)
CODE_PATTERNS = re.compile(
    r"\b(implémente|code|bug|fix|refactor|api|commit|endpoint|jwt|pytest|typescript|python)\b",
    re.IGNORECASE,
)


class ModelDomain(StrEnum):
    CODE = "code"
    DESIGN = "design"
    IMAGE = "image"
    TEXT = "text"


@dataclass(frozen=True)
class DomainClassification:
    domain: ModelDomain
    confidence: float
    reason: str


def classify_domain(message: str) -> DomainClassification:
    """Classify *message* into code/design/image/text for model routing."""
    lower = message.strip().lower()
    if not lower:
        return DomainClassification(ModelDomain.TEXT, 0.5, "empty message")

    if IMAGE_PATTERNS.search(lower):
        return DomainClassification(ModelDomain.IMAGE, 0.85, "image generation keywords")

    if CODE_PATTERNS.search(lower):
        return DomainClassification(ModelDomain.CODE, 0.85, "implementation keywords")

    if DESIGN_PATTERNS.search(lower):
        return DomainClassification(ModelDomain.DESIGN, 0.8, "design/UX keywords")

    return DomainClassification(ModelDomain.TEXT, 0.6, "general text/chat")
