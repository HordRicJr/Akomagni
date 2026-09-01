"""Akomagni Train — local LoRA fine-tuning (v0.3 scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TrainError(RuntimeError):
    """Raised when training cannot proceed."""


@dataclass(frozen=True)
class TrainPlan:
    """Suggested LoRA training plan from project + central memory."""

    base_model: str
    dataset_sources: list[str]
    output_dir: Path
    notes: str


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
    if central.is_dir():
        sources.append(str(central))
    if project.is_dir():
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
        notes="v0.3 scaffold — QLoRA pipeline integration pending.",
    )


def run_train_stub(plan: TrainPlan) -> str:
    """Placeholder until QLoRA trainer is wired (issue #15)."""
    raise TrainError(
        "LoRA training is not yet implemented. "
        f"Plan ready for {plan.base_model} → {plan.output_dir}. "
        "Track progress on https://github.com/HordRicJr/Akomagni/issues/15"
    )
