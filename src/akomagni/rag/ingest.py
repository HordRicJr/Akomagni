"""Document ingestion into the RAG index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from akomagni.rag.chunk import chunk_text
from akomagni.rag.embed import embed_text, serialize_embedding
from akomagni.rag.store import RagStoreError, open_store

_TEXT_SUFFIXES = {".md", ".txt", ".rst", ".py", ".yaml", ".yml", ".json"}


class RagIngestError(ValueError):
    """Raised when ingestion input is invalid."""


@dataclass(frozen=True)
class IngestResult:
    source: str
    chunks_added: int
    chunks_replaced: int


def ingest_text(
    text: str,
    *,
    source: str,
    db_path: Path,
    chunk_size: int = 800,
    overlap: int = 120,
) -> IngestResult:
    """Index a text blob under a logical source id (path or label)."""
    content = text.strip()
    if not content:
        raise RagIngestError("text must not be empty")
    if not source.strip():
        raise RagIngestError("source label must not be empty")

    pieces = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    if not pieces:
        raise RagIngestError("no chunks produced from text")

    return _write_chunks(source.strip(), pieces, db_path=db_path)


def ingest_path(
    path: Path,
    *,
    db_path: Path,
    chunk_size: int = 800,
    overlap: int = 120,
    recursive: bool = False,
) -> list[IngestResult]:
    """Index one file or all text files in a directory."""
    target = path.resolve()
    if not target.exists():
        raise RagIngestError(f"path not found: {target}")

    if target.is_file():
        return [_ingest_file(target, db_path=db_path, chunk_size=chunk_size, overlap=overlap)]

    if not target.is_dir():
        raise RagIngestError(f"not a file or directory: {target}")

    results: list[IngestResult] = []
    iterator = target.rglob("*") if recursive else target.glob("*")
    for child in sorted(iterator):
        if not child.is_file():
            continue
        if child.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        results.append(_ingest_file(child, db_path=db_path, chunk_size=chunk_size, overlap=overlap))
    if not results:
        raise RagIngestError(f"no ingestible text files under {target}")
    return results


def _ingest_file(
    path: Path,
    *,
    db_path: Path,
    chunk_size: int,
    overlap: int,
) -> IngestResult:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RagIngestError(f"cannot decode file as utf-8: {path}") from exc
    return ingest_text(
        text,
        source=str(path),
        db_path=db_path,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def _write_chunks(source: str, pieces: list[str], *, db_path: Path) -> IngestResult:
    stamp = datetime.now(UTC).isoformat()
    replaced = 0
    with open_store(db_path) as conn:
        existing = conn.execute("SELECT id FROM sources WHERE path = ?", (source,)).fetchone()
        if existing:
            source_id = existing["id"]
            replaced = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE source_id = ?", (source_id,)
            ).fetchone()[0]
            chunk_ids = [
                row["id"]
                for row in conn.execute("SELECT id FROM chunks WHERE source_id = ?", (source_id,))
            ]
            for chunk_id in chunk_ids:
                conn.execute("DELETE FROM chunks_vec WHERE chunk_id = ?", (chunk_id,))
            conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            conn.execute("UPDATE sources SET ingested_at = ? WHERE id = ?", (stamp, source_id))
        else:
            cursor = conn.execute(
                "INSERT INTO sources(path, ingested_at) VALUES (?, ?)",
                (source, stamp),
            )
            source_id = cursor.lastrowid

        for index, piece in enumerate(pieces):
            cursor = conn.execute(
                "INSERT INTO chunks(source_id, chunk_index, content) VALUES (?, ?, ?)",
                (source_id, index, piece),
            )
            chunk_id = cursor.lastrowid
            if chunk_id is None:
                raise RagStoreError("failed to insert chunk")
            embedding = serialize_embedding(embed_text(piece))
            conn.execute(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embedding),
            )
        conn.commit()

    return IngestResult(source=source, chunks_added=len(pieces), chunks_replaced=replaced)
