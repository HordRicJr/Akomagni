# Local inference API

Akomagni serves an **OpenAI-compatible** HTTP API via [llama.cpp](https://github.com/ggerganov/llama.cpp) `llama-server` on `http://127.0.0.1:8787/v1`.

## Quick start

```bash
pip install -e ".[inference]"
akomagni model pull phi-3.5-mini
akomagni serve --model phi-3.5-mini
akomagni inference status
akomagni inference chat "Explain Akomagni Flow in one sentence"
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Server health (llama-server) |
| `GET /v1/models` | List loaded models |
| `POST /v1/chat/completions` | Chat completion (OpenAI format) |

## OpenAI Python client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="not-needed",  # local server, no auth
)

response = client.chat.completions.create(
    model="local",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

## curl

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

## Security

The server binds to **127.0.0.1** by default (localhost only). Do not expose it to the public internet without authentication.
