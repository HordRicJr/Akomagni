# Akomagni Memory

Persistent local memory injected into every agent session — **not fine-tuning**.

## Two levels

| Level | Path | Scope |
|-------|------|-------|
| **Central** | `~/.akomagni/memory/` | All projects, all sessions |
| **Project** | `./.akomagni/memory/` | Current repo only (Git-friendly) |

## Central memory layout

```
~/.akomagni/memory/
├── profile.md           # Who you are
├── preferences.yaml     # Style, language
├── stacks/
│   ├── web.md
│   ├── backend.md
│   └── design.md
├── habits.md
└── learnings/
```

## Project memory

Store decisions, conventions, glossary for the current project. Commit `./.akomagni/memory/` to Git when appropriate.

## CLI

```bash
akomagni memory status
akomagni config init   # scaffolds central memory
```

## Merge rule

On conflict, **project memory wins** over central memory.

## v0.2+

- `memory add --global` / `memory promote`
- Auto-capture with user approval
- Feeds Akomagni Train (LoRA) dataset
