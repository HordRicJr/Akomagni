"""Memory and inference module tests."""

from akomagni.inference.server import serve_stub
from akomagni.memory.inject import load_central_context, load_project_context
from akomagni.memory.store import memory_status, project_memory_dir


def test_project_memory_dir(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    assert project_memory_dir() == tmp_path / ".akomagni" / "memory"


def test_memory_status_with_project(tmp_path, monkeypatch):
    home = tmp_path / "home"
    memory = home / "memory"
    memory.mkdir(parents=True)
    (memory / "profile.md").write_text("# profile", encoding="utf-8")
    (memory / "preferences.yaml").write_text("language: fr\n", encoding="utf-8")
    (memory / "stacks").mkdir()

    monkeypatch.setattr("akomagni.memory.store.MEMORY_DIR", memory)
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    proj = tmp_path / ".akomagni" / "memory"
    proj.mkdir(parents=True)
    (proj / "notes.md").write_text("decision", encoding="utf-8")

    text = memory_status(lang="fr")
    assert "✓" in text
    assert "entrées" in text


def test_load_central_context(tmp_path, monkeypatch):
    memory = tmp_path / "memory"
    stacks = memory / "stacks"
    stacks.mkdir(parents=True)
    (memory / "profile.md").write_text("Assou", encoding="utf-8")
    (memory / "preferences.yaml").write_text("language: fr\n", encoding="utf-8")
    (stacks / "web.md").write_text("Next.js", encoding="utf-8")
    monkeypatch.setattr("akomagni.memory.inject.MEMORY_DIR", memory)

    ctx = load_central_context()
    assert "Assou" in ctx
    assert "Next.js" in ctx


def test_load_project_context_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_project_context() == ""


def test_load_project_context_with_files(tmp_path, monkeypatch):
    (tmp_path / "_bmad").mkdir()
    monkeypatch.chdir(tmp_path)
    proj = tmp_path / ".akomagni" / "memory"
    proj.mkdir(parents=True)
    (proj / "decisions.md").write_text("use JWT", encoding="utf-8")
    assert "JWT" in load_project_context()


def test_serve_stub(capsys):
    serve_stub(host="127.0.0.1", port=9999)
    captured = capsys.readouterr()
    assert "9999" in captured.out
