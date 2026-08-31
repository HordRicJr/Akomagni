"""Akomagni RAG — hybrid BM25 + vector retrieval (sqlite-vec)."""

from akomagni.rag.context import retrieve_rag_context
from akomagni.rag.ingest import IngestResult, ingest_path, ingest_text
from akomagni.rag.query import QueryHit, hybrid_query

__all__ = [
    "IngestResult",
    "QueryHit",
    "hybrid_query",
    "ingest_path",
    "ingest_text",
    "retrieve_rag_context",
]
