"""Akomagni Train — local LoRA fine-tuning from Memory (v0.3)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_INSTRUCTION_PREFIX = "Apply this Akomagni memory learning when helping with related tasks."


class TrainError(RuntimeError):
    """Raised when training cannot proceed."""


@dataclass(frozen=True)
class TrainPlan:
    """Suggested LoRA training plan from project + central memory."""

    base_model: str
    dataset_sources: list[str]
    output_dir: Path
    notes: str


@dataclass(frozen=True)
class LearningExample:
    """One instruction-tuning row derived from a memory note."""

    instruction: str
    output: str
    source: str


@dataclass(frozen=True)
class TrainBundle:
    """Exported artifacts ready for an external QLoRA trainer."""

    plan: TrainPlan
    dataset_path: Path
    config_path: Path
    readme_path: Path
    example_count: int


def build_train_plan(
    *,
    base_model: str = "qwen2.5-coder-7b",
    project_root: Path | None = None,
) -> TrainPlan:
    """Build a training plan from Akomagni Memory learnings (read-only scan)."""
    root = project_root or Path.cwd()
    sources: list[str] = []

    central = Path.home() / ".akomagni" / "memory" / "learnings"
    project = root / ".akomagni" / "memory" / "learnings"
    if central.is_dir() and any(central.rglob("*.md")):
        sources.append(str(central))
    if project.is_dir() and any(project.rglob("*.md")):
        sources.append(str(project))

    if not sources:
        raise TrainError(
            "No memory learnings found. Add learnings with "
            "'akomagni memory add' before planning LoRA training."
        )

    out = root / ".akomagni" / "train" / "output"
    return TrainPlan(
        base_model=base_model,
        dataset_sources=sources,
        output_dir=out,
        notes=(
            "Export with 'akomagni train export/bundle', "
            "or fine-tune with 'akomagni train run' (requires akomagni[train])."
        ),
    )


def _parse_learning_markdown(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return path.stem, ""

    title = path.stem
    body = text
    match = re.match(r"^#\s+(.+)\n+([\s\S]*)$", text)
    if match:
        title = match.group(1).strip()
        body = match.group(2).strip()
    return title, body


def collect_learning_examples(sources: list[str]) -> list[LearningExample]:
    """Scan memory learning folders and build instruction-tuning rows."""
    examples: list[LearningExample] = []
    seen: set[tuple[str, str]] = set()

    for src in sources:
        root = Path(src)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            title, body = _parse_learning_markdown(path)
            if not body:
                continue
            instruction = f"{_INSTRUCTION_PREFIX}\n\nTopic: {title}"
            key = (instruction, body)
            if key in seen:
                continue
            seen.add(key)
            examples.append(
                LearningExample(
                    instruction=instruction,
                    output=body,
                    source=str(path),
                )
            )
    return examples


def export_jsonl(
    plan: TrainPlan,
    *,
    dest: Path | None = None,
) -> tuple[Path, int]:
    """Export memory learnings to JSONL (chat messages format)."""
    examples = collect_learning_examples(plan.dataset_sources)
    if not examples:
        raise TrainError("No markdown learnings found in memory sources.")

    dataset_path = dest or (plan.output_dir / "dataset.jsonl")
    dataset_path.parent.mkdir(parents=True, exist_ok=True)

    with dataset_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            record = {
                "messages": [
                    {"role": "user", "content": example.instruction},
                    {"role": "assistant", "content": example.output},
                ],
                "source": example.source,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return dataset_path, len(examples)


def write_train_config(plan: TrainPlan, dataset_path: Path) -> Path:
    """Write QLoRA config for native runner and external trainers."""
    from akomagni.train.models import resolve_hf_train_model

    config_path = plan.output_dir / "train.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        hf_model_id = resolve_hf_train_model(plan.base_model)
    except TrainError:
        hf_model_id = plan.base_model
    payload = {
        "base_model": plan.base_model,
        "hf_model_id": hf_model_id,
        "dataset": str(dataset_path),
        "format": "chat_messages_jsonl",
        "method": "qlora",
        "output_dir": str(plan.output_dir / "adapter"),
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "epochs": 1,
        "batch_size": 1,
        "learning_rate": 2.0e-4,
        "max_seq_length": 2048,
        "notes": (
            "Generated by akomagni train — run with `akomagni train run`, "
            "or point an external QLoRA tool at this file."
        ),
    }
    config_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return config_path


def write_train_readme(plan: TrainPlan, dataset_path: Path, config_path: Path, count: int) -> Path:
    """Write human-readable next steps beside exported artifacts."""
    readme_path = plan.output_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Akomagni Train bundle",
                "",
                f"- Base model: `{plan.base_model}`",
                f"- Examples: {count}",
                f"- Dataset: `{dataset_path.name}`",
                f"- Config: `{config_path.name}`",
                "",
                "## Next steps",
                "",
                "1. Review `dataset.jsonl` — each row is a chat fine-tune example from Memory.",
                "2. Install the train extra: `akomagni config extras train`",
                "3. Run native QLoRA/LoRA: `akomagni train run`",
                "4. Or point an external trainer at `train.yaml` (Unsloth, Axolotl, LLaMA-Factory).",
                "5. Load the adapter from `adapter/` (PEFT) — GGUF merge is a follow-up step.",
                "",
                "Epic: https://github.com/HordRicJr/Akomagni/issues/15",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return readme_path


def prepare_train_bundle(plan: TrainPlan) -> TrainBundle:
    """Export dataset + config + README for LoRA training."""
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path, count = export_jsonl(plan)
    config_path = write_train_config(plan, dataset_path)
    readme_path = write_train_readme(plan, dataset_path, config_path, count)
    return TrainBundle(
        plan=plan,
        dataset_path=dataset_path,
        config_path=config_path,
        readme_path=readme_path,
        example_count=count,
    )


def run_train_stub(plan: TrainPlan):
    """Backward-compatible alias for :func:`akomagni.train.runner.run_train`."""
    from akomagni.train.runner import run_train

    return run_train(plan)
