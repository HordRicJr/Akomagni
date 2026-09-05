"""--project workspace must not inherit a parent BMAD checkout (e.g. Money)."""

from __future__ import annotations

from akomagni.core.project import (
    find_akomagni_workspace,
    find_project_root,
    resolve_bmad_project_root,
    resolve_workspace_root,
)
from akomagni.skills.invoke import invoke_skill


def test_isolated_project_does_not_inherit_parent_bmad(tmp_path, monkeypatch):
    money = tmp_path / "Money"
    (money / "_bmad").mkdir(parents=True)
    (money / ".akomagni").mkdir(parents=True)
    app = money / "app_test"
    (app / ".akomagni" / "workflow").mkdir(parents=True)

    monkeypatch.chdir(app)
    assert find_akomagni_workspace() == app.resolve()
    assert find_project_root() is None
    root, is_project = resolve_workspace_root()
    assert root == app.resolve()
    assert is_project is True


def test_resolve_bmad_ignores_isolated_project_and_configured_parent(tmp_path, monkeypatch):
    money = tmp_path / "Money"
    (money / "_bmad").mkdir(parents=True)
    app = money / "app_test"
    (app / ".akomagni").mkdir(parents=True)
    kernel = tmp_path / "kernel"
    (kernel / "_bmad").mkdir(parents=True)

    monkeypatch.setattr("akomagni.core.project.configured_bmad_root", lambda: money.resolve())
    monkeypatch.setattr(
        "akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: kernel.resolve()
    )

    # Explicit --project without _bmad must not become BMAD root / Money.
    assert resolve_bmad_project_root(app) == kernel.resolve()
    assert resolve_bmad_project_root(app) != money.resolve()


def test_invoke_stores_sessions_in_project_not_parent(tmp_path, monkeypatch):
    money = tmp_path / "Money"
    (money / "_bmad").mkdir(parents=True)
    (money / ".akomagni").mkdir(parents=True)
    app = money / "app_test"
    app.mkdir(parents=True)
    home = tmp_path / "akomagni-home"
    home.mkdir()
    monkeypatch.setattr("akomagni.core.config.DATA_DIR", home)
    monkeypatch.setattr("akomagni.core.config.CONFIG_PATH", home / "config.yaml")
    monkeypatch.setattr("akomagni.core.config.MEMORY_DIR", home / "memory")
    monkeypatch.setattr("akomagni.core.config.MODELS_DIR", home / "models")
    monkeypatch.setattr("akomagni.core.config.SKILLS_DIR", home / "skills")
    monkeypatch.setattr("akomagni.core.bmad_kernel.find_shipped_bmad_core", lambda: None)
    monkeypatch.setattr("akomagni.core.bmad_kernel.ensure_bmad_kernel", lambda **_: None)
    monkeypatch.chdir(app)

    result = invoke_skill("help me brainstorm a budget app", project_root=app)
    assert result.project_root == app.resolve()
    assert result.session_path.is_relative_to(app.resolve())
    assert not result.session_path.is_relative_to(money.resolve() / ".akomagni")


def test_bmad_root_still_found_inside_real_bmad_tree(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    (root / "_bmad").mkdir(parents=True)
    (root / ".akomagni").mkdir(parents=True)
    nested = root / "src"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert find_project_root() == root.resolve()
    assert find_akomagni_workspace() == root.resolve()
