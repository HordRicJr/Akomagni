# Getting started

## Prerequisites

- Python 3.11+
- 8 GB RAM minimum (16 GB+ recommended)
- Git

## Install

One-liner (recommended): see [Install guide](https://hordricjr.github.io/Akomagni/install/).

Development:

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## First run

CLI language defaults to **English**. Switch later with `akomagni config language fr`.

```bash
akomagni config init
akomagni doctor
akomagni connect              # local GGUF, Rodium, or Foundry
akomagni skill link           # register BMAD skills
akomagni run cli --project ./my-app
```

## Try Akomagni Flow

```bash
akomagni flow route "I have an idea for a budget app"
akomagni flow invoke "I have an idea for a budget app"
akomagni flow status
akomagni skill list
akomagni model recommend
```

## Image / poster (cloud)

With Rodium connected, ask for an affiche/poster in `akomagni run cli`. Auto Router tries
URL-capable image models first, then Gemini image models. If the API returns base64 only,
Akomagni saves a PNG under `~/.local/share/akomagni/generated-images/` (Windows:
`%LOCALAPPDATA%\akomagni\generated-images\`) and prints the path.

## Next steps

- [Architecture](architecture.md)
- [Akomagni Flow](akomagni-flow.md)
- [Contributing](../../CONTRIBUTING.md)
