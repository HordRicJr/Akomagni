# Contributing to Akomagni

Thank you for your interest in contributing! Akomagni follows practices used by successful open-source projects (clear docs, CI, templates, bilingual maintenance).

**Français:** [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md)

## Table of contents

- [Code of Conduct](#code-of-conduct)
- [How to contribute](#how-to-contribute)
- [Branching strategy](#branching-strategy)
- [Development setup](#development-setup)
- [Project structure](#project-structure)
- [Pull request process](#pull-request-process)
- [Internationalization (i18n)](#internationalization-i18n)
- [Commit messages](#commit-messages)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## How to contribute

1. **Check existing issues** — someone may already be working on it.
2. **Open an issue** for bugs or features before large changes.
3. **Fork** the repo and create a branch from **`develop`** (not `main`).
4. **Make focused changes** — one concern per PR, linked to an issue.
5. **Update docs** (EN + FR when user-facing).
6. **Run tests** locally.
7. **Open a PR** using our template.

Good first contributions:

- Documentation fixes (EN or FR)
- Tests for `doctor`, `flow`, `memory`
- Bug fixes with reproduction steps
- Improving error messages

## Branching strategy

**Default PR target: `develop`.** Only maintainers merge `develop` → `main` for stable releases.

```
main ← stable releases
  ↑
develop ← integration (open PRs here)
  ↑
feature/#123-description
```

Full guide: [docs/en/branching.md](docs/en/branching.md)

### Commits must reference issues

```
feat(#42): integrate llama-server subprocess
fix(#15): correct VRAM detection on Windows
```

## Development setup

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
pytest
ruff check src tests
```

### Requirements

- Python 3.11+
- Git
- (Optional) NVIDIA GPU + drivers for CUDA inference tests

## Project structure

```
src/akomagni/
├── cli/          # Typer commands
├── core/         # config, doctor, router, registry
├── flow/         # Akomagni Flow orchestrator
├── memory/       # Akomagni Memory
└── inference/    # Local llama.cpp server
```

See [docs/en/architecture.md](docs/en/architecture.md) for design details.

## Pull request process

1. Update [CHANGELOG.md](CHANGELOG.md) under `## [Unreleased]` for user-visible changes.
2. Update **both** EN and FR docs when changing user-facing behavior.
3. Ensure CI passes (pytest + ruff).
4. Request review from maintainers.
5. Squash or merge per maintainer preference.

PRs without tests may be accepted for docs-only changes. Code changes should include tests when practical.

## Internationalization (i18n)

Akomagni maintains documentation in **English** (canonical) and **French**.

| Path | Language | Role |
|------|----------|------|
| `README.md` | English | Primary README |
| `README.fr.md` | French | French README |
| `docs/en/` | English | Full documentation |
| `docs/fr/` | French | Mirrored documentation |
| `CONTRIBUTING.md` / `.fr.md` | Both | Contribution guides |
| `CODE_OF_CONDUCT.md` / `.fr.md` | Both | Community standards |

**Rule:** Any PR that changes user-facing docs **must** update the matching file in both languages, or open a follow-up issue labeled `i18n` within 48 hours.

See [docs/I18N.md](docs/I18N.md) for the full policy.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/) **with issue numbers**:

```
feat(#42): integrate llama-server subprocess
fix(#15): correct VRAM detection on Windows
docs(#8): update getting-started FR
test(#21): add flow orchestrator coverage
ci(#30): add gitleaks workflow
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `security`.

## CI requirements

All PRs to `develop` must pass:

| Workflow | Checks |
|----------|--------|
| **Quality** | Ruff lint + format, i18n doc parity |
| **Test** | Unit/regression tests (Ubuntu + Windows, Python 3.11–3.12) |
| **Coverage** | ≥ **90%** line coverage (`pytest-cov`) |
| **Security** | `pip-audit`, Bandit SAST, Gitleaks secrets scan |

Run locally before pushing:

```bash
ruff check src tests && ruff format --check src tests
pytest tests/ --cov=akomagni --cov-fail-under=90
bandit -r src -c pyproject.toml
pip-audit
```

## Testing

```bash
pytest                    # all tests
pytest tests/test_doctor.py -v
akomagni flow route "new app idea"  # manual smoke test
```

## Documentation

- Architecture: [docs/en/architecture.md](docs/en/architecture.md)
- Akomagni Flow: [docs/en/akomagni-flow.md](docs/en/akomagni-flow.md)
- Akomagni Memory: [docs/en/akomagni-memory.md](docs/en/akomagni-memory.md)

When adding a new doc page, create both `docs/en/<name>.md` and `docs/fr/<name>.md`, and link from both README indexes.

## Questions?

Open a [GitHub Discussion](https://github.com/HordRicJr/Akomagni/discussions) or an issue with the `question` label.
