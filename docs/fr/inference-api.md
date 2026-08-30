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
