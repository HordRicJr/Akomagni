"""Tests for RAG context injection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from akomagni.flow.intent import classify_message
from akomagni.inference.chat import build_flow_system_prompt, try_chat_with_inference
from akomagni.inference.client import InferenceStatus
from akomagni.rag.context import format_rag_context, retrieve_rag_context
from akomagni.rag.ingest import ingest_text
from akomagni.rag.query import QueryHit
from akomagni.rag.store import init_store
from akomagni.skills.runner import build_context_env

pytest.importorskip("sqlite_vec")


@pytest.fixture
def rag_db(tmp_path):
    db_path = tmp_path / "rag" / "index.db"
    init_store(db_path)
    return db_path


def test_format_rag_context_empty():
    assert format_rag_context([]) == ""


def test_format_rag_context_with_hits():
    hits = [
        QueryHit(
            chunk_id=1,
            source="docs/api.md",
            content="Use JWT for authentication.",
            score=0.5,
            bm25_rank=1,
            vector_rank=2,
        )
    ]
    text = format_rag_context(hits)
    assert "Retrieved context" in text
    assert "JWT" in text
    assert "docs/api.md" in text


def test_retrieve_rag_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".akomagni" / "rag" / "index.db"
    init_store(db_path)
    ingest_text(
        "Always validate JWT tokens on protected routes.",
        source="auth.md",
        db_path=db_path,
    )
    context = retrieve_rag_context("JWT validation", project=True)
    assert "JWT" in context


def test_retrieve_rag_context_missing_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert retrieve_rag_context("anything", project=True) == ""


def test_build_flow_system_prompt_with_rag():
    decision = classify_message("implement login API")
    prompt = build_flow_system_prompt(
        decision,
        rag_context="## Retrieved context\n\nUse bcrypt for passwords.",
    )
    assert "Retrieved context" in prompt
    assert "bcrypt" in prompt


def test_build_context_env_rag():
    env = build_context_env(
        message="hello",
        central_context="",
        project_context="",
        rag_context="RAG chunk",
    )
    assert env["AKOMAGNI_RAG_CONTEXT"] == "RAG chunk"


def test_try_chat_with_inference_passes_rag_context():
    decision = classify_message("implement login API")
    with (
        patch(
            "akomagni.inference.chat.check_health",
            return_value=InferenceStatus(
                online=True,
                base_url="http://127.0.0.1:8787/v1",
                models=["local"],
            ),
        ),
        patch("akomagni.inference.chat.chat_completion", return_value="ok") as chat,
    ):
        try_chat_with_inference(
            "implement login",
            decision,
            rag_context="## Retrieved context\n\nJWT rules.",
        )
    assert "JWT rules" in chat.call_args.kwargs["system_prompt"]
