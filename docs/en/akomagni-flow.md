# Akomagni Flow

Akomagni Flow automatically routes user messages to the right **BMAD agent** and **skill** — no slash commands required.

## How it works

```
User message
     │
     ▼
Intent classifier (heuristic v0.1 → ML router v0.3)
     │
     ▼
Workflow gates (brainstorm mandatory on greenfield)
     │
     ▼
Agent activation (persona + memory inject)
     │
     ▼
Skill dispatch (bmad-brainstorming, bmad-prd, …)
```

## 17 BMAD agents

| Module | Agents |
|--------|--------|
| BMad Method | Mary, John, Sally, Winston, Amelia |
| CIS | Carson, Victor, Maya, Dr. Quinn, Sophia, Caravaggio |
| Game Dev Studio | Samus, Cloud Dragonborn, Link, Indie, Paige |
| Test Architecture | Murat |

Agents are discovered from `~/.akomagni/skills/**/customize.toml`.

## Brainstorm gate (mandatory)

On **greenfield** ideas (new project, no completed brainstorm memlog):

1. Flow intercepts before any other skill
2. Routes to Mary or Carson (`bmad-brainstorming`) or Samus for games
3. Unlocks when memlog `status: complete`

## CLI

```bash
akomagni flow route "design a landing page"
# 🎨 Sally · UX Design → bmad-ux
```

## Override (power users)

```bash
# Planned: @john, @amelia in chat
akomagni flow route "implement auth"  # auto → Amelia
```

## State file

`./.akomagni/workflow/state.yaml` tracks phase, active agent, completed skills.
