"""Retrieve and format RAG context for Flow and inference."""

from __future__ import annotations

from pathlib import Path

from akomagni.rag.query import QueryHit, hybrid_query
from akomagni.rag.store import default_index_path


def format_rag_context(hits: list[QueryHit]) -> str:
    """Turn retrieval hits into a markdown block for prompt injection."""
    if not hits:
        return ""
    sections: list[str] = ["## Retrieved context (RAG)", ""]
    for index, hit in enumerate(hits, start=1):
        sections.extend(
            [
                f"### Source {index}: {hit.source}",
                "",
                hit.content.strip(),
                "",
            ]
        )
    return "\n".join(sections).strip()


def retrieve_rag_context(
    query: str,
    *,
    project: bool = True,
    project_root: Path | None = None,
    limit: int = 3,
    rrf_k: int = 60,
) -> str:
    """Run hybrid search and return formatted context (empty when no index/hits)."""
    cleaned = query.strip()
    if not cleaned:
        return ""
    db_path = default_index_path(project=project, project_root=project_root)
    if not db_path.exists():
        if project:
            db_path = default_index_path(project=False)
        if not db_path.exists():
            return ""
    hits = hybrid_query(cleaned, db_path=db_path, limit=limit, rrf_k=rrf_k)
    return format_rag_context(hits)
