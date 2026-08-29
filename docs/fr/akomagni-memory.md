# Akomagni Memory

Mémoire locale persistante injectée à chaque session agent — **pas du fine-tuning**.

## Deux niveaux

| Niveau | Chemin | Portée |
|--------|--------|--------|
| **Centrale** | `~/.akomagni/memory/` | Tous projets, toutes sessions |
| **Projet** | `./.akomagni/memory/` | Ce repo (versionnable Git) |

## Structure mémoire centrale

```
~/.akomagni/memory/
├── profile.md
├── preferences.yaml
├── stacks/
│   ├── web.md
│   ├── backend.md
│   └── design.md
├── habits.md
└── learnings/
```

## Mémoire projet

Décisions, conventions, glossaire du projet courant. Commit `./.akomagni/memory/` si pertinent.

## CLI

```bash
akomagni memory status
akomagni config init
```

## Règle de fusion

En cas de conflit, la **mémoire projet** prime sur la centrale.

## v0.2+

- `memory add --global` / `memory promote`
- Capture auto avec approbation
- Alimente Akomagni Train (LoRA)
