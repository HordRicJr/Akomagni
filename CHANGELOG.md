# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Git Flow: `develop` integration branch, `main` for stable releases only
- CI workflows: **Quality** (ruff lint/format, i18n), **Test** (regression + 90% coverage), **Security** (pip-audit, bandit, gitleaks)
- Branching docs (EN/FR), ROADMAP.md, GitHub issues for full v0.2–v1.0 roadmap
- Commit convention: `type(#issue): summary`
- PR template targets `develop`

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
