# Architecture

## Vue d'ensemble

Akomagni est un **poste de travail IA local** en modules partageant un package Python unique.

```
Utilisateur (CLI / Agent / IDE)
        │
        ▼
┌───────────────────────────────────────┐
│  Akomagni Flow (orchestrateur)        │
│  intent → agent → skill BMAD          │
└───────────────┬───────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│ Memory │ │ Router  │ │ Inference│
│ inject │ │ modèles │ │ :8787    │
└────────┘ └─────────┘ └──────────┘
```

## Modules

| Module | Chemin | Rôle |
|--------|--------|------|
| CLI | `src/akomagni/cli/` | Point d'entrée Typer |
| Core | `src/akomagni/core/` | Config, doctor, router |
| Flow | `src/akomagni/flow/` | Orchestration Akomagni Flow |
| Memory | `src/akomagni/memory/` | Akomagni Memory |
| Inference | `src/akomagni/inference/` | API llama.cpp |

## Répertoires de données

| Chemin | Portée |
|--------|--------|
| `~/.akomagni/config.yaml` | Config globale |
| `~/.akomagni/memory/` | Mémoire centrale |
| `~/.akomagni/models/` | Modèles GGUF |
| `./.akomagni/memory/` | Mémoire projet |
| `./.akomagni/workflow/` | État Flow, memlogs brainstorm |

## Principes

1. **Local d'abord** — pas de cloud obligatoire
2. **BMAD = couche orchestration** — ne pas réécrire les 17 agents
3. **Tranches verticales** — livrer bout-en-bout par étapes
4. **3 modes, un core** — CLI, Agent, IDE partagent le backend
