## Summary

<!-- What does this PR do? Link the issue: Fixes #N -->

Fixes #

## Type of change

- [ ] Bug fix (`fix`)
- [ ] New feature (`feat`)
- [ ] Documentation (EN)
- [ ] Documentation (FR)
- [ ] Tests / coverage
- [ ] CI / security
- [ ] Refactor / chore

## Target branch

- [ ] This PR targets **`develop`** (required for features/fixes)
- [ ] This PR targets `main` (release/hotfix only — maintainer approval required)

## i18n checklist

- [ ] User-facing docs updated in **English** (`docs/en/`, `README.md`)
- [ ] User-facing docs updated in **French** (`docs/fr/`, `README.fr.md`)
- [ ] Or linked issue labeled `i18n`

## CI checklist

```bash
ruff check src tests && ruff format --check src tests
pytest tests/ --cov=akomagni --cov-fail-under=90
bandit -r src -c pyproject.toml
```

- [ ] Quality workflow passes
- [ ] Test + coverage (≥90%) passes
- [ ] Security workflow passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Commits

<!-- Commits follow: type(#issue): summary -->
