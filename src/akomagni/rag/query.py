"""Hybrid BM25 + vector retrieval with reciprocal rank fusion."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from akomagni.rag.embed import embed_text, serialize_embedding
from akomagni.rag.store import open_store

_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class QueryHit:
    chunk_id: int
    source: str
    content: str
    score: float
    bm25_rank: int | None
    vector_rank: int | None


def hybrid_query(
    query: str,
    *,
    db_path: Path,
    limit: int = 5,
    rrf_k: int = 60,
) -> list[QueryHit]:
    """Run FTS5 + sqlite-vec search and fuse rankings with RRF."""
    cleaned = query.strip()
    if not cleaned:
        return []
    if not db_path.exists():
        return []

    fts_query = _fts_query(cleaned)
    query_embedding = serialize_embedding(embed_text(cleaned))

    with open_store(db_path) as conn:
        bm25_rows = _bm25_search(conn, fts_query, limit=limit * 10)
        vector_rows = _vector_search(conn, query_embedding, limit=limit * 10)
        return _fuse_results(conn, bm25_rows, vector_rows, limit=limit, rrf_k=rrf_k)


def _fts_query(text: str) -> str:
    tokens = _FTS_TOKEN_RE.findall(text)
    if not tokens:
        return text
    return " OR ".join(f'"{token}"' for token in tokens[:12])


def _bm25_search(conn, fts_query: str, *, limit: int) -> list[tuple[int, int]]:
    try:
        rows = conn.execute(
            """
            SELECT rowid AS chunk_id, rank
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
    except sqlite3.Error:
        return []
    ranked: list[tuple[int, int]] = []
    for index, row in enumerate(rows, start=1):
        ranked.append((int(row["chunk_id"]), index))
    return ranked


def _vector_search(conn, query_embedding: bytes, *, limit: int) -> list[tuple[int, int]]:
    rows = conn.execute(
        """
        SELECT chunk_id, distance
        FROM chunks_vec
        WHERE embedding MATCH ?
          AND k = ?
        ORDER BY distance
        """,
        (query_embedding, limit),
    ).fetchall()
    ranked: list[tuple[int, int]] = []
    for index, row in enumerate(rows, start=1):
        ranked.append((int(row["chunk_id"]), index))
    return ranked


def _fuse_results(
    conn,
    bm25_rows: list[tuple[int, int]],
    vector_rows: list[tuple[int, int]],
    *,
    limit: int,
    rrf_k: int,
) -> list[QueryHit]:
    scores: dict[int, float] = {}
    bm25_rank: dict[int, int] = {}
    vector_rank: dict[int, int] = {}

    for chunk_id, rank in bm25_rows:
        bm25_rank[chunk_id] = rank
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for chunk_id, rank in vector_rows:
        vector_rank[chunk_id] = rank
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)

    if not scores:
        return []

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    hits: list[QueryHit] = []
    for chunk_id, score in ordered:
        row = conn.execute(
            """
            SELECT chunks.id, chunks.content, sources.path AS source
            FROM chunks
            JOIN sources ON sources.id = chunks.source_id
            WHERE chunks.id = ?
            """,
            (chunk_id,),
        ).fetchone()
        if row is None:
            continue
        hits.append(
            QueryHit(
                chunk_id=int(row["id"]),
                source=str(row["source"]),
                content=str(row["content"]),
                score=score,
                bm25_rank=bm25_rank.get(chunk_id),
                vector_rank=vector_rank.get(chunk_id),
            )
        )
    return hits


def hits_to_json(hits: list[QueryHit]) -> str:
    """Serialize query hits for machine-readable CLI output."""
    payload = [
        {
            "chunk_id": hit.chunk_id,
            "source": hit.source,
            "score": round(hit.score, 6),
            "bm25_rank": hit.bm25_rank,
            "vector_rank": hit.vector_rank,
            "content": hit.content,
        }
        for hit in hits
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)
