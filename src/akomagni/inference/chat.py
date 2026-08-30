"""Wire Akomagni Flow routing to the local inference backend."""

from __future__ import annotations

from akomagni.flow.intent import RouteDecision
from akomagni.inference.client import InferenceClientError, chat_completion, check_health


def build_flow_system_prompt(decision: RouteDecision) -> str:
    """Build a system prompt from the Flow routing decision."""
    return (
        f"You are the Akomagni agent `{decision.agent_id}` using skill `{decision.skill}`.\n"
        f"Context: {decision.hint}\n"
        "Answer concisely in the user's language."
    )


def try_chat_with_inference(
    message: str,
    decision: RouteDecision,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str | None = None,
) -> str | None:
    """Call local /v1/chat/completions when the server is online."""
    status = check_health(host=host, port=port)
    if not status.online:
        return None
    model_id = model or (status.models[0] if status.models else None)
    try:
        return chat_completion(
            message,
            host=host,
            port=port,
            model=model_id,
            system_prompt=build_flow_system_prompt(decision),
        )
    except InferenceClientError:
        return None
