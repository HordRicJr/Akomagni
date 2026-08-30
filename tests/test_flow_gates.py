"""Tests for bmad-help.csv catalog and workflow gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from akomagni.flow.gates import apply_workflow_gates, check_skill_gates
from akomagni.flow.help_catalog import clear_help_catalog_cache, load_help_catalog, parse_help_csv
from akomagni.flow.intent import classify_message
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import save_state


@pytest.fixture
def bmad_project(tmp_path):
    config = tmp_path / "_bmad" / "_config"
    config.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "bmad-help.csv"
    (config / "bmad-help.csv").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    clear_help_catalog_cache()
    yield tmp_path
    clear_help_catalog_cache()


def test_parse_help_csv_fixture():
    catalog = parse_help_csv(Path(__file__).parent / "fixtures" / "bmad-help.csv")
    assert "bmad-prd" in catalog
    assert catalog["bmad-prd"].preceded_by == ("bmad-product-brief",)
    assert catalog["bmad-prd"].required is True


def test_load_help_catalog_from_project(bmad_project):
    catalog = load_help_catalog(bmad_project)
    assert "bmad-build" in catalog
    assert catalog["bmad-build"].preceded_by == ("bmad-sprint-planning",)


def test_gate_blocks_prd_without_brief(bmad_project, monkeypatch):
    monkeypatch.chdir(bmad_project)
    gate = check_skill_gates("bmad-prd", project_root=bmad_project)
    assert gate.allowed is False
    assert gate.missing_prerequisites == ("bmad-product-brief",)


def test_gate_allows_prd_with_brief_completed(bmad_project, monkeypatch):
    monkeypatch.chdir(bmad_project)
    save_state({"completed": ["bmad-product-brief"]}, bmad_project)
    gate = check_skill_gates("bmad-prd", project_root=bmad_project)
    assert gate.allowed is True


def test_apply_workflow_gates_redirects_to_prerequisite(bmad_project, monkeypatch):
    monkeypatch.chdir(bmad_project)
    decision = classify_message("écris le prd")
    assert decision.skill == "bmad-prd"
    redirected = apply_workflow_gates(decision, project_root=bmad_project)
    assert redirected.skill == "bmad-product-brief"
    assert "Gate BMAD" in redirected.hint


def test_route_message_applies_gates(bmad_project, monkeypatch):
    monkeypatch.chdir(bmad_project)
    (bmad_project / ".akomagni" / "workflow" / "brainstorm").mkdir(parents=True)
    (bmad_project / ".akomagni" / "workflow" / "state.yaml").write_text(
        "gates:\n  brainstorm: complete\n",
        encoding="utf-8",
    )
    decision = route_message("écris le prd", project_root=bmad_project)
    assert decision.skill == "bmad-product-brief"
