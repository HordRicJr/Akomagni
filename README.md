# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI Quality](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml)
[![CI Test](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml)
[![CI Security](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml)

**Akomagni: a new way to work with AI.**

An open-source hybrid AI workstation, built to go beyond a chatbot or coding assistant. It brings models, agents, skills, workflows, memory, and tools into one environment so a simple request becomes a real work process.

[Français](README.fr.md) · [Site](https://hordricjr.github.io/Akomagni/) · [Install](https://hordricjr.github.io/Akomagni/install/) · [Tools hub](https://hordricjr.github.io/Akomagni/tools/) · [Documentation](docs/README.md) · [Roadmap](ROADMAP.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

---

## Skills give the AI real capabilities

A **Skill** is a specialized capability or working method the AI can use for a precise task. Instead of asking one model to invent every process alone, Akomagni lets it lean on structured competencies: development, design, research, writing, analysis, product, business, and more.

The model supplies intelligence. Skills supply a structured way to work. They ship in the BMAD kernel on install / `akomagni update` — no path setup required.

## Specialized agents

Akomagni is not a single generalist agent. It ships **17 BMAD agents**, each tied to tasks and workflows, so the system can take different roles depending on context.

## Akomagni Flow: you do not need to know the system

Describe your goal in your own words. You do not need agent names, skill ids, or special commands.

Akomagni analyzes the request and can route it to the right **agent + workflow + skill**:

**Intent → Analysis → Agent → Skill → Workflow → Result**

Flow is the orchestration layer between you and the AI tools.

## Auto Router: pick the right model

Akomagni does not force a single model. Auto Router selects the best fit by task (code, design, image, text, and more).

On **Rodium**, that means economical multi-provider catalogue ids (Google, Anthropic, OpenAI, `rodiumai/smart`, …) using live pricing when available. Locally, it maps domains to your pulled GGUF models.

## Local, cloud, or hybrid

- **Local:** Hugging Face GGUF models, including offline work
- **Cloud:** your own APIs via Rodium or Microsoft Foundry (`akomagni connect`)
- **Hybrid:** local models + external APIs + agents + skills + tools

You choose how and with which engines you work.

## Memory that stays with the project

**Akomagni Memory** keeps a central store and per-project memory so context, facts, and history survive sessions instead of resetting every chat.

## One environment, several ways to work

| Surface | Status |
|---------|--------|
| **CLI** | Primary interface today: config, models, skills, Flow, memory, services |
| **VS Code + MCP** | Extension and MCP tools for Cursor / VS Code |
| **IDE** | Roadmap: deeper integration in the developer workspace |

CLI UI language defaults to **English**. Switch anytime:

```bash
akomagni config language fr   # French
akomagni config language en   # English (default)
```

## What makes Akomagni different

Most AI tools focus on one job: write code, chat, generate images, or automate a slice of work.

Akomagni aims at an environment where **models, agents, skills, and workflows collaborate**.

Not only: *What answer can the AI give me?*

But: *What is my goal, which competencies are needed, and which workflow should the AI use to help me get there?*

Because it is open source, the architecture can be studied, adapted, and extended: new skills, agents, models, and integrations.

### In one sentence

Akomagni is an open-source AI workstation that orchestrates models, agents, skills, memory, and workflows to turn user intent into an intelligent work process.

**One workspace. Multiple models. Specialized agents. Powerful Skills. Intelligent workflows. Open source.**

---

## Quick start

### Requirements

- Python **3.11+**
- **8 GB RAM** minimum (16 GB+ recommended)
- Windows, Linux, or macOS

### One-liner install

```bash
# Linux / macOS
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Then:

```bash
akomagni connect
akomagni skill list
akomagni run cli --project ./my-app
```

Full guide: [hordricjr.github.io/Akomagni/install/](https://hordricjr.github.io/Akomagni/install/)

### Development install

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
akomagni connect
akomagni skill list
```

## Commands

```bash
akomagni doctor                    # Hardware scan + profile + BMAD kernel
akomagni connect                   # Local / Rodium / Foundry + optional HF token
akomagni skill list                # List shipped BMAD skills
akomagni skill link                # Optional: register an extra custom skill folder
akomagni run cli --project ./app   # Chat + Flow on a project
akomagni config init               # Create ~/.akomagni/config.yaml (language: en)
akomagni config language fr        # Optional: French CLI
akomagni update                    # Pull latest, sync BMAD kernel, show what's new
akomagni memory status             # Central + project memory
akomagni flow route "your message" # Route to BMAD agent/skill
akomagni flow router-mode auto     # ML router when inference is online
akomagni skill list                # List linked skills
akomagni model pull qwen2.5-coder-7b
akomagni model pull owner/repo:file.gguf   # Any Hugging Face GGUF
akomagni serve --model phi-3.5-mini        # Local OpenAI-compatible API (:8787)
akomagni mcp serve                 # MCP agent tools (Cursor / VS Code)
akomagni train plan                # Preview LoRA dataset from memory
akomagni train run -m phi-3.5-mini # Native QLoRA/LoRA (akomagni config extras train)
```

## Project structure

```
Akomagni/
├── src/akomagni/       # Python package
│   ├── cli/            # Typer entrypoint
│   ├── core/           # config, doctor, router, registry
│   ├── flow/           # Akomagni Flow orchestrator
│   ├── memory/         # Akomagni Memory
│   └── inference/      # Local server + cloud providers
├── docs/               # Documentation (en + fr)
├── site/               # GitHub Pages
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
| **v0.3** | Akomagni Train (LoRA), connect wizard, skill link, Rodium multi-provider Auto Router ✅ |
| **v1.0** | Akomagni IDE (VS Code fork) — MCP + roadmap page today |

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributing

- [CONTRIBUTING.md](CONTRIBUTING.md) — English first, French mirror required for docs
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Author

Created by [ASSOUN Akomagni Kodjovi Rodrigue](https://github.com/HordRicJr) — Akomagni is an independent open-source project.
