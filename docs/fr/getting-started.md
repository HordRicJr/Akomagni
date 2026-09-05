# Démarrage rapide

## Prérequis

- Python 3.11+
- 8 Go RAM minimum (16 Go+ recommandé)
- Git

## Installation

One-liner (recommandé) : voir le [guide Install](https://hordricjr.github.io/Akomagni/install/).

Développement :

```bash
git clone https://github.com/HordRicJr/Akomagni.git
cd Akomagni
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Première utilisation

La langue CLI est **l’anglais par défaut**. Ensuite : `akomagni config language fr`.

```bash
akomagni config init
akomagni doctor
akomagni connect              # GGUF local, Rodium ou Foundry
akomagni skill link           # enregistrer les skills BMAD
akomagni run cli --project ./mon-app
```

## Tester Akomagni Flow

```bash
akomagni flow route "J'ai une idée pour une app de budget"
akomagni flow invoke "J'ai une idée pour une app de budget"
akomagni flow status
akomagni skill list
akomagni model recommend
```

## Image / affiche (cloud)

Avec Rodium, demande une affiche dans `akomagni run cli`. L’Auto Router essaie d’abord les
modèles image qui renvoient une URL, puis la famille Gemini image. Si l’API ne renvoie que
du base64, Akomagni enregistre un PNG dans
`%LOCALAPPDATA%\akomagni\generated-images\` (Linux/macOS :
`~/.local/share/akomagni/generated-images/`) et affiche le chemin.

## Suite

- [Architecture](architecture.md)
- [Akomagni Flow](akomagni-flow.md)
- [Contribuer](../../CONTRIBUTING.fr.md)
