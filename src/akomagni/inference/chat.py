"""Wire Akomagni Flow routing to the local inference backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from akomagni.core.config import MODELS_DIR, load_config
from akomagni.core.router.swap import (
    DomainModelPlan,
    ModelSwapPlan,
    plan_model_swap,
    resolve_domain_model,
)
from akomagni.flow.intent import RouteDecision
from akomagni.inference.client import (
    ImageArtifact,
    InferenceStatus,
    chat_completion,
    check_health,
    check_health_from_config,
)
from akomagni.inference.endpoint import resolve_inference_endpoint


def _azure_image_model_candidates(
    cfg: dict[str, Any],
    *,
    primary: str | None,
    status: InferenceStatus,
) -> list[str]:
    """Foundry deployment names only — never Rodium catalogue ids like google/…."""
    from akomagni.inference.endpoint import AZURE_DEFAULT_MODELS

    ordered: list[str] = []
    providers = cfg.get("providers") or {}
    azure = providers.get("azure") or {}
    mapped = azure.get("deployments") or azure.get("models") or {}
    configured = mapped.get("image") if isinstance(mapped, dict) else None

    def _add(name: str | None) -> None:
        if not name:
            return
        cleaned = str(name).strip()
        # Reject Rodium-style catalogue ids on Foundry.
        if not cleaned or "/" in cleaned or cleaned.lower().startswith("rodium"):
            return
        if cleaned not in ordered:
            ordered.append(cleaned)

    _add(primary)
    _add(str(configured) if configured else None)
    _add(AZURE_DEFAULT_MODELS.get("image"))

    live = list(status.models or [])
    image_hints = ("image", "dall-e", "dalle", "flux", "stable-diffusion")
    for model in live:
        low = model.lower()
        if any(h in low for h in image_hints):
            _add(model)

    # Prefer configured/live image deployments; drop chat-only fallbacks like gpt-4o-mini
    # unless they were explicitly configured as image.
    chat_like = ("gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-35", "gpt-3.5", "o1", "o3", "o4")
    if configured or any(any(h in m.lower() for h in image_hints) for m in live):
        filtered = [
            m
            for m in ordered
            if not any(m.lower() == c or m.lower().startswith(c) for c in chat_like)
            or m == str(configured or "").strip()
        ]
        if filtered:
            return filtered
    return ordered


@dataclass(frozen=True)
class InferenceChatPlan:
    domain_plan: DomainModelPlan
    swap_plan: ModelSwapPlan
    model_id: str | None


def build_flow_system_prompt(
    decision: RouteDecision,
    *,
    rag_context: str = "",
    skill_guidance: str = "",
    tools_enabled: bool = False,
) -> str:
    """Build a system prompt from the Flow routing decision (+ optional skill)."""
    lines = [
        f"You are the Akomagni agent `{decision.agent_id}` using skill `{decision.skill}`.",
        f"Context: {decision.hint}",
        "You are running inside the Akomagni CLI chat for the user's active project only.",
        "Stay inside the active --project folder conceptually; never assume parent checkouts.",
        "Answer in the user's language.",
    ]
    if tools_enabled:
        lines.extend(
            [
                "IMPLEMENTATION MODE: create real files with project tools.",
                "Always tell the user briefly what you are doing before each batch of tools.",
                "Never dump long source code into chat; write files via tools instead.",
                "Finish by starting the local dev server and giving the user the URL.",
            ]
        )
    else:
        lines.extend(
            [
                "Collaborate step by step in conversation.",
                "Do not invent or write project files unless the user explicitly asks you to output code.",
                "Do not dump an entire codebase, scaffold, or multi-file tree in one reply.",
                (
                    "When implementation is needed, say what you will create and use project tools — "
                    "do not paste long source code into the chat."
                ),
                "Prefer short clarifying questions and one next step at a time.",
            ]
        )
    if skill_guidance.strip():
        lines.extend(["", "## Active skill guidance", "", skill_guidance.strip()])
    if rag_context.strip():
        lines.extend(["", rag_context.strip()])
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
    skill_guidance: str = "",
    history: list[dict[str, str]] | None = None,
) -> str | ImageArtifact | None:
    """Call inference when the configured provider is online.

    For cloud image domains, returns an :class:`ImageArtifact` so the CLI can
    ask where to save the file. Text/chat still returns a string reply.
    """
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
    if not endpoint.is_local:
        from akomagni.inference.provider_routing import pick_fallback_model

        model_id = model or plan.model_id
        if not model_id:
            model_id = pick_fallback_model(endpoint.provider, status.models)

    if plan.domain_plan.classification.domain.value == "image" and not endpoint.is_local:
        from akomagni.inference.client import InferenceClientError, image_generation
        from akomagni.inference.endpoint import cloud_model_for_domain
        from akomagni.inference.provider_routing import image_hint_for_provider
        from akomagni.inference.rodium_router import image_model_candidates

        provider = getattr(endpoint, "provider", "local")
        primary = model_id or cloud_model_for_domain("image", config=cfg, message=message)

        if provider == "azure":
            # Foundry uses deployment names on the resource — never Rodium catalogue ids.
            candidates = _azure_image_model_candidates(cfg, primary=primary, status=status)
            if not candidates:
                return (
                    "Image generation needs an image deployment on this Foundry resource "
                    "(e.g. gpt-image-1 or dall-e-3).\n"
                    "Deploy one in Azure AI Foundry / Azure OpenAI, then reconnect:\n"
                    "  akomagni connect foundry <url> --auth api_key\n"
                    "Or use Rodium for catalogue image models: akomagni connect rodium\n"
                    "Docs: https://learn.microsoft.com/azure/ai-foundry/"
                )
            errors: list[str] = []
            for image_model in candidates:
                try:
                    return image_generation(
                        message,
                        base_url=endpoint.base_url,
                        api_key=endpoint.api_key,
                        model=image_model,
                        provider=provider,
                        auth_mode=getattr(endpoint, "auth_mode", "api_key"),
                    )
                except InferenceClientError as exc:
                    errors.append(f"{image_model}: {exc}")
                    continue
            detail = "\n".join(errors[:5]) if errors else "no image deployment tried"
            return image_hint_for_provider("azure") + f"\n{detail}"

        if provider == "rodium":
            errors = []
            for image_model in image_model_candidates(primary, message=message):
                try:
                    return image_generation(
                        message,
                        base_url=endpoint.base_url,
                        api_key=endpoint.api_key,
                        model=image_model,
                        provider=provider,
                        auth_mode=getattr(endpoint, "auth_mode", "api_key"),
                    )
                except InferenceClientError as exc:
                    errors.append(f"{image_model}: {exc}")
                    continue
            detail = "\n".join(errors[:5]) if errors else "no image model tried"
            return image_hint_for_provider("rodium") + f"\n{detail}"

        return image_hint_for_provider(provider)

    return chat_completion(
        message,
        host=host,
        port=port,
        base_url=None if endpoint.is_local else endpoint.base_url,
        api_key=endpoint.api_key,
        model=model_id,
        history=history,
        system_prompt=build_flow_system_prompt(
            decision,
            rag_context=rag_context,
            skill_guidance=skill_guidance,
        ),
        provider=getattr(endpoint, "provider", "local"),
        auth_mode=getattr(endpoint, "auth_mode", "api_key"),
    )
