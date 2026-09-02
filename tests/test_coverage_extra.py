"""Discovery, registry, state, and doctor edge cases."""

from unittest.mock import MagicMock, patch

from akomagni.core.doctor.scan import _detect_gpu, _recommend_profile
from akomagni.core.project import find_project_root, resolve_workspace_root, skill_search_roots
from akomagni.core.registry.models import recommend_models
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import load_state, record_invocation, save_state, workflow_dir
from akomagni.skills.discovery import discover_skills, find_skill


def test_recommend_profile_standard():
    assert _recommend_profile(16, None) == "standard"


def test_recommend_profile_vram():
    assert _recommend_profile(8, 16) == "power"


def test_detect_gpu_with_nvidia_smi():
    mock_result = MagicMock(returncode=0, stdout="NVIDIA RTX, 8192\n")
    with (
        patch("akomagni.core.doctor.scan.shutil.which", return_value="/usr/bin/nvidia-smi"),
        patch("subprocess.run", return_value=mock_result),
    ):
        gpu = _detect_gpu()
    assert gpu["name"] == "NVIDIA RTX"
    assert gpu["backend"] == "cuda"


def test_detect_gpu_not_found():
    with patch("akomagni.core.doctor.scan.shutil.which", return_value=None):
        assert _detect_gpu()["name"] is None


def test_recommend_models():
    rec = recommend_models()
    assert "profile" in rec
    assert "models" in rec


def test_discover_from_skill_md(tmp_path, monkeypatch):
    root = tmp_path / "skills-root"
    skill = root / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: test skill\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("akomagni.skills.discovery.skill_search_roots", lambda _=None: [root])
    found = discover_skills()
    assert "my-skill" in found


def test_discover_from_manifest(tmp_path):
    bmad = tmp_path / "_bmad" / "_config"
    bmad.mkdir(parents=True)
    skill_path = tmp_path / "_bmad" / "core" / "demo-skill"
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    manifest = bmad / "skill-manifest.csv"
    manifest.write_text(
        "canonicalId,name,description,module,path\n"
        ',demo-skill,"Demo skill",core,_bmad/core/demo-skill/SKILL.md\n',
        encoding="utf-8",
    )
    found = discover_skills(tmp_path)
    assert "demo-skill" in found
    assert find_skill("demo-skill", tmp_path) is not None


def test_find_project_root(tmp_path):
    (tmp_path / "_bmad").mkdir()
    assert find_project_root(tmp_path) == tmp_path


def test_workflow_dir_uses_central_when_no_project(tmp_path, monkeypatch):
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    assert workflow_dir(None, discover=False) == home / "workflow"


def test_skill_search_roots_includes_global(tmp_path, monkeypatch):
    global_skills = tmp_path / "global-skills"
    global_skills.mkdir()
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", global_skills)
    (tmp_path / "_bmad").mkdir()
    roots = skill_search_roots(tmp_path)
    assert global_skills in roots


def test_workflow_state_roundtrip(tmp_path):
    state = {"phase": "plan", "gates": {"brainstorm": "in_progress"}}
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded["phase"] == "plan"


def test_record_invocation_updates_state(tmp_path):
    session = tmp_path / ".akomagni" / "workflow" / "sessions" / "test.md"
    session.parent.mkdir(parents=True)
    session.write_text("session", encoding="utf-8")
    record_invocation(
        agent_id="bmad-agent-analyst",
        skill_id="bmad-brainstorming",
        session_path=session,
        project_root=tmp_path,
    )
    state = load_state(tmp_path)
    assert state["active_agent"] == "bmad-agent-analyst"
    assert state["gates"]["brainstorm"] == "in_progress"


def test_route_message_forces_brainstorm_on_greenfield(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    decision = route_message("je veux une app de budget")
    assert decision.skill == "bmad-brainstorming"


def test_is_greenfield_skips_when_brainstorm_complete(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    wf = tmp_path / ".akomagni" / "workflow"
    wf.mkdir(parents=True)
    (wf / "state.yaml").write_text("gates:\n  brainstorm: complete\n", encoding="utf-8")
    from akomagni.flow.orchestrator import _is_greenfield

    assert _is_greenfield("je veux créer une app") is False


def test_is_greenfield_skips_when_memlog_exists(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    brainstorm = tmp_path / ".akomagni" / "workflow" / "brainstorm" / "session1"
    brainstorm.mkdir(parents=True)
    (brainstorm / ".memlog.md").write_text("done", encoding="utf-8")
    from akomagni.flow.orchestrator import _is_greenfield

    assert _is_greenfield("nouveau projet") is False


def test_load_workflow_state_from_file(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    wf = tmp_path / ".akomagni" / "workflow"
    wf.mkdir(parents=True)
    (wf / "state.yaml").write_text("phase: plan\n", encoding="utf-8")

    assert load_state(tmp_path)["phase"] == "plan"


def test_route_message_greenfield(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    decision = route_message("je veux créer une nouvelle app")
    assert decision.skill == "bmad-brainstorming"


def test_load_state_missing_file(tmp_path):
    state = load_state(tmp_path)
    assert state["phase"] == "anytime"
