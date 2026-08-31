"""Config module tests."""

from akomagni.core.config import ensure_default_config, load_config


def test_ensure_default_config_creates_files(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")

    path = ensure_default_config()
    assert path.is_file()
    assert (home / "memory" / "profile.md").is_file()
    assert (home / "memory" / "stacks" / "design.md").is_file()


def test_load_config_merges_defaults(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")

    ensure_default_config()
    cfg = load_config()
    assert cfg["router"]["mode"] == "auto"
    assert cfg["router"]["domains"]["code"] == "qwen2.5-coder-7b"
    assert "models" in cfg
