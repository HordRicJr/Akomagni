"""Tests for domain model router."""

from __future__ import annotations

from pathlib import Path

from akomagni.core.config import DEFAULT_CONFIG
from akomagni.core.router.domain import ModelDomain, classify_domain
from akomagni.core.router.swap import models_match, plan_model_swap, resolve_domain_model
from akomagni.inference.client import InferenceStatus


def test_classify_domain_code():
    result = classify_domain("implémente le endpoint login avec JWT")
    assert result.domain is ModelDomain.CODE


def test_classify_domain_design():
    result = classify_domain("design a landing page in figma")
    assert result.domain is ModelDomain.DESIGN


def test_classify_domain_image():
    result = classify_domain("génère un logo pour mon app")
    assert result.domain is ModelDomain.IMAGE


def test_classify_domain_text():
    result = classify_domain("explique-moi la blockchain")
    assert result.domain is ModelDomain.TEXT


def test_resolve_domain_model_code(tmp_path):
    model = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    model.write_text("gguf", encoding="utf-8")
    plan = resolve_domain_model(
        "fix bug in auth module",
        config=DEFAULT_CONFIG,
        models_dir=tmp_path,
    )
    assert plan.classification.domain is ModelDomain.CODE
    assert plan.catalog_name == "qwen2.5-coder-7b"
    assert plan.model_path == model


def test_resolve_domain_model_image_skips_inference():
    plan = resolve_domain_model(
        "génère une illustration",
        config=DEFAULT_CONFIG,
        models_dir=Path("/tmp"),
    )
    assert plan.skip_inference is True


def test_models_match():
    assert models_match("qwen2.5-coder-7b-instruct-q4_k_m.gguf", "qwen2.5-coder-7b")
    assert not models_match("phi-3.5-mini", "qwen2.5-coder-7b")


def test_plan_model_swap_needed():
    status = InferenceStatus(
        online=True,
        base_url="http://127.0.0.1:8787/v1",
        models=["phi-3.5-mini-instruct-q4.gguf"],
    )
    target = Path("/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf")
    plan = plan_model_swap(
        status=status,
        target_path=target,
        target_model_id=target.name,
    )
    assert plan.needs_swap is True
    assert "Hot-swap required" in plan.hint


def test_classify_domain_empty():
    result = classify_domain("   ")
    assert result.domain is ModelDomain.TEXT


def test_plan_model_swap_offline():
    status = InferenceStatus(online=False, base_url="http://127.0.0.1:8787/v1")
    plan = plan_model_swap(
        status=status,
        target_path=Path("/models/test.gguf"),
        target_model_id="test.gguf",
    )
    assert plan.needs_swap is False
    assert "offline" in plan.hint.lower()


def test_plan_model_swap_already_loaded():
    status = InferenceStatus(
        online=True,
        base_url="http://127.0.0.1:8787/v1",
        models=["qwen2.5-coder-7b-instruct-q4_k_m.gguf"],
    )
    target = Path("/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf")
    plan = plan_model_swap(
        status=status,
        target_path=target,
        target_model_id=target.name,
    )
    assert plan.needs_swap is False
