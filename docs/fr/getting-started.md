# Démarrage rapide

## Prérequis

- Python 3.11+
- 8 Go RAM minimum (16 Go+ recommandé)
- Git

## Cloner et installer

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Première utilisation

```bash
akomagni config init    # crée ~/.akomagni/config.yaml
akomagni doctor         # scan machine + profil
akomagni memory status  # répertoires mémoire
```

## Tester Akomagni Flow

```bash
akomagni flow route "J'ai une idée pour une app de budget"
# → 📊 Mary · Brainstorming → bmad-brainstorming
```

## CLI interactive

```bash
akomagni run cli
```

## Suite

- [Architecture](architecture.md)
- [Akomagni Flow](akomagni-flow.md)
- [Contribuer](../../CONTRIBUTING.fr.md)
