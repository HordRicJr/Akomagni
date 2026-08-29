# Getting started

## Prerequisites

- Python 3.11+
- 8 GB RAM minimum (16 GB+ recommended)
- Git

## Clone and install

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## First run

```bash
akomagni config init    # creates ~/.akomagni/config.yaml
akomagni doctor         # hardware scan + profile recommendation
akomagni memory status  # memory directories
```

## Try Akomagni Flow

```bash
akomagni flow route "I have an idea for a budget app"
akomagni flow invoke "I have an idea for a budget app"   # writes session file
akomagni flow status
akomagni skill list
akomagni model recommend
```

## Interactive CLI

```bash
akomagni run cli
```

## Next steps

- [Architecture](architecture.md)
- [Akomagni Flow](akomagni-flow.md)
- [Contributing](../../CONTRIBUTING.md)
