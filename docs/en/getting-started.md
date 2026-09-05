# Getting started

Install Akomagni, connect a provider, and run the CLI. BMAD skills are installed with the kernel automatically.

## Requirements

- Python 3.11+
- 8 GB RAM minimum
- Git

## Install

```bash
# macOS / Linux
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Full guide: [Install](https://hordricjr.github.io/Akomagni/install/)

## First commands

CLI language is **English** by default.

```bash
akomagni connect
akomagni skill list
akomagni run cli --project ./my-app

# optional
akomagni config language fr
```

## Local models (optional)

```bash
akomagni config extras inference
akomagni model pull qwen2.5-coder-7b
akomagni serve --model qwen2.5-coder-7b
```

## Next

- [Akomagni Flow](akomagni-flow.md)
- [Architecture](architecture.md)
- [Contributing](../../CONTRIBUTING.md)
