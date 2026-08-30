from akomagni.core.doctor.scan import _recommend_profile, run_doctor
from akomagni.flow.orchestrator import route_message


def test_recommend_profile_power():
    assert _recommend_profile(32, 16) == "power"


def test_recommend_profile_light():
    assert _recommend_profile(8, None) == "light"


def test_doctor_returns_profile():
    report = run_doctor()
    assert report["profile"] in {"light", "standard", "power"}
    assert "ram_total_gb" in report


def test_flow_routes_brainstorm():
    d = route_message("J'ai une idée pour une nouvelle app de budget")
    assert d.skill == "bmad-brainstorming"
    assert d.greenfield is True


def test_flow_routes_dev(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = route_message("Implémente le endpoint login avec JWT")
    assert d.agent_id == "bmad-agent-dev"
