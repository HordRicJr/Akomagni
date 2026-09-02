"""Tests for CLI i18n catalog."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.core.i18n import normalize_language, resolve_language, translate

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


def test_normalize_language():
    assert normalize_language("fr") == "fr"
    assert normalize_language("FR-CA") == "fr"
    assert normalize_language("de") == "en"
    assert normalize_language(None) == "en"


def test_translate_english():
    assert "Recommended profile" in translate("doctor.recommended_profile", "en", profile="light")


def test_translate_french():
    assert "Profil recommandé" in translate("doctor.recommended_profile", "fr", profile="light")


def test_resolve_language_from_config():
    assert resolve_language({"language": "fr"}) == "fr"


def test_resolve_language_defaults_to_english():
    assert resolve_language({}) == "en"
    assert resolve_language({"language": None}) == "en"


def test_config_language_invalid(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "language", "de"])
    assert result.exit_code == 1
    assert "Unsupported" in result.stdout or "non supportée" in result.stdout


def test_config_language_show_and_set(akomagni_home):
    runner.invoke(app, ["config", "init"])
    show = runner.invoke(app, ["config", "language"])
    assert show.exit_code == 0
    assert "en" in show.stdout

    set_fr = runner.invoke(app, ["config", "language", "fr"])
    assert set_fr.exit_code == 0

    doctor = runner.invoke(app, ["doctor"])
    assert doctor.exit_code == 0
    assert "Profil recommandé" in doctor.stdout


def test_config_extras_invalid(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["config", "extras", "unknown"])
    assert result.exit_code == 1


def test_extras_alias_invalid(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["extras", "unknown"])
    assert result.exit_code == 1


def test_doctor_english_by_default(akomagni_home):
    runner.invoke(app, ["config", "init"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Recommended profile" in result.stdout
