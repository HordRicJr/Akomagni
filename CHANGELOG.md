# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Site design**: light, minimal product UI inspired by clean workstation sites (Ollama-like typography and install-first home)
- **Install guide**: shorter path — install → connect → skill link → run
- **Rodium image routing**: prefer URL-capable OpenAI image models (`gpt-image-1-mini`, `gpt-image-1.5`, …) with fallbacks across the catalogue; save Gemini base64 responses as PNG under `generated-images/`
- **Rodium catalogue defaults**: align economy/balanced/coding/strong static candidates with current multi-provider model ids
- **Docs / README / site**: product vision (skills, agents, Flow, Auto Router, hybrid, memory); CLI language English by default

### Added

- **Skill link**: `akomagni skill link` registers BMAD skill folders so Flow works outside the install tree; English greenfield intents (`build a`, `brainstorming`) route to brainstorming
- **Rodium routing**: multi-provider catalogue (Google / Anthropic / OpenAI / `rodiumai/smart`); picks economical models by task using `GET /v1/models` pricing; remaps legacy `rodium/basic|fast|pro`
- **Connect wizard**: `akomagni connect` for local / Rodium / Foundry + Hugging Face token; `run cli --project` onboarding; pull any Hub GGUF via `owner/repo:file.gguf`
- **Train (LoRA)** — `akomagni train plan|export|bundle|run`; native QLoRA (CUDA) / LoRA fallback via `akomagni[train]`
- **Site** — GitHub Pages hub: install, tools marketplace, IDE roadmap, module pages
- **CLI i18n** — English/French (`akomagni config language fr`)
- **ML flow router** — `heuristic` / `ml` / `auto` modes via local inference
- **Train scaffold** — `akomagni train plan` / `export` / `bundle` from memory
- **Memory epic** — add, promote, auto-capture with approval queue
- **MCP agent tools** — sandboxed fs/shell/git with approval queue
- **RAG** — hybrid BM25 + vector ingest/query
- **Inference** — llama.cpp server, model pull, OpenAI-compatible API on :8787
- Install one-liners published at `hordricjr.github.io/Akomagni/install/`

### Added (v0.1.1)

- `akomagni flow invoke` — writes BMAD activation session files
- `akomagni flow status` — workflow state for current project
- `akomagni skill list` / `skill path` — discover BMAD skills on disk
- `akomagni model recommend` / `model list` — hardware-based model suggestions
- Interactive CLI creates session files by default (`--no-invoke` to disable only routing)
- Skill discovery from `~/.akomagni/skills`, `.claude/skills`, and `_bmad` manifest

### Added (v0.1.0 scaffold)

- Initial open-source release scaffold
- CLI: `doctor`, `config`, `memory status`, `flow route`, `run cli`, `serve` (stub)
- Akomagni Flow heuristic router (17 BMAD agents catalog)
- Akomagni Memory central scaffold (`~/.akomagni/`)
- Bilingual documentation (EN + FR)
- CI workflow (pytest + ruff)
- Contributing guidelines, Code of Conduct, Security policy

## [0.1.0] - 2026-08-29

### Added

- Project bootstrap: Python package, Typer CLI, install scripts
- Hardware scan via `akomagni doctor`
- Apache-2.0 license

[Unreleased]: https://github.com/HordRicJr/Akomagni/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/HordRicJr/Akomagni/releases/tag/v0.1.0
