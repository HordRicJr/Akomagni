# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/HordRicJr/Akomagni/actions/workflows/ci.yml/badge.svg)](https://github.com/HordRicJr/Akomagni/actions/workflows/ci.yml)

**Poste de travail IA local et open source** pour les créateurs — code, design, image, rédaction, recherche et business.

[English](README.md) · [Documentation](docs/README.md) · [Contribuer](CONTRIBUTING.fr.md) · [Code de conduite](CODE_OF_CONDUCT.fr.md)

---

## Pourquoi Akomagni ?

Les outils IA cloud sont puissants mais payants, envoient tes données ailleurs, et ciblent surtout les devs. Le local est souvent fragmenté. **Akomagni** réunit :

| Pilier | Rôle |
|--------|------|
| **Inférence locale** | Modèles Hugging Face (GGUF), offline, gratuit |
| **Akomagni Flow** | Route automatiquement vers 17 agents BMAD — pas de `/` |
| **Akomagni Memory** | Mémoire centrale + projet, compatible Git |
| **Router Auto** | Choisit le modèle selon la tâche (code, design, image…) |
| **3 modes** | CLI, Agent, IDE (fork VS Code, prévu) |

> Pas un clone Cursor. Un **poste de travail local multi-métiers** avec workflows BMAD structurés.

## Démarrage rapide

### Prérequis

- Python **3.11+**
- **8 Go RAM** minimum (16 Go+ recommandé)
- Windows, Linux ou macOS

### Installation (développement)

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
akomagni doctor
```

## Commandes (v0.1)

```bash
akomagni doctor                    # Scan machine + profil recommandé
akomagni config init               # Crée ~/.akomagni/config.yaml
akomagni memory status             # Mémoire centrale + projet
akomagni flow route "ton message"  # Tester le routage agent/skill
akomagni run cli                   # CLI interactive (stub)
akomagni serve                     # API inference locale (stub → llama.cpp)
```

## Documentation

| Langue | Index |
|--------|-------|
| English | [docs/en/README.md](docs/en/README.md) |
| Français | [docs/fr/README.md](docs/fr/README.md) |

## Feuille de route

| Version | Focus |
|---------|-------|
| **v0.1** | CLI, doctor, config, Akomagni Flow (heuristique), mémoire, stub inference |
| **v0.2** | Serveur llama.cpp, model pull, invoke skills BMAD, RAG |
| **v0.3** | Akomagni Train (LoRA), router ML |
| **v1.0** | Akomagni IDE (fork VS Code), site akomagni.dev |

Voir [CHANGELOG.md](CHANGELOG.md).

## Contribuer

- [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md)
- [CODE_OF_CONDUCT.fr.md](CODE_OF_CONDUCT.fr.md)
- [SECURITY.md](SECURITY.md)

## Licence

Apache-2.0 — voir [LICENSE](LICENSE).

## Auteur

Créé par [Assou](https://github.com/HordRicJr).
