# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/HordRicJr/Akomagni/actions/workflows/ci.yml/badge.svg)](https://github.com/HordRicJr/Akomagni/actions/workflows/ci.yml)

**Local, open-source AI workstation** for creators — code, design, images, writing, research, and business workflows.

[Français](README.fr.md) · [Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

---

## Why Akomagni?

Cloud AI tools are powerful but costly, privacy-invasive, and dev-centric. Local tools are often fragmented. **Akomagni** combines:

| Pillar | What it does |
|--------|----------------|
| **Local inference** | Hugging Face models (GGUF), offline, free |
| **Akomagni Flow** | Auto-routes to 17 BMAD agents — no slash commands |
| **Akomagni Memory** | Central + per-project memory, Git-friendly |
| **Auto Router** | Picks the right model per task (code, design, image…) |
| **Three modes** | CLI, Agent, IDE (VS Code fork, planned) |

> Not a Cursor clone. A **multi-domain local workstation** with structured BMAD workflows.

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

### One-liner (when published)

```bash
# Linux / macOS
curl -fsSL https://akomagni.dev/install/linux | bash

# Windows (PowerShell)
irm https://akomagni.dev/install/windows | iex
```

## Commands (v0.1)

```bash
akomagni doctor                    # Scan hardware + recommend profile
akomagni config init               # Create ~/.akomagni/config.yaml
akomagni memory status             # Central + project memory
akomagni flow route "your message" # Test agent/skill routing
akomagni flow invoke "your message"# Write BMAD activation session
akomagni skill list                # Discover installed BMAD skills
akomagni model recommend           # Models for your hardware profile
akomagni run cli                   # Interactive CLI (creates sessions)
akomagni serve                     # Local inference API (stub → llama.cpp)
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
| **v0.1** | CLI, doctor, config, Akomagni Flow (heuristic), memory scaffold, inference stub |
| **v0.2** | llama.cpp server, model pull, BMAD skill invoke, RAG |
| **v0.3** | Akomagni Train (LoRA), ML router |
| **v1.0** | Akomagni IDE (VS Code fork), akomagni.dev site |

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
