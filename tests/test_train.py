"""Tests for Akomagni Train (dataset export + native QLoRA runner)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from akomagni.cli.main import app
from akomagni.train.lora import (
    TrainError,
    build_train_plan,
    export_jsonl,
    prepare_train_bundle,
)
from akomagni.train.models import requires_gpu, resolve_hf_train_model
from akomagni.train.runner import TrainResult, execute_training, load_train_yaml, run_train

runner = CliRunner()


def _seed_learnings(tmp_path) -> None:
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "note.md").write_text(
        "# Pytest rule\n\nAlways use pytest for Python tests.\n", encoding="utf-8"
    )


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


def test_build_train_plan_requires_learnings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TrainError, match="No memory learnings"):
        build_train_plan()


def test_build_train_plan_with_project_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="qwen2.5-coder-7b")
    assert plan.base_model == "qwen2.5-coder-7b"
    assert any("learnings" in s for s in plan.dataset_sources)


def test_export_jsonl_writes_chat_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan()
    dataset_path, count = export_jsonl(plan)
    assert count == 1
    assert dataset_path.is_file()
    row = json.loads(dataset_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["messages"][0]["role"] == "user"
    assert "Pytest rule" in row["messages"][0]["content"]
    assert "pytest" in row["messages"][1]["content"].lower()


def test_prepare_train_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan()
    bundle = prepare_train_bundle(plan)
    assert bundle.example_count == 1
    assert bundle.dataset_path.is_file()
    assert bundle.config_path.is_file()
    assert bundle.readme_path.is_file()
    config = yaml.safe_load(bundle.config_path.read_text(encoding="utf-8"))
    assert config["base_model"] == plan.base_model
    assert config["method"] == "qlora"
    assert config["hf_model_id"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert "akomagni train run" in bundle.readme_path.read_text(encoding="utf-8")


def test_resolve_hf_train_model_catalog_and_direct():
    assert resolve_hf_train_model("qwen2.5-coder-7b") == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert resolve_hf_train_model("phi-3.5-mini") == "microsoft/Phi-3.5-mini-instruct"
    assert resolve_hf_train_model("org/custom-model") == "org/custom-model"
    with pytest.raises(TrainError, match="No Transformers base mapping"):
        resolve_hf_train_model("not-a-real-model")
    with pytest.raises(TrainError, match="empty"):
        resolve_hf_train_model("   ")
    assert requires_gpu("qwen2.5-coder-7b") is True
    assert requires_gpu("phi-3.5-mini") is False


def test_load_train_yaml_errors(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(TrainError, match="Missing train config"):
        load_train_yaml(missing)
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(TrainError, match="Invalid train.yaml"):
        load_train_yaml(bad)


def _fake_stack(*, cuda: bool = False) -> dict:
    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return cuda

    torch = SimpleNamespace(cuda=FakeCuda(), float16="fp16", float32="fp32")

    class FakeTokenizer:
        pad_token = None
        eos_token = "</s>"

        @classmethod
        def from_pretrained(cls, *_a, **_k):
            return cls()

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        def save_pretrained(self, path: str) -> None:
            Path(path).mkdir(parents=True, exist_ok=True)
            (Path(path) / "tokenizer.json").write_text("{}", encoding="utf-8")

    class FakeModel:
        @classmethod
        def from_pretrained(cls, *_a, **_k):
            return cls()

    class FakeDataset(list):
        def map(self, fn):
            return FakeDataset(fn(row) for row in self)

    def load_dataset(*_a, **_k):
        return FakeDataset(
            [
                {
                    "messages": [
                        {"role": "user", "content": "hi"},
                        {"role": "assistant", "content": "hello"},
                    ]
                }
            ]
        )

    class FakeTrainer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def train(self):
            return None

        def save_model(self, path: str) -> None:
            Path(path).mkdir(parents=True, exist_ok=True)
            (Path(path) / "adapter_config.json").write_text("{}", encoding="utf-8")

    return {
        "torch": torch,
        "load_dataset": load_dataset,
        "LoraConfig": lambda **kwargs: kwargs,
        "get_peft_model": lambda model, _cfg: model,
        "prepare_model_for_kbit_training": lambda model: model,
        "AutoModelForCausalLM": FakeModel,
        "AutoTokenizer": FakeTokenizer,
        "BitsAndBytesConfig": lambda **kwargs: kwargs,
        "SFTConfig": lambda **kwargs: kwargs,
        "SFTTrainer": FakeTrainer,
    }


def test_run_train_success_mocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="phi-3.5-mini")
    result = run_train(plan, stack=_fake_stack(cuda=False))
    assert isinstance(result, TrainResult)
    assert result.method == "lora"
    assert result.hf_model_id == "microsoft/Phi-3.5-mini-instruct"
    assert result.adapter_dir.is_dir()
    assert (result.adapter_dir / "adapter_config.json").is_file()


def test_run_train_requires_gpu_for_large_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="qwen2.5-coder-7b")
    with pytest.raises(TrainError, match="CUDA GPU"):
        run_train(plan, stack=_fake_stack(cuda=False))


def test_run_train_missing_extras(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="phi-3.5-mini")

    def _boom():
        raise TrainError(
            "Training requires the optional 'train' extra "
            "(missing dependency: peft).\n"
            "Install with: pip install 'akomagni[train]' "
            "(or: akomagni config extras train)"
        )

    monkeypatch.setattr("akomagni.train.runner.import_train_stack", _boom)
    with pytest.raises(TrainError, match="akomagni\\[train\\]"):
        run_train(plan)


def test_missing_train_extra_message():
    from akomagni.train.runner import _missing_train_extra

    err = _missing_train_extra(ImportError("x", name="peft"))
    assert "akomagni[train]" in str(err)
    assert "peft" in str(err)


def test_collect_examples_skips_empty_and_dupes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    learnings = tmp_path / ".akomagni" / "memory" / "learnings"
    learnings.mkdir(parents=True)
    (learnings / "empty.md").write_text("# Empty\n\n", encoding="utf-8")
    (learnings / "a.md").write_text("# Same\n\nBody one.\n", encoding="utf-8")
    (learnings / "b.md").write_text("# Same\n\nBody one.\n", encoding="utf-8")
    (learnings / "plain.md").write_text("no heading just body\n", encoding="utf-8")
    plan = build_train_plan()
    from akomagni.train.lora import collect_learning_examples

    examples = collect_learning_examples(plan.dataset_sources + [str(tmp_path / "missing-dir")])
    assert len([e for e in examples if e.output.strip() == "Body one."]) == 1
    assert any("no heading" in e.output for e in examples)
    assert len(examples) >= 2


def test_export_jsonl_custom_dest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan()
    dest = tmp_path / "custom" / "out.jsonl"
    path, count = export_jsonl(plan, dest=dest)
    assert path == dest
    assert count == 1
    assert dest.is_file()


def test_write_train_config_unknown_model_keeps_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="totally-unknown-gguf")
    bundle = prepare_train_bundle(plan)
    config = yaml.safe_load(bundle.config_path.read_text(encoding="utf-8"))
    assert config["hf_model_id"] == "totally-unknown-gguf"


def test_run_train_stub_delegates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="phi-3.5-mini")
    from akomagni.train.lora import run_train_stub

    called: list[object] = []

    def _fake(p, stack=None):
        called.append(p)
        bundle = prepare_train_bundle(p)
        return TrainResult(
            bundle=bundle,
            adapter_dir=p.output_dir / "adapter",
            hf_model_id="microsoft/Phi-3.5-mini-instruct",
            method="lora",
            example_count=1,
        )

    monkeypatch.setattr("akomagni.train.runner.run_train", _fake)
    result = run_train_stub(plan)
    assert called == [plan]
    assert result.method == "lora"


def test_messages_to_text_fallback_and_bnb():
    from akomagni.train.runner import _bnb_available, _messages_to_text

    class BrokenTok:
        def apply_chat_template(self, *_a, **_k):
            raise ValueError("no template")

    class NoTemplate:
        pass

    text = _messages_to_text(
        BrokenTok(),
        [{"role": "user", "content": "u"}, {"role": "assistant", "content": "a"}],
    )
    assert "user: u" in text
    assert "assistant:" in text
    assert "user: hi" in _messages_to_text(NoTemplate(), [{"role": "user", "content": "hi"}])

    class FakeTorch:
        class cuda:
            @staticmethod
            def is_available():
                return False

    assert _bnb_available(FakeTorch()) is False


def test_bnb_available_true(monkeypatch):
    from akomagni.train import runner as runner_mod

    class CudaTorch:
        class cuda:
            @staticmethod
            def is_available():
                return True

    monkeypatch.setitem(__import__("sys").modules, "bitsandbytes", SimpleNamespace())
    assert runner_mod._bnb_available(CudaTorch()) is True


def test_execute_training_cuda_lora_without_bnb(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "a"},
                    {"role": "assistant", "content": "b"},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = tmp_path / "adapter"
    monkeypatch.setattr("akomagni.train.runner._bnb_available", lambda _torch: False)
    method = execute_training(
        hf_model_id="microsoft/Phi-3.5-mini-instruct",
        dataset_path=dataset,
        adapter_dir=adapter,
        config={"epochs": 1, "batch_size": 1},
        stack=_fake_stack(cuda=True),
    )
    assert method == "lora"


def test_run_train_wraps_trainer_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    plan = build_train_plan(base_model="phi-3.5-mini")

    def _boom(**_kwargs):
        raise RuntimeError("cuda OOM")

    monkeypatch.setattr("akomagni.train.runner.execute_training", _boom)
    with pytest.raises(TrainError, match="Training failed"):
        run_train(plan, stack=_fake_stack(cuda=False))


def test_central_learnings_included(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    central = home / ".akomagni" / "memory" / "learnings"
    central.mkdir(parents=True)
    (central / "c.md").write_text("# Central\n\nFrom home.\n", encoding="utf-8")
    monkeypatch.setattr("akomagni.train.lora.Path.home", lambda: home)
    plan = build_train_plan()
    assert any(str(central) == s for s in plan.dataset_sources)


def test_execute_training_qlora_path(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "a"},
                    {"role": "assistant", "content": "b"},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = tmp_path / "adapter"
    monkeypatch.setattr("akomagni.train.runner._bnb_available", lambda _torch: True)
    method = execute_training(
        hf_model_id="microsoft/Phi-3.5-mini-instruct",
        dataset_path=dataset,
        adapter_dir=adapter,
        config={"epochs": 1, "batch_size": 1, "learning_rate": 2e-4},
        stack=_fake_stack(cuda=True),
    )
    assert method == "qlora"
    assert (adapter / "adapter_config.json").is_file()


def test_train_plan_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "plan"])
    assert result.exit_code == 0
    assert "qwen2.5-coder-7b" in result.stdout
    assert "Examples" in result.stdout


def test_train_export_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "export"])
    assert result.exit_code == 0
    assert "Exported" in result.stdout


def test_train_bundle_cli(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)
    result = runner.invoke(app, ["train", "bundle"])
    assert result.exit_code == 0
    assert "Train bundle ready" in result.stdout
    assert (tmp_path / ".akomagni" / "train" / "output" / "dataset.jsonl").is_file()


def test_train_run_cli_success(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)

    def _fake_run(plan):
        bundle = prepare_train_bundle(plan)
        adapter = plan.output_dir / "adapter"
        adapter.mkdir(parents=True, exist_ok=True)
        return TrainResult(
            bundle=bundle,
            adapter_dir=adapter,
            hf_model_id="microsoft/Phi-3.5-mini-instruct",
            method="lora",
            example_count=bundle.example_count,
        )

    monkeypatch.setattr("akomagni.train.runner.run_train", _fake_run)
    result = runner.invoke(app, ["train", "run", "-m", "phi-3.5-mini"])
    assert result.exit_code == 0, result.stdout
    assert "Training complete" in result.stdout
    assert "Adapter" in result.stdout


def test_train_run_cli_missing_extra(tmp_path, monkeypatch, akomagni_home):
    monkeypatch.chdir(tmp_path)
    _seed_learnings(tmp_path)

    def _boom(plan):
        raise TrainError("Training requires the optional 'train' extra")

    monkeypatch.setattr("akomagni.train.runner.run_train", _boom)
    result = runner.invoke(app, ["train", "run", "-m", "phi-3.5-mini"])
    assert result.exit_code == 1
    assert "train" in result.stdout.lower()
