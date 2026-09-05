"""Wire Akomagni Flow routing to the local inference backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from akomagni.core.config import MODELS_DIR, load_config
from akomagni.core.router.swap import (
    DomainModelPlan,
    ModelSwapPlan,
    plan_model_swap,
    resolve_domain_model,
)
from akomagni.flow.intent import RouteDecision
from akomagni.inference.client import (
    InferenceStatus,
    chat_completion,
    check_health,
    check_health_from_config,
)
from akomagni.inference.endpoint import resolve_inference_endpoint


@dataclass(frozen=True)
class InferenceChatPlan:
    domain_plan: DomainModelPlan
    swap_plan: ModelSwapPlan
    model_id: str | None


def build_flow_system_prompt(decision: RouteDecision, *, rag_context: str = "") -> str:
    """Build a system prompt from the Flow routing decision."""
    lines = [
        f"You are the Akomagni agent `{decision.agent_id}` using skill `{decision.skill}`.",
        f"Context: {decision.hint}",
    ]
    if rag_context.strip():
        lines.extend(["", rag_context.strip()])
    lines.append("Answer concisely in the user's language.")
    return "\n".join(lines)


def plan_inference_chat(
    message: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    config: dict | None = None,
    models_dir: Path | None = None,
    status: InferenceStatus | None = None,
) -> InferenceChatPlan:
    """Resolve domain model and whether a worker hot-swap is needed."""
    cfg = config or load_config()
    models = models_dir or MODELS_DIR
    domain_plan = resolve_domain_model(message, config=cfg, models_dir=models)
    endpoint = resolve_inference_endpoint(cfg)
    if endpoint.is_local:
        inference_status = status or check_health(host=host, port=port)
    else:
        inference_status = status or check_health_from_config(cfg)
    swap_plan = plan_model_swap(
        status=inference_status,
        target_path=domain_plan.model_path,
        target_model_id=domain_plan.model_id,
    )
    model_id = domain_plan.model_id
    if inference_status.models and not swap_plan.needs_swap and endpoint.is_local:
        model_id = inference_status.models[0]
    return InferenceChatPlan(domain_plan=domain_plan, swap_plan=swap_plan, model_id=model_id)


def try_chat_with_inference(
    message: str,
    decision: RouteDecision,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
    auto_swap: bool = False,
    rag_context: str = "",
) -> str | None:
    """Call /v1/chat/completions when the configured provider is online."""
    cfg = load_config()
    endpoint = resolve_inference_endpoint(cfg)
    plan = plan_inference_chat(message, host=host, port=port, config=cfg)
    if plan.domain_plan.skip_inference:
        return None

    if endpoint.is_local:
        status = check_health(host=host, port=port)
    else:
        status = check_health_from_config(cfg)
    if not status.online:
        return None

    if (
        endpoint.is_local
        and auto_swap
        and plan.swap_plan.needs_swap
        and plan.domain_plan.model_path is not None
    ):
        from akomagni.inference.worker import hot_swap_model

        inference = cfg.get("inference", {})
        swap = hot_swap_model(
            plan.domain_plan.catalog_name or plan.domain_plan.model_id or "",
            models_dir=MODELS_DIR,
            host=host,
            port=port,
            binary=inference.get("binary"),
            ctx_size=int(inference.get("ctx_size", 4096)),
            n_gpu_layers=int(inference.get("n_gpu_layers", -1)),
        )
        if not swap.swapped and "not found" in swap.message.lower():
            return None
        status = check_health(host=host, port=port)
        plan = plan_inference_chat(message, host=host, port=port, status=status, config=cfg)

    model_id = model or plan.model_id or (status.models[0] if status.models else None)
    # Cloud: use domain-mapped catalogue id. Listed smart profiles can still 404.
    if not endpoint.is_local:
        model_id = model or plan.model_id
        if not model_id and status.models:
            preferred = next(
                (m for m in status.models if "/" in m and not m.startswith("rodium/")),
                status.models[0],
            )
            model_id = preferred

    if plan.domain_plan.classification.domain.value == "image" and not endpoint.is_local:
        from akomagni.inference.client import InferenceClientError, image_generation
        from akomagni.inference.endpoint import cloud_model_for_domain
        from akomagni.inference.rodium_router import image_model_candidates

        primary = model_id or cloud_model_for_domain("image", config=cfg)
        errors: list[str] = []
        for image_model in image_model_candidates(primary):
            try:
                return image_generation(
                    message,
                    base_url=endpoint.base_url,
                    api_key=endpoint.api_key,
                    model=image_model,
                )
            except InferenceClientError as exc:
                errors.append(f"{image_model}: {exc}")
                continue
        detail = "\n".join(errors[:5]) if errors else "no image model tried"
        return (
            "Image generation failed after trying catalogue image models.\n"
            f"{detail}\n"
            "Check RODI credits / model access "
            "(https://www.rodiumai.io/docs/guides/image-generation)."
        )

    return chat_completion(
        message,
        host=host,
        port=port,
        base_url=None if endpoint.is_local else endpoint.base_url,
        api_key=endpoint.api_key,
        model=model_id,
        system_prompt=build_flow_system_prompt(decision, rag_context=rag_context),
    )
