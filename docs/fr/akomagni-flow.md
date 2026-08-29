# Akomagni Flow

Akomagni Flow route automatiquement les messages vers le bon **agent BMAD** et **skill** — pas de commandes `/`.

## Fonctionnement

```
Message utilisateur
     │
     ▼
Classifieur d'intent (heuristique v0.1 → router ML v0.3)
     │
     ▼
Gates workflow (brainstorm obligatoire greenfield)
     │
     ▼
Activation agent (persona + injection mémoire)
     │
     ▼
Dispatch skill (bmad-brainstorming, bmad-prd, …)
```

## 17 agents BMAD

| Module | Agents |
|--------|--------|
| BMad Method | Mary, John, Sally, Winston, Amelia |
| CIS | Carson, Victor, Maya, Dr. Quinn, Sophia, Caravaggio |
| GDS | Samus, Cloud Dragonborn, Link, Indie, Paige |
| TEA | Murat |

Découverte via `~/.akomagni/skills/**/customize.toml`.

## Gate brainstorm (obligatoire)

Sur toute **nouvelle idée** (greenfield, pas de memlog brainstorm terminé) :

1. Flow intercepte avant tout autre skill
2. Route vers Mary/Carson (`bmad-brainstorming`) ou Samus (jeux)
3. Débloque quand `status: complete` dans le memlog

## CLI

```bash
akomagni flow route "design une landing page"
# 🎨 Sally · UX Design → bmad-ux
```

## Fichier d'état

`./.akomagni/workflow/state.yaml` — phase, agent actif, skills complétés.
