"""Offline text embeddings for RAG indexing and query."""

from __future__ import annotations

import hashlib
import math
import re

DEFAULT_EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def embed_text(text: str, *, dim: int = DEFAULT_EMBED_DIM) -> list[float]:
    """Deterministic bag-of-hashes embedding (offline, no model required)."""
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return vec

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0:
        return vec
    return [value / norm for value in vec]


def serialize_embedding(values: list[float]) -> bytes:
    """Pack floats for sqlite-vec blob storage."""
    import struct

    return struct.pack(f"{len(values)}f", *values)
