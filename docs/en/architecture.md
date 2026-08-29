# Architecture

## Overview

Akomagni is a **local AI workstation** composed of layered modules sharing a single Python package.

```
User (CLI / Agent / IDE)
        │
        ▼
┌───────────────────────────────────────┐
│  Akomagni Flow (orchestrator)         │
│  intent → agent → BMAD skill          │
└───────────────┬───────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│ Memory │ │ Router  │ │ Inference│
│ inject │ │ models  │ │ :8787    │
└────────┘ └─────────┘ └──────────┘
```

## Modules

| Module | Path | Responsibility |
|--------|------|----------------|
| CLI | `src/akomagni/cli/` | Typer entrypoint |
| Core | `src/akomagni/core/` | Config, doctor, model router |
| Flow | `src/akomagni/flow/` | Akomagni Flow orchestration |
| Memory | `src/akomagni/memory/` | Akomagni Memory store + inject |
| Inference | `src/akomagni/inference/` | llama.cpp OpenAI-compatible API |

## Data directories

| Path | Scope |
|------|-------|
| `~/.akomagni/config.yaml` | Global config |
| `~/.akomagni/memory/` | Central memory (all projects) |
| `~/.akomagni/models/` | Downloaded GGUF models |
| `./.akomagni/memory/` | Project memory (Git-friendly) |
| `./.akomagni/workflow/` | Flow state, brainstorm memlogs |

## Design principles

1. **Local first** — no cloud dependency for core features
2. **BMAD as orchestration layer** — do not rewrite 17 agents
3. **Vertical slices** — ship end-to-end features incrementally
4. **Three modes, one core** — CLI, Agent, IDE share the same backend

## v0.1 vs roadmap

| Component | v0.1 | v0.2+ |
|-----------|------|-------|
| Doctor | ✅ | GPU backends |
| Flow | Heuristic router | ML router + skill invoke |
| Inference | Stub | llama-server |
| Memory | Scaffold | Auto-capture |
| RAG | — | sqlite-vec |
| IDE | — | VS Code fork |
