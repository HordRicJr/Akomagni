# API d'inférence locale

Akomagni expose une API HTTP **compatible OpenAI** via `llama-server` (llama.cpp) sur `http://127.0.0.1:8787/v1`.

## Démarrage rapide

```bash
pip install -e ".[inference]"
akomagni model pull phi-3.5-mini
akomagni serve --model phi-3.5-mini
akomagni inference status
akomagni inference chat "Explique Akomagni Flow en une phrase"
```

## Providers cloud

Les backends d'inférence sont isolés — Akomagni ne mélange jamais les ids catalogue Rodium avec les déploiements Foundry ou les GGUF locaux :

| Connect | Rôle |
|---------|------|
| `akomagni connect local` | llama-server hors ligne (GGUF souvent tirés de Hugging Face) |
| `akomagni connect rodium` | Catalogue Rodium (`google/…`, `openai/…`, …) |
| `akomagni connect foundry <url>` | Noms de **déploiements** Azure / Foundry uniquement |
| `akomagni connect hf` | Token Hub pour `model pull` — **pas** un provider d'inférence |

### Rodium AI

```bash
akomagni connect rodium
akomagni inference status
```

### Microsoft Foundry

Utilise la route Azure OpenAI **v1** (`…/openai/v1`). **Entra ID est le défaut** : Akomagni installe `azure-identity` et lance `az login` si besoin.

```bash
# Azure CLI requis sur le PATH pour la connexion bureau Entra
akomagni connect foundry https://YOUR-RESOURCE.openai.azure.com/openai/v1/

# Hôtes aussi valides :
# https://YOUR-RESOURCE.services.ai.azure.com/openai/v1/
# https://YOUR-RESOURCE.services.ai.azure.com/api/projects/PROJECT

akomagni extras foundry
akomagni inference status

# Auth par clé API à la place d'Entra
akomagni connect foundry https://YOUR-RESOURCE.openai.azure.com/openai/v1/ --auth api_key
```

Variables d'environnement (clé) : `AZURE_OPENAI_API_KEY` / `AZURE_INFERENCE_CREDENTIAL`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_AUTH=api_key|entra`.

Référence : [endpoints Foundry](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints)

## Points d'accès

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Santé du serveur (llama-server) |
| `GET /v1/models` | Modèles chargés |
| `POST /v1/chat/completions` | Complétion chat (format OpenAI) |

## Client OpenAI Python

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="not-needed",  # serveur local, pas d'auth
)

response = client.chat.completions.create(
    model="local",
    messages=[{"role": "user", "content": "Bonjour !"}],
)
print(response.choices[0].message.content)
```

## curl

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Bonjour"}],
    "stream": false
  }'
```

## Sécurité

Le serveur écoute sur **127.0.0.1** par défaut (localhost uniquement). Ne l'exposez pas sur Internet sans authentification.
