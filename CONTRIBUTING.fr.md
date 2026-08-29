# Contribuer à Akomagni

Merci de ton intérêt ! Akomagni suit les pratiques des grands projets open source : docs claires, CI, templates, maintenance bilingue.

**English:** [CONTRIBUTING.md](CONTRIBUTING.md)

## Code de conduite

Ce projet adhère au [Contributor Covenant](CODE_OF_CONDUCT.fr.md).

## Comment contribuer

1. **Vérifie les issues** existantes.
2. **Ouvre une issue** avant les gros changements.
3. **Fork** le repo, branche depuis `main`.
4. **Changements ciblés** — une préoccupation par PR.
5. **Mets à jour la doc** (EN + FR si visible utilisateur).
6. **Lance les tests** localement.
7. **Ouvre une PR** avec le template.

## Installation dev

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -e ".[dev]"
akomagni config init
pytest
ruff check src tests
```

## Process PR

1. Mettre à jour [CHANGELOG.md](CHANGELOG.md) section `## [Unreleased]`.
2. Mettre à jour **EN et FR** pour tout changement visible.
3. CI verte (pytest + ruff).
4. Review par les mainteneurs.

## Internationalisation (i18n)

| Chemin | Langue |
|--------|--------|
| `README.md` | Anglais (canonique) |
| `README.fr.md` | Français |
| `docs/en/` | Documentation anglaise |
| `docs/fr/` | Documentation française |

**Règle :** toute PR modifiant la doc utilisateur **doit** mettre à jour les deux langues, ou ouvrir une issue `i18n` sous 48 h.

Voir [docs/I18N.md](docs/I18N.md).

## Messages de commit

Format [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat(flow): gate brainstorm obligatoire greenfield
fix(doctor): détection VRAM Windows
docs(fr): guide démarrage
```

## Tests

```bash
pytest
akomagni flow route "une idée pour une app"
```

## Questions ?

[GitHub Discussions](https://github.com/HordRicJr/Akomagni/discussions) ou issue label `question`.
