# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`--project` isolation**: a folder with `.akomagni` (e.g. `./app_test` under a parent BMAD checkout) keeps sessions/workflow/RAG/memory there — no longer inherits the parent `_bmad` tree
- **CLI chat**: do not auto-enable `--exec` on new projects; isolated projects are not treated as BMAD exec roots; system prompt stays step-by-step (no codebase dumps)

## [0.3.0] - 2026-09-05

### Added

- **BMAD kernel**: shipped under `bmad-core/` — install and `akomagni update` register skills automatically (no `skill link` / path knowledge required)
- **Update report**: `akomagni update` shows version bump, changelog highlights, and BMAD skill count
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

### Changed

- **BMAD skill discovery**: portable only (cwd / home skill folders / shipped kernel / `skill link` config) — no hardcoded developer machine paths
- **BMAD skill exec**: resolve `_bmad/scripts/render_skill.py` from the skill path / linked workspace (not only cwd); persist `skills.bmad_project_root` on `skill link`; skip free-chat code dumps for BMAD skills
- **Site design**: high-contrast readable UI (Syne + Source Sans 3, teal accent, cool mist background); brand-first hero and clearer section rhythm on GitHub Pages
- **Site copy**: features aligned with product (Skills, 17 agents, Flow pipeline, Auto Router + Space/`/model` picker, hybrid, memory, CLI/IDE)
- **Install guide**: install → connect → run (skills come with the kernel)
- **Image routing**: quality-first multi-vendor models (Gemini Pro/Flash Image + OpenAI gpt-image); CLI asks where to save the PNG after generation
- **Image save on Windows**: chunked writes + data-URL base64 cleanup so large Gemini PNGs no longer fail with Errno 22
- **Rodium model picker**: Auto (by task) or pin any catalogue model — Space / `/model` opens the list in CLI; asked during `akomagni connect`
- **Rodium catalogue defaults**: align economy/balanced/coding/strong static candidates with current multi-provider model ids
- **Docs / README / site**: product vision (skills, agents, Flow, Auto Router, hybrid, memory); CLI language English by default

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

[Unreleased]: https://github.com/HordRicJr/Akomagni/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/HordRicJr/Akomagni/compare/v0.1.0...v0.3.0
[0.1.0]: https://github.com/HordRicJr/Akomagni/releases/tag/v0.1.0
