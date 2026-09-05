# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI Quality](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml)
[![CI Test](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml)
[![CI Security](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml)

**Akomagni: une nouvelle façon de travailler avec l’IA.** Poste de travail IA open source, hybride et extensible: modèles, agents, skills, mémoire et workflows dans un même environnement.

[English](README.md) · [Site](https://hordricjr.github.io/Akomagni/) · [Installation](https://hordricjr.github.io/Akomagni/install/) · [Hub outils](https://hordricjr.github.io/Akomagni/tools/) · [Documentation](docs/README.md) · [Contribuer](CONTRIBUTING.fr.md) · [Code de conduite](CODE_OF_CONDUCT.fr.md)

---

## Pourquoi Akomagni ?

Les outils IA cloud sont puissants mais fragmentés. Le local reste souvent isolé. **Akomagni** réunit :

| Pilier | Rôle |
|--------|------|
| **Local + cloud** | GGUF Hugging Face hors ligne, ou API Rodium / Microsoft Foundry |
| **Akomagni Flow** | Oriente le langage naturel vers 17 agents BMAD et leurs skills |
| **Skills** | Méthodes de travail structurées (`akomagni skill link`) |
| **Router Auto** | Choisit le modèle selon la tâche; sur Rodium: auto / fast / pro |
| **Mémoire** | Contexte central + projet qui survit aux sessions |
| **3 modes** | CLI, Agent, IDE (extension VS Code + MCP) |

> Pas un simple chatbot. Un **poste de travail multi-métiers** où skills, agents et workflows collaborent.

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

### Installation en une ligne

```bash
# Linux / macOS
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Guide complet : [hordricjr.github.io/Akomagni/install/](https://hordricjr.github.io/Akomagni/install/)

## Commandes

```bash
akomagni doctor                    # Scan machine + profil recommandé
akomagni connect                   # Wizard: local / Rodium / Foundry + token HF
akomagni skill link                # Enregistrer les skills BMAD
akomagni run cli --project ./app   # Chat + Flow sur un projet
akomagni config init               # Crée ~/.akomagni/config.yaml
akomagni config language fr        # Interface CLI en français
akomagni memory status             # Mémoire centrale + projet
akomagni flow route "ton message"  # Routage vers agent/skill BMAD
akomagni flow router-mode auto     # Routeur ML si l'inférence est en ligne
akomagni model pull qwen2.5-coder-7b  # Télécharger un modèle GGUF
akomagni serve --model phi-3.5-mini   # API locale compatible OpenAI (:8787)
akomagni mcp serve                 # Outils agent MCP (Cursor / VS Code)
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
