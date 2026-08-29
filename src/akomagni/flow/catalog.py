"""Built-in agent registry for Akomagni Flow (v0.1 heuristic router)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    name: str
    icon: str
    module: str  # bmm | cis | gds | tea


AGENTS: tuple[AgentDef, ...] = (
    # BMad Method
    AgentDef("bmad-agent-analyst", "Mary", "📊", "bmm"),
    AgentDef("bmad-agent-pm", "John", "📋", "bmm"),
    AgentDef("bmad-agent-ux-designer", "Sally", "🎨", "bmm"),
    AgentDef("bmad-agent-architect", "Winston", "🏗️", "bmm"),
    AgentDef("bmad-agent-dev", "Amelia", "💻", "bmm"),
    # CIS
    AgentDef("bmad-cis-agent-brainstorming-coach", "Carson", "🧠", "cis"),
    AgentDef("bmad-cis-agent-innovation-strategist", "Victor", "⚡", "cis"),
    AgentDef("bmad-cis-agent-design-thinking-coach", "Maya", "🎨", "cis"),
    AgentDef("bmad-cis-agent-creative-problem-solver", "Dr. Quinn", "🔬", "cis"),
    AgentDef("bmad-cis-agent-storyteller", "Sophia", "📖", "cis"),
    AgentDef("bmad-cis-agent-presentation-master", "Caravaggio", "🎬", "cis"),
    # GDS
    AgentDef("gds-agent-game-designer", "Samus Shepard", "🎲", "gds"),
    AgentDef("gds-agent-game-architect", "Cloud Dragonborn", "🏛️", "gds"),
    AgentDef("gds-agent-game-dev", "Link Freeman", "🕹️", "gds"),
    AgentDef("gds-agent-game-solo-dev", "Indie", "🎮", "gds"),
    AgentDef("gds-agent-tech-writer", "Paige", "📚", "gds"),
    # TEA
    AgentDef("bmad-tea", "Murat", "🧪", "tea"),
)

AGENT_BY_ID = {a.agent_id: a for a in AGENTS}
