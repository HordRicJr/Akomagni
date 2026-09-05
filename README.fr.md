# Akomagni

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI Quality](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/quality.yml)
[![CI Test](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/test.yml)
[![CI Security](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml/badge.svg?branch=develop)](https://github.com/HordRicJr/Akomagni/actions/workflows/security.yml)

**Akomagni : une nouvelle façon de travailler avec l’IA.**

Poste de travail IA open source, hybride et extensible, conçu pour aller au-delà du simple chatbot ou assistant de programmation. Il réunit modèles, agents, skills, workflows, mémoire et outils dans un même environnement, afin de transformer une simple demande en véritable processus de travail.

[English](README.md) · [Site](https://hordricjr.github.io/Akomagni/) · [Installation](https://hordricjr.github.io/Akomagni/install/) · [Hub outils](https://hordricjr.github.io/Akomagni/tools/) · [Documentation](docs/README.md) · [Contribuer](CONTRIBUTING.fr.md) · [Code de conduite](CODE_OF_CONDUCT.fr.md)

---

## Des Skills pour donner des capacités à l’IA

Une **Skill** représente une capacité ou une méthode de travail spécialisée que l’IA peut utiliser pour accomplir une tâche précise. Plutôt que de demander à un modèle de tout inventer seul, Akomagni lui permet de s’appuyer sur des compétences structurées : développement, design, recherche, rédaction, analyse, produit, business, et plus.

Le modèle fournit l’intelligence. Les Skills lui donnent une manière structurée de travailler. Enregistre-les avec `akomagni skill link`.

## Des agents spécialisés

Akomagni ne se limite pas à un seul agent généraliste. Le système intègre **17 agents BMAD**, chacun associé à des tâches et workflows spécifiques, pour passer d’une IA qui répond à une IA capable d’adopter différents rôles selon le contexte.

## Akomagni Flow : pas besoin de connaître le système

Décris ton objectif avec tes propres mots. Tu n’as pas besoin du nom d’un agent, d’une Skill ou d’une commande particulière.

Akomagni analyse la demande et peut l’orienter vers le bon **agent + workflow + Skill** :

**Intention → Analyse → Agent → Skill → Workflow → Résultat**

Flow est la couche d’orchestration entre toi et les outils d’IA.

## Un Auto Router pour choisir le bon modèle

Akomagni n’impose pas un modèle unique. L’Auto Router sélectionne le modèle le plus adapté selon la tâche : code, design, image, texte, etc.

Sur **Rodium**, cela passe par des identifiants multi-providers économiques (Google, Anthropic, OpenAI, `rodiumai/smart`, …) et les tarifs du catalogue quand ils sont disponibles. En local, les domaines pointent vers tes GGUF téléchargés.

## Local, cloud ou hybride

- **Local :** modèles Hugging Face au format GGUF, y compris hors ligne
- **Cloud :** tes propres services via Rodium ou Microsoft Foundry (`akomagni connect`)
- **Hybride :** modèles locaux + APIs externes + agents + skills + tools

Tu gardes la liberté de choisir comment et avec quels moteurs travailler.

## Une mémoire qui accompagne les projets

**Akomagni Memory** conserve une mémoire centrale et une mémoire par projet, pour garder le contexte, les informations et l’historique utiles plutôt que de repartir de zéro à chaque interaction.

## Un même environnement, plusieurs façons de travailler

| Surface | Statut |
|---------|--------|
| **CLI** | Interface principale aujourd’hui : config, modèles, skills, Flow, mémoire, services |
| **VS Code + MCP** | Extension et outils MCP pour Cursor / VS Code |
| **IDE** | Feuille de route : intégration plus profonde dans l’espace de travail |

La langue de l’interface CLI est **l’anglais par défaut**. Tu peux changer ensuite :

```bash
akomagni config language fr   # Français
akomagni config language en   # Anglais (défaut)
```

## Ce qui différencie Akomagni

Les outils d’IA se concentrent souvent sur une fonction : écrire du code, discuter, générer des images ou automatiser une tranche de tâches.

Akomagni vise un environnement où **plusieurs modèles, agents, Skills et workflows collaborent**.

Pas seulement : *Quelle réponse l’IA peut-elle me donner ?*

Mais : *Quel est mon objectif, quelles compétences sont nécessaires, et quel workflow l’IA doit-elle utiliser pour m’aider ?*

Open source : l’architecture peut être étudiée, adaptée et enrichie (nouvelles Skills, agents, modèles, intégrations).

### En une phrase

Akomagni est un poste de travail IA open source qui orchestre modèles, agents, Skills, mémoire et workflows pour transformer une intention utilisateur en processus de travail intelligent.

**One workspace. Multiple models. Specialized agents. Powerful Skills. Intelligent workflows. Open source.**

---

## Démarrage rapide

### Prérequis

- Python **3.11+**
- **8 Go RAM** minimum (16 Go+ recommandé)
- Windows, Linux ou macOS

### Installation en une ligne

```bash
# Linux / macOS
curl -fsSL https://hordricjr.github.io/Akomagni/install/linux | bash

# Windows (PowerShell)
irm https://hordricjr.github.io/Akomagni/install/windows | iex
```

Puis :

```bash
akomagni connect
akomagni skill link
akomagni run cli --project ./mon-app
# optionnel :
akomagni config language fr
```

Guide complet : [hordricjr.github.io/Akomagni/install/](https://hordricjr.github.io/Akomagni/install/)

### Installation développement

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
akomagni connect
akomagni skill link
```

## Commandes

```bash
akomagni doctor                    # Scan machine + profil
akomagni connect                   # Local / Rodium / Foundry + token HF optionnel
akomagni skill link                # Enregistrer les skills BMAD
akomagni run cli --project ./app   # Chat + Flow sur un projet
akomagni config init               # Crée ~/.akomagni/config.yaml (language: en)
akomagni config language fr        # Optionnel : CLI en français
akomagni update                    # Dernière version + réinstall CLI
akomagni memory status             # Mémoire centrale + projet
akomagni flow route "ton message"  # Routage agent/skill BMAD
akomagni flow router-mode auto     # Routeur ML si inférence en ligne
akomagni skill list                # Lister les skills liées
akomagni model pull qwen2.5-coder-7b
akomagni model pull owner/repo:file.gguf
akomagni serve --model phi-3.5-mini
akomagni mcp serve
akomagni train plan
akomagni train run -m phi-3.5-mini
```

## Documentation

| Langue | Index |
|--------|-------|
| English | [docs/en/README.md](docs/en/README.md) |
| Français | [docs/fr/README.md](docs/fr/README.md) |

## Feuille de route

| Version | Focus |
|---------|-------|
| **v0.1** | CLI, doctor, config, Akomagni Flow (heuristique), mémoire ✅ |
| **v0.2** | Serveur llama.cpp, model pull, invoke BMAD, RAG, MCP ✅ |
| **v0.3** | Train (LoRA), connect, skill link, Auto Router Rodium multi-providers ✅ |
| **v1.0** | Akomagni IDE (fork VS Code) — MCP + page roadmap aujourd’hui |

Voir [CHANGELOG.md](CHANGELOG.md).

## Contribuer

- [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md)
- [CODE_OF_CONDUCT.fr.md](CODE_OF_CONDUCT.fr.md)
- [SECURITY.md](SECURITY.md)

## Licence

Apache-2.0 — voir [LICENSE](LICENSE).

## Auteur

Créé par [ASSOUN Akomagni Kodjovi Rodrigue](https://github.com/HordRicJr) — Akomagni est un projet open source indépendant.
