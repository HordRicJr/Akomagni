# Akomagni Chat — VS Code Extension

**Your AI chat sidebar for VS Code** — BMAD agent routing, local models, Rodium AI, and Azure AI Foundry in one place.

## Install

1. Download `akomagni-chat-0.2.0.vsix` from your Downloads folder.
2. In VS Code: **Extensions** → `...` menu → **Install from VSIX…**
3. Or run: `code --install-extension akomagni-chat-0.2.0.vsix`

## Connect a provider

```bash
# Online (Rodium AI) — prompts for API key
akomagni connect rodium

# Azure AI Foundry
akomagni connect foundry https://YOUR-RESOURCE.openai.azure.com/openai/v1/

# Local (offline)
akomagni config provider local
akomagni serve --model qwen2.5-coder-7b
```

## Use

1. Click the **Akomagni** icon in the Activity Bar.
2. Select provider: **Local** | **Rodium** | **Azure Foundry**.
3. Pick a model from the dropdown.
4. Chat — BMAD agents route your message automatically (same as `akomagni run cli`).

## Requirements

- [Akomagni CLI](https://github.com/HordRicJr/Akomagni) on PATH for BMAD routing.
- For cloud: `akomagni connect` (syncs VS Code settings).
- For local: `akomagni serve` running on port 8787.

## Logo

Marketplace icon: `media/icon-128.png` (128×128 PNG).
