"""SQLite + FTS5 + sqlite-vec storage for RAG."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from akomagni.rag.embed import DEFAULT_EMBED_DIM

_SCHEMA_VERSION = 1


class RagStoreError(RuntimeError):
    """Raised when the RAG store cannot be opened or initialized."""


def default_index_path(*, project: bool = False, project_root: Path | None = None) -> Path:
    if project:
        root = project_root or Path.cwd()
        return root / ".akomagni" / "rag" / "index.db"
    from akomagni.core.config import DATA_DIR

    return DATA_DIR / "rag" / "index.db"


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec
    except ImportError as exc:
        raise RagStoreError(
            "sqlite-vec is required for RAG — install with: pip install sqlite-vec"
        ) from exc
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)


def init_store(db_path: Path, *, embed_dim: int = DEFAULT_EMBED_DIM) -> Path:
    """Create or migrate the RAG index database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _load_sqlite_vec(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current < _SCHEMA_VERSION:
            _create_schema(conn, embed_dim=embed_dim)
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            conn.commit()
    finally:
        conn.close()
    return db_path


def _create_schema(conn: sqlite3.Connection, *, embed_dim: int) -> None:
    if embed_dim <= 0 or embed_dim > 4096:
        raise ValueError("embed_dim must be between 1 and 4096")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            UNIQUE(source_id, chunk_index)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            content='chunks',
            content_rowid='id',
            tokenize='unicode61'
        );
        """
    )
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
            chunk_id INTEGER PRIMARY KEY,
            embedding float[{embed_dim}]
        );
        """
    )
    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )


@contextmanager
def open_store(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a RAG database connection with sqlite-vec loaded."""
    init_store(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _load_sqlite_vec(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


def store_status(db_path: Path) -> dict[str, int | str]:
    """Return basic counts for CLI status output."""
    if not db_path.exists():
        return {"path": str(db_path), "sources": 0, "chunks": 0}
    with open_store(db_path) as conn:
        sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"path": str(db_path), "sources": sources, "chunks": chunks}
