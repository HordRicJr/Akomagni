# Démarrage rapide

Installer Akomagni, connecter un provider, lier les skills, lancer la CLI.

## Prérequis

- Python 3.11+
- 8 Go RAM minimum
- Git

## Installation

```bash
# macOS / Linux
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Guide : [Install](https://hordricjr.github.io/Akomagni/install/)

## Premières commandes

La CLI est en **anglais** par défaut.

```bash
akomagni connect
akomagni skill link
akomagni run cli --project ./mon-app

# optionnel
akomagni config language fr
```

## Modèles locaux (optionnel)

```bash
akomagni config extras inference
akomagni model pull qwen2.5-coder-7b
akomagni serve --model qwen2.5-coder-7b
```

## Suite

- [Akomagni Flow](akomagni-flow.md)
- [Architecture](architecture.md)
- [Contribuer](../../CONTRIBUTING.fr.md)
