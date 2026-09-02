# Akomagni Chat — VS Code Extension

Graphical chat sidebar for Akomagni. Connect Rodium AI, Azure Foundry, or local inference from the CLI, then chat in VS Code.

## Quick start

1. Install this extension from the VS Code Marketplace (search **Akomagni Chat**).
2. In your project terminal:

```bash
akomagni connect rodium
# or
akomagni connect foundry https://YOUR-RESOURCE.openai.azure.com/openai/v1/
```

3. Open the **Akomagni** icon in the Activity Bar → **Chat**.

## Configure manually

VS Code Settings (`akomagni.*`):

| Setting | Description |
|---------|-------------|
| `akomagni.provider` | `rodium`, `azure`, or `local` |
| `akomagni.baseUrl` | OpenAI-compatible API URL |
| `akomagni.apiKey` | API key (set by `akomagni connect`) |
| `akomagni.model` | Model id (e.g. `openai/gpt-4o`) |

## Azure Foundry alternative

You can also use **Microsoft Foundry Toolkit** (`ms-windows-ai-studio.windows-ai-studio`) for the full Azure model playground and agent builder.

## Development

```bash
cd vscode-extension
code .
# Press F5 to launch Extension Development Host
```

## Publish

```bash
npm install -g @vscode/vsce
vsce package
vsce publish
```
