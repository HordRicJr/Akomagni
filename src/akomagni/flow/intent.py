"""Heuristic intent classification (v0.1 — remplacé par modèle routeur ensuite)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    agent_id: str
    skill: str
    confidence: float
    badge: str
    hint: str
    greenfield: bool = False


GAME_PATTERNS = re.compile(
    r"\b(jeu|game|gdd|gameplay|unity|godot|unreal|niveau|level design)\b",
    re.IGNORECASE,
)
TEST_PATTERNS = re.compile(r"\b(test|qa|e2e|ci|couverture|flaky|pytest)\b", re.IGNORECASE)
PITCH_PATTERNS = re.compile(r"\b(pitch|deck|slides|présentation|youtube|keynote)\b", re.IGNORECASE)
STORY_PATTERNS = re.compile(r"\b(post|article|linkedin|histoire|narration|rédige)\b", re.IGNORECASE)
DESIGN_PATTERNS = re.compile(r"\b(design|ux|ui|maquette|figma|wireframe|css|tailwind)\b", re.IGNORECASE)
ARCH_PATTERNS = re.compile(r"\b(architect|architecture|infra|scalabilité)\b", re.IGNORECASE)
PRD_PATTERNS = re.compile(r"\b(prd|spec|epic|story|backlog|requirements)\b", re.IGNORECASE)
DEV_PATTERNS = re.compile(r"\b(implémente|code|bug|fix|refactor|api|commit)\b", re.IGNORECASE)
BRAINSTORM_PATTERNS = re.compile(
    r"\b(idée|brainstorm|créer un|nouveau projet|pivot|comment faire)\b",
    re.IGNORECASE,
)
INNOVATION_PATTERNS = re.compile(r"\b(innovation|disruption|business model|blue ocean)\b", re.IGNORECASE)
PROBLEM_PATTERNS = re.compile(r"\b(problème complexe|root cause|triz|bloqué)\b", re.IGNORECASE)
IMAGE_PATTERNS = re.compile(r"\b(logo|image|illustration|génère.*visuel|sdxl|flux)\b", re.IGNORECASE)


def _badge(agent_id: str, skill_label: str) -> str:
    from akomagni.flow.catalog import AGENT_BY_ID

    agent = AGENT_BY_ID.get(agent_id)
    if not agent:
        return f"✨ Akomagni · {skill_label}"
    return f"{agent.icon} {agent.name} · {skill_label}"


def classify_message(message: str, *, greenfield: bool = False) -> RouteDecision:
    text = message.strip()
    lower = text.lower()

    if IMAGE_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="akomagni",
            skill="image-pipeline",
            confidence=0.75,
            badge="✨ Akomagni · Image",
            hint="Route image (SDXL/Flux) — pipeline à brancher sur inference.",
        )

    if GAME_PATTERNS.search(lower):
        if BRAINSTORM_PATTERNS.search(lower) or greenfield:
            return RouteDecision(
                agent_id="gds-agent-game-designer",
                skill="gds-brainstorm-game",
                confidence=0.9,
                badge=_badge("gds-agent-game-designer", "Brainstorm jeu"),
                hint="Gate greenfield : brainstorm jeu obligatoire avant GDD.",
                greenfield=True,
            )
        if PRD_PATTERNS.search(lower) or "gdd" in lower:
            return RouteDecision(
                agent_id="gds-agent-game-designer",
                skill="gds-gdd",
                confidence=0.85,
                badge=_badge("gds-agent-game-designer", "GDD"),
                hint="Vérifie qu'un brainstorm jeu est terminé.",
            )
        return RouteDecision(
            agent_id="gds-agent-game-dev",
            skill="gds-quick-dev",
            confidence=0.7,
            badge=_badge("gds-agent-game-dev", "Dev jeu"),
            hint="Implémentation jeu via Link Freeman.",
        )

    if TEST_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-tea",
            skill="bmad-testarch-automate",
            confidence=0.8,
            badge=_badge("bmad-tea", "Tests"),
            hint="Murat — stratégie et automatisation des tests.",
        )

    if PITCH_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-cis-agent-presentation-master",
            skill="presentation-deck",
            confidence=0.85,
            badge=_badge("bmad-cis-agent-presentation-master", "Présentation"),
            hint="Caravaggio — deck, pitch ou visuel.",
        )

    if INNOVATION_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-cis-agent-innovation-strategist",
            skill="bmad-cis-innovation-strategy",
            confidence=0.85,
            badge=_badge("bmad-cis-agent-innovation-strategist", "Innovation"),
            hint="Victor — stratégie de disruption.",
        )

    if PROBLEM_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-cis-agent-creative-problem-solver",
            skill="bmad-cis-problem-solving",
            confidence=0.8,
            badge=_badge("bmad-cis-agent-creative-problem-solver", "Problem solving"),
            hint="Dr. Quinn — résolution systémique.",
        )

    if STORY_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-cis-agent-storyteller",
            skill="bmad-cis-storytelling",
            confidence=0.85,
            badge=_badge("bmad-cis-agent-storyteller", "Storytelling"),
            hint="Sophia — rédaction et narration.",
        )

    if BRAINSTORM_PATTERNS.search(lower) or greenfield:
        host = (
            "bmad-cis-agent-brainstorming-coach"
            if "créatif" in lower or "wild" in lower
            else "bmad-agent-analyst"
        )
        skill_label = "Brainstorming"
        return RouteDecision(
            agent_id=host,
            skill="bmad-brainstorming",
            confidence=0.92,
            badge=_badge(host, skill_label),
            hint="Akomagni Flow : brainstorm obligatoire sur nouvelle idée (greenfield).",
            greenfield=True,
        )

    if DESIGN_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-agent-ux-designer",
            skill="bmad-ux",
            confidence=0.85,
            badge=_badge("bmad-agent-ux-designer", "UX Design"),
            hint="Sally — design UI/UX ; PRD recommandé si absent.",
        )

    if ARCH_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-agent-architect",
            skill="bmad-architecture",
            confidence=0.85,
            badge=_badge("bmad-agent-architect", "Architecture"),
            hint="Winston — architecture ; PRD requis.",
        )

    if PRD_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-agent-pm",
            skill="bmad-prd",
            confidence=0.85,
            badge=_badge("bmad-agent-pm", "PRD"),
            hint="John — PRD ; brainstorm ou brief recommandé en amont.",
        )

    if DEV_PATTERNS.search(lower):
        return RouteDecision(
            agent_id="bmad-agent-dev",
            skill="bmad-build",
            confidence=0.8,
            badge=_badge("bmad-agent-dev", "Build"),
            hint="Amelia — implémentation ; story + sprint-status requis.",
        )

    return RouteDecision(
        agent_id="akomagni",
        skill="chat",
        confidence=0.5,
        badge="✨ Akomagni · Général",
        hint="Aucun agent BMAD spécifique — chat libre ou précise ton intent.",
    )
