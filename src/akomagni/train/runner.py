"""Native QLoRA / LoRA runner for Akomagni Train."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from akomagni.train.lora import TrainBundle, TrainError, TrainPlan, prepare_train_bundle
from akomagni.train.models import requires_gpu, resolve_hf_train_model


@dataclass(frozen=True)
class TrainResult:
    """Result of a native training run."""

    bundle: TrainBundle
    adapter_dir: Path
    hf_model_id: str
    method: str
    example_count: int


def _missing_train_extra(exc: ImportError) -> TrainError:
    return TrainError(
        "Training requires the optional 'train' extra "
        f"(missing dependency: {exc.name or 'train stack'}).\n"
        "Install with: pip install 'akomagni[train]' "
        "(or: akomagni config extras train)"
    )


def import_train_stack() -> dict[str, Any]:
    """Lazy-import heavy training dependencies."""
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        raise _missing_train_extra(exc) from exc

    return {
        "torch": torch,
        "load_dataset": load_dataset,
        "LoraConfig": LoraConfig,
        "get_peft_model": get_peft_model,
        "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
        "SFTConfig": SFTConfig,
        "SFTTrainer": SFTTrainer,
    }


def load_train_yaml(path: Path) -> dict[str, Any]:
    """Load hyperparameters from train.yaml."""
    if not path.is_file():
        raise TrainError(f"Missing train config: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TrainError(f"Invalid train.yaml format: {path}")
    return payload


def _bnb_available(torch: Any) -> bool:
    if not torch.cuda.is_available():
        return False
    try:
        import bitsandbytes  # noqa: F401
    except ImportError:
        return False
    return True


def _messages_to_text(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        except (TypeError, ValueError, AttributeError):
            rendered = None
        if rendered is not None:
            return rendered
    parts: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        parts.append(f"{role}: {content}")
    parts.append("assistant:")
    return "\n".join(parts)


def execute_training(
    *,
    hf_model_id: str,
    dataset_path: Path,
    adapter_dir: Path,
    config: dict[str, Any],
    stack: dict[str, Any] | None = None,
) -> str:
    """Run QLoRA (CUDA + bitsandbytes) or LoRA fallback and save the adapter."""
    mods = stack or import_train_stack()
    torch = mods["torch"]
    load_dataset = mods["load_dataset"]
    LoraConfig = mods["LoraConfig"]
    get_peft_model = mods["get_peft_model"]
    prepare_model_for_kbit_training = mods["prepare_model_for_kbit_training"]
    AutoModelForCausalLM = mods["AutoModelForCausalLM"]
    AutoTokenizer = mods["AutoTokenizer"]
    BitsAndBytesConfig = mods["BitsAndBytesConfig"]
    SFTConfig = mods["SFTConfig"]
    SFTTrainer = mods["SFTTrainer"]

    use_qlora = _bnb_available(torch)
    method = "qlora" if use_qlora else "lora"
    adapter_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(hf_model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {"trust_remote_code": True}
    if use_qlora:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        model_kwargs["device_map"] = "auto"
    elif torch.cuda.is_available():
        model_kwargs["torch_dtype"] = torch.float16
        model_kwargs["device_map"] = "auto"
    else:
        model_kwargs["torch_dtype"] = torch.float32

    model = AutoModelForCausalLM.from_pretrained(hf_model_id, **model_kwargs)
    if use_qlora:
        model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(
        r=int(config.get("lora_r", 16)),
        lora_alpha=int(config.get("lora_alpha", 32)),
        lora_dropout=float(config.get("lora_dropout", 0.05)),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=config.get("target_modules")
        or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)

    dataset = load_dataset("json", data_files=str(dataset_path), split="train")

    def _format_row(row: dict[str, Any]) -> dict[str, str]:
        messages = row.get("messages") or []
        return {"text": _messages_to_text(tokenizer, messages)}

    dataset = dataset.map(_format_row)

    training_args = SFTConfig(
        output_dir=str(adapter_dir),
        num_train_epochs=float(config.get("epochs", 1)),
        per_device_train_batch_size=int(config.get("batch_size", 1)),
        learning_rate=float(config.get("learning_rate", 2.0e-4)),
        logging_steps=1,
        save_strategy="epoch",
        report_to=[],
        dataset_text_field="text",
        max_seq_length=int(config.get("max_seq_length", 2048)),
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    return method


def run_train(plan: TrainPlan, *, stack: dict[str, Any] | None = None) -> TrainResult:
    """Export bundle (if needed) and run native QLoRA/LoRA training."""
    bundle = prepare_train_bundle(plan)
    config = load_train_yaml(bundle.config_path)
    configured = config.get("hf_model_id")
    hf_model_id = (
        str(configured).strip()
        if configured
        else resolve_hf_train_model(str(config.get("base_model") or plan.base_model))
    )
    adapter_dir = Path(str(config.get("output_dir") or (plan.output_dir / "adapter")))

    mods = stack or import_train_stack()
    torch = mods["torch"]
    if requires_gpu(plan.base_model) and not torch.cuda.is_available():
        raise TrainError(
            f"Training '{plan.base_model}' needs a CUDA GPU for practical fine-tuning. "
            "Use --model phi-3.5-mini or llama-3.2-3b on CPU, "
            "or run on a machine with an NVIDIA GPU."
        )

    try:
        method = execute_training(
            hf_model_id=hf_model_id,
            dataset_path=bundle.dataset_path,
            adapter_dir=adapter_dir,
            config=config,
            stack=mods,
        )
    except TrainError:
        raise
    except Exception as exc:
        raise TrainError(f"Training failed: {exc}") from exc

    return TrainResult(
        bundle=bundle,
        adapter_dir=adapter_dir,
        hf_model_id=hf_model_id,
        method=method,
        example_count=bundle.example_count,
    )
