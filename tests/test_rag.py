"""Tests for RAG ingest and hybrid query."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.rag.chunk import chunk_text
from akomagni.rag.embed import embed_text
from akomagni.rag.ingest import RagIngestError, ingest_path, ingest_text
from akomagni.rag.query import hybrid_query
from akomagni.rag.store import init_store, store_status

pytest.importorskip("sqlite_vec")

runner = CliRunner()


@pytest.fixture
def akomagni_home(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    return home


@pytest.fixture
def rag_db(tmp_path):
    db_path = tmp_path / "rag" / "index.db"
    init_store(db_path)
    return db_path


def test_chunk_text_overlap():
    text = "alpha " * 200
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_embed_text_normalized():
    vec = embed_text("akomagni rag hybrid search")
    assert len(vec) == 384
    norm = sum(value * value for value in vec) ** 0.5
    assert norm == pytest.approx(1.0, rel=1e-5)


def test_ingest_and_hybrid_query(rag_db):
    ingest_text(
        "Akomagni uses BMAD skills for orchestration.\n\nOffline RAG with sqlite-vec.",
        source="notes.md",
        db_path=rag_db,
    )
    hits = hybrid_query("BMAD orchestration", db_path=rag_db, limit=3)
    assert hits
    assert any("BMAD" in hit.content for hit in hits)


def test_ingest_path_directory(rag_db, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.md").write_text("# One\n\nJWT authentication pattern.\n", encoding="utf-8")
    (docs / "two.txt").write_text(
        "SQLite FTS5 and sqlite-vec hybrid retrieval.\n", encoding="utf-8"
    )

    results = ingest_path(docs, db_path=rag_db)
    assert len(results) == 2
    status = store_status(rag_db)
    assert status["sources"] == 2
    assert status["chunks"] >= 2

    hits = hybrid_query("JWT authentication", db_path=rag_db)
    assert hits
    assert "JWT" in hits[0].content


def test_ingest_replaces_existing_source(rag_db):
    ingest_text("first version about routers", source="doc.md", db_path=rag_db)
    ingest_text("second version about memory capture", source="doc.md", db_path=rag_db)
    status = store_status(rag_db)
    assert status["sources"] == 1
    hits = hybrid_query("memory capture", db_path=rag_db)
    assert hits
    assert "memory capture" in hits[0].content


def test_ingest_empty_raises(rag_db):
    with pytest.raises(RagIngestError, match="empty"):
        ingest_text("   ", source="x.md", db_path=rag_db)


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_embed_text_empty():
    assert embed_text("") == [0.0] * 384
    assert embed_text("!!!") == [0.0] * 384


def test_hybrid_query_empty_and_missing_db(rag_db, tmp_path):
    assert hybrid_query("   ", db_path=rag_db) == []
    missing = tmp_path / "missing.db"
    assert hybrid_query("anything", db_path=missing) == []


def test_ingest_path_errors(tmp_path, rag_db):
    with pytest.raises(RagIngestError, match="not found"):
        ingest_path(tmp_path / "nope", db_path=rag_db)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(RagIngestError, match="no ingestible"):
        ingest_path(empty_dir, db_path=rag_db)


def test_ingest_path_decode_error(rag_db, tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe")
    with pytest.raises(RagIngestError, match="decode"):
        ingest_path(bad, db_path=rag_db)


def test_rag_cli_errors(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    missing = runner.invoke(app, ["rag", "ingest", str(tmp_path / "missing.md")])
    assert missing.exit_code == 1
    assert "Error" in missing.stdout

    no_hits = runner.invoke(app, ["rag", "query", "nothing here", "--project"])
    assert no_hits.exit_code == 1
    assert "No matches" in no_hits.stdout


def test_rag_central_ingest(akomagni_home, tmp_path):
    doc = tmp_path / "central.md"
    doc.write_text("Central memory uses sqlite-vec hybrid retrieval.\n", encoding="utf-8")
    result = runner.invoke(app, ["rag", "ingest", str(doc)])
    assert result.exit_code == 0
    query = runner.invoke(app, ["rag", "query", "sqlite-vec", "--json"])
    assert query.exit_code == 0
    payload = json.loads(query.stdout)
    assert payload[0]["content"]


def test_chunk_multiparagraph():
    p1 = "alpha " * 80
    p2 = "beta " * 80
    chunks = chunk_text(f"{p1}\n\n{p2}", chunk_size=120, overlap=20)
    assert len(chunks) >= 2


def test_ingest_empty_source(rag_db):
    with pytest.raises(RagIngestError, match="source label"):
        ingest_text("hello", source="  ", db_path=rag_db)


def test_ingest_recursive_directory(rag_db, tmp_path):
    nested = tmp_path / "docs" / "nested"
    nested.mkdir(parents=True)
    (nested / "deep.md").write_text(
        "Recursive ingest finds nested markdown files.\n", encoding="utf-8"
    )
    results = ingest_path(tmp_path / "docs", db_path=rag_db, recursive=True)
    assert len(results) == 1
    hits = hybrid_query("nested markdown", db_path=rag_db)
    assert hits


def test_hybrid_query_punctuation_only(rag_db):
    ingest_text("keyword anchor document", source="x.md", db_path=rag_db)
    hits = hybrid_query("!!!", db_path=rag_db)
    assert isinstance(hits, list)


def test_bm25_search_sql_error():
    import sqlite3

    from akomagni.rag.query import _bm25_search

    class BadConn:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("fts failed")

    assert _bm25_search(BadConn(), "test", limit=5) == []


def test_store_import_error(monkeypatch):
    import builtins
    import sys

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sqlite_vec":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("sqlite_vec", None)
    from akomagni.rag.store import RagStoreError, init_store

    with pytest.raises(RagStoreError, match="sqlite-vec"):
        init_store(Path("test-import-error.db"))


def test_rag_cli_status_and_query(akomagni_home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status = runner.invoke(app, ["rag", "status"])
    assert status.exit_code == 0
    assert "Sources" in status.stdout
    assert "0" in status.stdout
    doc = tmp_path / "guide.md"
    doc.write_text("Akomagni Flow routes messages to BMAD agents.\n", encoding="utf-8")
    ingest = runner.invoke(app, ["rag", "ingest", str(doc), "--project"])
    assert ingest.exit_code == 0
    assert "Indexed" in ingest.stdout

    query = runner.invoke(app, ["rag", "query", "BMAD agents", "--project", "--json"])
    assert query.exit_code == 0
    payload = json.loads(query.stdout)
    assert payload
    assert "BMAD" in payload[0]["content"]
