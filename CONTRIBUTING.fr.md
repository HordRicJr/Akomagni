# Contribuer à Akomagni

Merci de ton intérêt ! Akomagni suit les pratiques des grands projets open source.

**English:** [CONTRIBUTING.md](CONTRIBUTING.md)

## Branches

**Cible des PR : `develop`** (pas `main`). `main` = releases stables uniquement.

```
main ← releases
  ↑
develop ← intégration (ouvre tes PR ici)
  ↑
feature/#123-description
```

Guide : [docs/fr/branching.md](docs/fr/branching.md)

## Commits liés aux issues

```
feat(#42): intégrer llama-server
fix(#15): correction VRAM Windows
test(#21): couverture orchestrator
```

## CI requise

| Workflow | Vérifications |
|----------|---------------|
| **Quality** | Ruff lint + format, parité docs EN/FR |
| **Test** | Tests unitaires/régression (Ubuntu + Windows) |
| **Coverage** | Couverture ≥ **90 %** |
| **Security** | pip-audit, Bandit, Gitleaks |

```bash
ruff check src tests && ruff format --check src tests
pytest -m regression              # suite régression (gate CI)
pytest tests/ --cov=akomagni --cov-fail-under=90
bandit -r src -c pyproject.toml
pip-audit
```

## Installation dev

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
git checkout develop
pip install -e ".[dev]"
akomagni config init
```

## Process PR

1. Branche depuis `develop`
2. Référence l'issue dans chaque commit `type(#N): …`
3. CHANGELOG + docs EN/FR
4. CI verte → review → merge dans `develop`

## Questions ?

[GitHub Discussions](https://github.com/HordRicJr/Akomagni/discussions)
