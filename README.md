# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI Quality](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml)
[![CI Test](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml)
[![CI Security](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml)

**Akomagni: a new way to work with AI.** An open-source hybrid workstation that turns intent into workflows with models, agents, skills, memory, and tools.

[Français](README.fr.md) · [Site](https://hordricjr.github.io/Akomagni/) · [Install](https://hordricjr.github.io/Akomagni/install/) · [Tools hub](https://hordricjr.github.io/Akomagni/tools/) · [Documentation](docs/README.md) · [Roadmap](ROADMAP.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

---

## Why Akomagni?

Cloud AI tools are powerful but costly, privacy-invasive, and dev-centric. Local tools are often fragmented. **Akomagni** combines:

| Pillar | What it does |
|--------|----------------|
| **Local + cloud** | Hugging Face GGUF offline, or Rodium / Microsoft Foundry APIs |
| **Akomagni Flow** | Auto-routes to 17 BMAD agents: no slash commands |
| **Akomagni Memory** | Central + per-project memory, Git-friendly |
| **Auto Router** | Picks the right model per task (code, design, text) and saves tokens on Rodium |
| **Three modes** | CLI, Agent, IDE (VS Code extension + MCP today) |

> Not a chatbot wrap. A **multi-domain workstation** with structured BMAD workflows.

## Quick start

### Requirements

- Python **3.11+**
- **8 GB RAM** minimum (16 GB+ recommended)
- Windows, Linux, or macOS

### Install (development)

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
akomagni config init
akomagni doctor
```

### One-liner install

```bash
# Linux / macOS
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Full guide: [hordricjr.github.io/Akomagni/install/](https://hordricjr.github.io/Akomagni/install/)

## Commands

```bash
akomagni doctor                    # Scan hardware + recommend profile
akomagni connect                   # One wizard: local / Rodium / Foundry + Hugging Face token
akomagni skill link                # Register BMAD skills (auto-detect or pass a folder)
akomagni run cli --project ./app   # Chat + Flow; pick provider on first session
akomagni config init               # Create ~/.akomagni/config.yaml
akomagni update                    # Pull latest + reinstall CLI
akomagni config language fr        # French CLI (en/fr)
akomagni memory status             # Central + project memory
akomagni flow route "your message" # Route to BMAD agent/skill
akomagni flow router-mode auto     # ML router when inference is online
akomagni skill list                # Discover installed BMAD skills
akomagni model pull qwen2.5-coder-7b
akomagni model pull owner/repo:file.gguf   # Any Hugging Face GGUF
akomagni serve --model phi-3.5-mini        # Local OpenAI-compatible API (:8787)
akomagni mcp serve                 # MCP agent tools (Cursor / VS Code)
akomagni train plan                # Preview LoRA dataset from memory
akomagni train run -m phi-3.5-mini # Native QLoRA/LoRA (needs: akomagni config extras train)
```

## Project structure

```
Akomagni/
├── src/akomagni/       # Python package
│   ├── cli/            # Typer entrypoint
│   ├── core/           # config, doctor, router, registry
│   ├── flow/           # Akomagni Flow orchestrator
│   ├── memory/         # Akomagni Memory
│   └── inference/      # Local server (llama.cpp)
├── docs/               # Documentation (en + fr)
├── install/            # install.sh, install.ps1
├── tests/
└── .github/            # CI, issue/PR templates
```

## Documentation

| Language | Index |
|----------|-------|
| English | [docs/en/README.md](docs/en/README.md) |
| Français | [docs/fr/README.md](docs/fr/README.md) |

## Roadmap

| Version | Focus |
|---------|-------|
| **v0.1** | CLI, doctor, config, Akomagni Flow (heuristic), memory scaffold ✅ |
| **v0.2** | llama.cpp server, model pull, BMAD invoke, RAG, Memory epic, MCP agent ✅ |
| **v0.3** | Akomagni Train (LoRA) — export/bundle + native `train run` |
| **v1.0** | Akomagni IDE (VS Code fork) — MCP + roadmap page today |

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributing

We welcome contributions! Please read:

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, PR process, i18n policy
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md) — vulnerability reporting

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Author

Created by [ASSOUN Akomagni Kodjovi Rodrigue](https://github.com/HordRicJr) — Akomagni is an independent open-source project.
