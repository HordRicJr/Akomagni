"""Akomagni CLI — doctor, serve, flow, memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from akomagni import __version__
from akomagni.core.config import MODELS_DIR, ensure_default_config, load_config
from akomagni.core.doctor import run_doctor
from akomagni.core.i18n import resolve_language, translate
from akomagni.core.registry import list_catalog, recommend_models
from akomagni.core.router import classify_domain
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import load_state
from akomagni.inference.chat import plan_inference_chat, try_chat_with_inference
from akomagni.inference.client import (
    InferenceClientError,
    chat_completion,
    check_health_from_config,
)
from akomagni.inference.llama import list_local_models
from akomagni.inference.pull import ModelPullError, pull_model
from akomagni.inference.server import serve as start_inference_server
from akomagni.inference.worker import hot_swap_model, read_worker_state, stop_worker
from akomagni.mcp.approval import ApprovalError, pop_request, reject_request
from akomagni.mcp.approval import list_pending as list_mcp_pending
from akomagni.mcp.sandbox import resolve_workspace
from akomagni.mcp.server import run_stdio_server
from akomagni.mcp.tools import AgentTools, ToolError
from akomagni.memory.capture import (
    CaptureError,
    approve_capture,
    build_capture_text,
    list_pending,
    maybe_prompt_capture,
    propose_capture,
    reject_capture,
)
from akomagni.memory.ops import MemoryError, add_memory, promote_project_memory
from akomagni.memory.store import memory_status
from akomagni.rag.context import retrieve_rag_context
from akomagni.rag.ingest import RagIngestError, ingest_path
from akomagni.rag.query import hits_to_json, hybrid_query
from akomagni.rag.store import default_index_path, store_status
from akomagni.skills.discovery import discover_skills, find_skill
from akomagni.skills.invoke import invoke_skill

app = typer.Typer(
    name="akomagni",
    help="Akomagni — local AI workstation (code, design, image, business).",
    no_args_is_help=True,
)
console = Console()
run_app = typer.Typer(help="Run an Akomagni mode.")
memory_app = typer.Typer(help="Akomagni Memory — central + project.")
flow_app = typer.Typer(help="Akomagni Flow — BMAD agent orchestration.")
config_app = typer.Typer(help="Configuration ~/.akomagni/config.yaml")
skill_app = typer.Typer(help="BMAD skills discovery and invocation.")
model_app = typer.Typer(help="Local model catalog and recommendations.")
router_app = typer.Typer(help="Domain model router (code, design, image, text).")
inference_app = typer.Typer(help="OpenAI-compatible local inference API.")
rag_app = typer.Typer(help="RAG ingest and hybrid retrieval (BM25 + sqlite-vec).")
mcp_app = typer.Typer(help="MCP agent tools with workspace sandbox.")
train_app = typer.Typer(help="LoRA fine-tuning from Akomagni Memory (v0.3).")
ide_app = typer.Typer(help="IDE setup — MCP config for Cursor/VS Code until v1.0 fork.")

app.add_typer(run_app, name="run")
app.add_typer(memory_app, name="memory")
app.add_typer(flow_app, name="flow")
app.add_typer(config_app, name="config")
app.add_typer(skill_app, name="skill")
app.add_typer(model_app, name="model")
app.add_typer(router_app, name="router")
app.add_typer(inference_app, name="inference")
app.add_typer(rag_app, name="rag")
app.add_typer(mcp_app, name="mcp")
app.add_typer(train_app, name="train")
app.add_typer(ide_app, name="ide")


@app.command("connect")
def connect_cmd(
    provider: str = typer.Argument(..., help="Cloud provider: rodium, foundry, or local."),
    url: str | None = typer.Argument(
        None,
        help="API base URL (optional for Rodium; required for Foundry).",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project folder for VS Code settings sync.",
    ),
    no_sync: bool = typer.Option(False, "--no-sync", help="Skip writing .vscode/settings.json."),
) -> None:
    """Connect a cloud AI provider — prompts for API key interactively."""
    from akomagni.inference.connect import (
        FOUNDRY_URL_HINT,
        RODIUM_DEFAULT_URL,
        ConnectError,
        connect_provider,
        normalize_provider,
    )

    try:
        normalized = normalize_provider(provider)
    except ConnectError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    if normalized == "local":
        result = connect_provider("local", sync_ide=False)
        console.print("[green]Connected to local inference[/] (offline mode)")
        console.print("Run: akomagni serve --model <name>")
        return

    base_url = url
    if normalized == "rodium" and not base_url:
        base_url = typer.prompt(
            "Rodium API URL",
            default=RODIUM_DEFAULT_URL,
        )
    elif normalized == "azure" and not base_url:
        base_url = typer.prompt(
            "Azure Foundry URL",
            default=FOUNDRY_URL_HINT,
        )

    key_label = "Rodium API key (rd_sk_…)" if normalized == "rodium" else "Azure API key"
    api_key = typer.prompt(key_label, hide_input=True)
    if not api_key.strip():
        console.print("[red]API key cannot be empty.[/]")
        raise typer.Exit(code=1)

    root = Path(workspace) if workspace else Path.cwd()
    try:
        result = connect_provider(
            normalized,
            base_url=base_url,
            api_key=api_key,
            workspace=root,
            sync_ide=not no_sync,
        )
    except ConnectError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    label = "Rodium AI" if normalized == "rodium" else "Azure Foundry"
    if result.online:
        console.print(f"[green]Connected to {label}[/] — {result.base_url}")
        if result.models:
            console.print(f"Models available: {len(result.models)}")
    else:
        console.print(f"[yellow]Saved credentials for {label}[/] but API check failed.")
        if result.error:
            console.print(f"[dim]{result.error}[/]")
    console.print("\nNext:")
    console.print("  akomagni run cli          # chat in terminal")
    console.print("  akomagni ide open         # open VS Code with Akomagni Chat")
    if normalized == "azure":
        console.print("  Or install Foundry Toolkit: ms-windows-ai-studio.windows-ai-studio")


def _lang() -> str:
    return resolve_language(load_config())


def _t(key: str, **kwargs: Any) -> str:
    return translate(key, _lang(), **kwargs)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"akomagni {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Afficher la version.",
    ),
) -> None:
    """Akomagni CLI."""


@app.command()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Sortie JSON machine."),
) -> None:
    """Scanner la machine et recommander un profil + modèles."""
    lang = _lang()
    report = run_doctor(lang=lang)
    if json_output:
        import json
        import sys

        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
        return
    from rich.markup import escape

    for line in report["summary"].splitlines():
        if "[bold]" in line:
            console.print(line.replace("[bold]", "").replace("[/bold]", ""))
        else:
            console.print(escape(line))


@app.command()
def update() -> None:
    """Update Akomagni from git (pull + reinstall)."""
    from akomagni.core.update import UpdateError, run_update

    try:
        result = run_update()
    except UpdateError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from None
    except OSError as exc:
        # Windows file locks should never crash the CLI with a raw traceback.
        console.print(
            f"[red]{_t('error')}:[/] Cannot refresh launcher ({exc}).\n"
            "Close this window and reinstall:\n"
            "  irm https://hordricjr.github.io/Akomagni/install/windows | iex"
        )
        raise typer.Exit(code=1) from None
    console.print(f"[green]{_t('update.success')}[/]")
    if result.previous_ref != result.current_ref:
        console.print(
            _t("update.from_to", previous=result.previous_ref, current=result.current_ref)
        )
    else:
        console.print("  Already up to date.")
    console.print(_t("update.install_dir", path=result.install_dir))
    console.print(_t("update.bin_path", path=result.bin_path))


@app.command()
def serve(
    host: str = typer.Option(None, help="Hôte API OpenAI-compatible."),
    port: int = typer.Option(None, help="Port API."),
    model: str | None = typer.Option(None, "--model", "-m", help="GGUF model name or path."),
    binary: str | None = typer.Option(
        None, "--binary", help="Path to llama-server binary (auto-detect by default)."
    ),
) -> None:
    """Démarrer llama-server (API OpenAI-compatible sur :8787)."""
    cfg = load_config()
    inference = cfg.get("inference", {})
    start_inference_server(
        host=host or inference.get("host", "127.0.0.1"),
        port=port or inference.get("port", 8787),
        model=model,
        binary=binary,
    )


@run_app.command("cli")
def run_cli(
    invoke: bool = typer.Option(
        True,
        "--invoke/--no-invoke",
        help="Write Akomagni Flow session files for each message.",
    ),
    execute: bool = typer.Option(
        False,
        "--exec/--no-exec",
        help="Run BMAD skill via `uv run render_skill.py` after routing.",
    ),
    inference: bool = typer.Option(
        True,
        "--inference/--no-inference",
        help="Call local inference API after routing (fallback when offline).",
    ),
    auto_swap: bool = typer.Option(
        False,
        "--auto-swap/--no-auto-swap",
        help="Hot-swap GGUF worker when domain model differs from loaded model.",
    ),
    rag: bool | None = typer.Option(
        None,
        "--rag/--no-rag",
        help="Inject RAG retrieval into inference and skill subprocess.",
    ),
) -> None:
    """Interactive CLI — routes messages and optionally creates skill sessions."""
    ensure_default_config()
    cfg = load_config()
    inf_cfg = cfg.get("inference", {})
    mem_cfg = cfg.get("memory", {})
    rag_cfg = cfg.get("rag", {})
    use_rag = bool(rag_cfg.get("inject", True)) if rag is None else rag
    auto_capture = bool(mem_cfg.get("auto_capture", False))
    capture_global = bool(mem_cfg.get("capture_global", False))
    host = inf_cfg.get("host", "127.0.0.1")
    port = int(inf_cfg.get("port", 8787))
    from akomagni.inference.endpoint import resolve_inference_endpoint

    endpoint = resolve_inference_endpoint(cfg)
    # Local default_model must not override cloud domain models (breaks Rodium/Azure).
    model_override = None if not endpoint.is_local else inf_cfg.get("default_model")

    console.print(f"[bold]{_t('run.cli_banner')}[/]")
    inference_online = False
    if inference:
        status = check_health_from_config(cfg)
        inference_online = status.online
        if inference_online:
            console.print(f"[dim]{_t('run.inference_online', url=status.base_url)}[/]")
        else:
            provider = str(inf_cfg.get("provider", "local"))
            if provider == "local":
                console.print(f"[dim]{_t('run.inference_offline')}[/]")
            else:
                console.print(
                    f"[dim]Cloud inference ({provider}) offline — check API key and base URL[/]"
                )

    while True:
        try:
            message = console.input("[cyan]›[/] ")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        if not message.strip():
            continue
        rag_context = ""
        if use_rag:
            rag_context = retrieve_rag_context(
                message,
                project=bool(rag_cfg.get("inject_project", True)),
                limit=int(rag_cfg.get("inject_limit", 3)),
                rrf_k=int(rag_cfg.get("rrf_k", 60)),
            )
            if rag_context:
                console.print("[dim]RAG context injected[/]")
        if invoke:
            result = invoke_skill(
                message,
                execute=execute,
                rag_context=rag_context,
            )
            decision = result.decision
            console.print(
                f"[dim]{decision.badge}[/] → `{decision.skill}` ({decision.confidence:.0%})"
            )
            console.print(f"[green]Session:[/] {result.session_path}")
            if result.skill:
                console.print(f"[dim]Skill path:[/] {result.skill.path}")
            else:
                console.print(
                    "[yellow]Skill not found on disk — run from a BMAD project or link skills.[/]"
                )
            if execute and result.run_result is not None:
                if result.run_result.success:
                    console.print(f"[green]Workflow rendered:[/] {result.run_result.workflow_path}")
                else:
                    console.print(f"[yellow]Skill exec failed:[/] {result.run_result.error}")
        else:
            decision = route_message(message)
            console.print(
                f"[dim]{decision.badge}[/] → `{decision.skill}` ({decision.confidence:.0%})"
            )
            console.print(decision.hint)

        if inference and inference_online:
            chat_plan = plan_inference_chat(message, host=host, port=port)
            domain = chat_plan.domain_plan.classification.domain
            catalog = chat_plan.domain_plan.catalog_name or "n/a"
            console.print(f"[dim]Domain router:[/] {domain} → {catalog}")
            if chat_plan.swap_plan.needs_swap and not auto_swap:
                console.print(f"[yellow]{chat_plan.swap_plan.hint}[/]")
            try:
                reply = try_chat_with_inference(
                    message,
                    decision,
                    host=host,
                    port=port,
                    model=model_override,
                    auto_swap=auto_swap,
                    rag_context=rag_context,
                )
            except InferenceClientError as exc:
                console.print(f"[yellow]{_t('run.inference_failed')}[/] {exc}")
                continue
            if reply:
                console.print(f"\n[bold]Akomagni[/]\n{reply}\n")
                if auto_capture:
                    preview = build_capture_text(message, reply)
                    console.print(f"[dim]{_t('memory.capture_preview')}[/]")
                    console.print(preview[:240] + ("…" if len(preview) > 240 else ""))
                    try:
                        answer = console.input(f"{_t('memory.save_prompt')} ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        console.print()
                        break
                    if answer in {"y", "yes", "o", "oui"}:
                        saved = maybe_prompt_capture(
                            message,
                            reply,
                            global_=capture_global,
                            approved=True,
                        )
                        console.print(f"[green]{_t('memory.saved_to')}:[/] {saved}")
                    elif answer in {"l", "later", "pending", "p", "plus tard"}:
                        proposal = propose_capture(
                            message,
                            reply,
                            global_=capture_global,
                        )
                        console.print(
                            f"[yellow]{_t('memory.queued_capture', capture_id=proposal.capture_id)}[/]"
                        )
            else:
                console.print(f"[yellow]{_t('run.inference_failed')}[/]")


@run_app.command("agent")
def run_agent() -> None:
    """Mode agent (stub — même routeur qu'en CLI pour v0.1)."""
    run_cli()


@run_app.command("ide")
def run_ide() -> None:
    """Open Akomagni IDE (fork VS Code — use `akomagni ide setup` for MCP today)."""
    console.print(
        "[yellow]Akomagni IDE[/] (v1.0 fork) is not bundled yet.\n"
        "Today: [bold]akomagni ide setup[/] then use Cursor or VS Code with MCP.\n"
        "Or: [bold]akomagni run cli[/] · [bold]akomagni serve[/]"
    )
    raise typer.Exit(code=1)


@memory_app.command("status")
def memory_cmd_status() -> None:
    """Afficher l'état de la mémoire centrale et projet."""
    console.print(memory_status())


@memory_app.command("add")
def memory_cmd_add(
    text: str = typer.Argument(..., help="Learning or note to store."),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Store in central memory (~/.akomagni/memory/).",
    ),
    title: str | None = typer.Option(None, "--title", "-t", help="Optional note title."),
) -> None:
    """Add a learning to project or central memory."""
    try:
        path = add_memory(text, global_=global_, title=title)
    except MemoryError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    label = _t("memory.saved_central") if global_ else _t("memory.saved_project")
    console.print(f"[green]{label}:[/] {path}")


@memory_app.command("promote")
def memory_cmd_promote() -> None:
    """Promote project memory into central learnings."""
    try:
        result = promote_project_memory()
    except MemoryError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]{_t('memory.promoted', count=result.files_copied)}[/]\n"
        f"  from: {result.source}\n"
        f"  to:   {result.destination}"
    )


@memory_app.command("pending")
def memory_cmd_pending(
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="List central pending captures.",
    ),
) -> None:
    """List memory captures awaiting approval."""
    pending = list_pending(global_=global_)
    if not pending:
        console.print(f"[dim]{_t('memory.no_pending')}[/]")
        return
    scope = "central" if global_ else "project"
    console.print(f"[bold]{_t('memory.pending_title', scope=scope)}[/]")
    for item in pending:
        preview = item.suggested_text.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "…"
        console.print(f"  [cyan]{item.capture_id}[/]  {item.suggested_title}")
        console.print(f"    {preview}")


@memory_app.command("approve")
def memory_cmd_approve(
    capture_id: str = typer.Argument(..., help="Pending capture id."),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Approve a central pending capture.",
    ),
    title: str | None = typer.Option(None, "--title", "-t", help="Override note title."),
) -> None:
    """Approve a pending capture and save it to memory."""
    try:
        path = approve_capture(capture_id, global_=global_, title=title)
    except CaptureError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]{_t('memory.approved')}:[/] {path}")


@memory_app.command("reject")
def memory_cmd_reject(
    capture_id: str = typer.Argument(..., help="Pending capture id."),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Reject a central pending capture.",
    ),
) -> None:
    """Reject a pending capture without saving."""
    try:
        reject_capture(capture_id, global_=global_)
    except CaptureError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[yellow]{_t('memory.rejected')}[/] capture `{capture_id}`")


@flow_app.command("route")
def flow_route(
    message: str = typer.Argument(..., help="User message to route."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Test Akomagni Flow routing (agent + skill)."""
    decision = route_message(message)
    if json_output:
        import json

        print(
            json.dumps(
                {
                    "agent_id": decision.agent_id,
                    "skill": decision.skill,
                    "confidence": decision.confidence,
                    "badge": decision.badge,
                    "hint": decision.hint,
                    "greenfield": decision.greenfield,
                },
                ensure_ascii=False,
            )
        )
        return
    console.print(f"{decision.badge}  agent={decision.agent_id}  skill={decision.skill}")
    console.print(decision.hint)


@flow_app.command("router-mode")
def flow_router_mode(
    mode: str | None = typer.Argument(
        None,
        help="Flow router mode: heuristic, ml, or auto (omit to show current).",
    ),
) -> None:
    """Show or set Akomagni Flow intent router mode (heuristic / ML / auto)."""
    import yaml

    from akomagni.core.config import CONFIG_PATH

    cfg = load_config()
    router = dict(cfg.get("router", {}))
    if mode is None:
        console.print(f"Flow router mode: [bold]{router.get('mode', 'auto')}[/bold]")
        console.print(
            "[dim]heuristic = regex only · ml = inference classifier · auto = ML if online[/dim]"
        )
        return
    normalized = mode.strip().lower()
    if normalized not in {"heuristic", "ml", "auto"}:
        console.print("[red]Invalid mode. Use: heuristic, ml, or auto[/red]")
        raise typer.Exit(code=1)
    router["mode"] = normalized
    merged = {**cfg, "router": router}
    CONFIG_PATH.write_text(
        yaml.dump(merged, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    console.print(f"[green]Flow router mode set to[/] {normalized}")


@flow_app.command("invoke")
def flow_invoke(
    message: str = typer.Argument(..., help="User message to route and invoke."),
    skill: str | None = typer.Option(None, "--skill", "-s", help="Override skill id."),
    execute: bool = typer.Option(
        False,
        "--exec/--no-exec",
        help="Run BMAD skill via `uv run render_skill.py`.",
    ),
    open_session: bool = typer.Option(
        False,
        "--open",
        help="Print session path prominently for copy-paste.",
    ),
) -> None:
    """Route a message and write a BMAD activation session file."""
    result = invoke_skill(message, skill_override=skill, execute=execute)
    decision = result.decision
    console.print(f"{decision.badge}  skill={decision.skill}")
    console.print(f"[bold green]{_t('flow.session_written')}:[/] {result.session_path}")
    if result.skill:
        console.print(f"Skill: {result.skill.path}")
    else:
        console.print(
            "[yellow]Warning:[/] skill files not found. Run inside a BMAD project "
            "or install skills to ~/.akomagni/skills/"
        )
    if execute and result.run_result is not None:
        if result.run_result.success:
            console.print(
                f"[bold green]{_t('flow.workflow_rendered')}:[/] {result.run_result.workflow_path}"
            )
        else:
            console.print(f"[yellow]{_t('flow.skill_exec_failed')}:[/] {result.run_result.error}")
    state = load_state(result.project_root, discover=result.project_root is not None)
    if state.get("active_agent"):
        console.print(f"Workflow state updated — active agent: {state['active_agent']}")
    if open_session:
        console.print(result.session_path.read_text(encoding="utf-8"))


@flow_app.command("status")
def flow_status() -> None:
    """Show Akomagni Flow workflow state for the current project."""
    state = load_state()
    import yaml

    console.print(yaml.dump(state, allow_unicode=True, default_flow_style=False))


@skill_app.command("list")
def skill_list(
    filter_text: str | None = typer.Option(None, "--filter", "-f", help="Filter by name."),
) -> None:
    """List discovered BMAD skills."""
    skills = discover_skills()
    if not skills:
        console.print(
            f"[yellow]{_t('skill.none_found')}[/] Install BMAD or link skills to ~/.akomagni/skills/"
        )
        raise typer.Exit(code=1)
    for skill_id in sorted(skills):
        if filter_text and filter_text.lower() not in skill_id.lower():
            continue
        info = skills[skill_id]
        module = f" [{info.module}]" if info.module else ""
        console.print(f"[bold]{skill_id}[/]{module}")
        if info.description:
            console.print(f"  {info.description[:120]}{'…' if len(info.description) > 120 else ''}")
        console.print(f"  [dim]{info.path}[/]")


@skill_app.command("path")
def skill_path(
    skill_id: str = typer.Argument(..., help="Skill id, e.g. bmad-brainstorming"),
) -> None:
    """Print the filesystem path for a skill."""
    info = find_skill(skill_id)
    if not info:
        console.print(f"[red]{_t('skill.not_found')}:[/] {skill_id}")
        raise typer.Exit(code=1)
    console.print(info.path)


@router_app.command("classify")
def router_classify(
    message: str = typer.Argument(..., help="Message to classify."),
) -> None:
    """Classify a message into code/design/image/text."""
    result = classify_domain(message)
    console.print(f"domain={result.domain}  confidence={result.confidence:.0%}")
    console.print(result.reason)


@router_app.command("plan")
def router_plan(
    message: str = typer.Argument(..., help="Message to route to a GGUF model."),
) -> None:
    """Show domain model mapping and hot-swap advice."""
    cfg = load_config()
    inf = cfg.get("inference", {})
    host = inf.get("host", "127.0.0.1")
    port = int(inf.get("port", 8787))
    plan = plan_inference_chat(message, host=host, port=port, config=cfg, models_dir=MODELS_DIR)
    domain = plan.domain_plan.classification
    console.print(f"Domain     : {domain.domain} ({domain.confidence:.0%})")
    console.print(f"Catalog    : {plan.domain_plan.catalog_name or 'n/a'}")
    console.print(f"Model path : {plan.domain_plan.model_path or 'not downloaded'}")
    console.print(f"Swap       : {plan.swap_plan.hint}")


@model_app.command("recommend")
def model_recommend() -> None:
    """Recommend models for this machine (uses akomagni doctor)."""
    rec = recommend_models()
    console.print(f"{_t('model.profile')}: [bold]{rec['profile']}[/bold]")
    console.print(f"{_t('model.models')} : {', '.join(rec['models'])}")
    console.print(f"{_t('model.cache')}  : {rec['models_dir']}")
    console.print("\n[dim]akomagni model catalog — list downloadable GGUF models[/dim]")
    console.print("[dim]akomagni model pull <name> — download a model[/dim]")


@model_app.command("catalog")
def model_catalog() -> None:
    """List downloadable GGUF models from the Akomagni catalog."""
    for entry in list_catalog():
        console.print(f"[bold]{entry.name}[/] [{entry.profile}]")
        console.print(f"  {entry.description}")
        console.print(f"  [dim]{entry.repo_id} → {entry.filename}[/]")


@model_app.command("pull")
def model_pull(
    name: str = typer.Argument(..., help="Catalog model name, e.g. qwen2.5-coder-7b"),
    force: bool = typer.Option(False, "--force", help="Re-download even if cached."),
) -> None:
    """Download a GGUF model from Hugging Face."""
    from akomagni.core.config import MODELS_DIR

    try:
        path = pull_model(name, models_dir=MODELS_DIR, force=force)
    except ModelPullError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Model ready:[/] {path}")


@model_app.command("list")
def model_list() -> None:
    """List model profiles from config and downloaded GGUF files."""
    from akomagni.core.config import MODELS_DIR

    cfg = load_config()
    profiles = cfg.get("models", {}).get("profiles", {})
    console.print("[bold]Profiles (config)[/]")
    for name, models in profiles.items():
        console.print(f"  {name}: {', '.join(models)}")
    local = list_local_models(MODELS_DIR)
    console.print("\n[bold]Downloaded (.gguf)[/]")
    if not local:
        console.print("  [dim]none — run: akomagni model pull <name>[/dim]")
        return
    for path in local:
        console.print(f"  {path.relative_to(MODELS_DIR)}")


@inference_app.command("swap")
def inference_swap(
    name: str = typer.Argument(..., help="Catalog model name or GGUF path."),
) -> None:
    """Hot-swap the background llama-server worker to another GGUF model."""
    cfg = load_config()
    inference = cfg.get("inference", {})
    host = inference.get("host", "127.0.0.1")
    port = int(inference.get("port", 8787))
    result = hot_swap_model(
        name,
        models_dir=MODELS_DIR,
        host=host,
        port=port,
        binary=inference.get("binary"),
        ctx_size=int(inference.get("ctx_size", 4096)),
        n_gpu_layers=int(inference.get("n_gpu_layers", -1)),
    )
    if result.swapped:
        console.print(f"[green]{result.message}[/]")
    elif "already loaded" in result.message.lower():
        console.print(f"[dim]{result.message}[/]")
    else:
        console.print(f"[red]{result.message}[/]")
        raise typer.Exit(code=1)


@inference_app.command("stop")
def inference_stop() -> None:
    """Stop the background inference worker."""
    if stop_worker():
        console.print(f"[green]{_t('inference.worker_stopped')}[/]")
    else:
        console.print(f"[dim]{_t('inference.no_worker')}[/]")


@inference_app.command("worker")
def inference_worker() -> None:
    """Show background worker state."""
    state = read_worker_state()
    if state is None:
        console.print(f"[dim]{_t('inference.no_worker_state')}[/]")
        return
    console.print(f"PID   : {state.pid}")
    console.print(f"Model : {state.model_path}")
    console.print(f"API   : http://{state.host}:{state.port}/v1")


@inference_app.command("status")
def inference_status() -> None:
    """Check whether the configured inference provider is online."""
    cfg = load_config()
    status = check_health_from_config(cfg)
    provider = str((cfg.get("inference") or {}).get("provider", "local"))
    if status.online:
        console.print(f"[green]{_t('inference.online')}[/] — {status.base_url} ({provider})")
        if status.models:
            console.print(f"Models: {', '.join(status.models[:5])}")
    else:
        console.print(f"[red]{_t('inference.offline')}[/] — {status.base_url} ({provider})")
        if status.error:
            console.print(status.error)
        raise typer.Exit(code=1)


@inference_app.command("chat")
def inference_chat(
    message: str = typer.Argument(..., help="User message to send to the model."),
    model: str | None = typer.Option(None, "--model", "-m", help="Model id override."),
) -> None:
    """Send one message to /v1/chat/completions and print the reply."""
    from akomagni.inference.endpoint import resolve_inference_endpoint

    cfg = load_config()
    endpoint = resolve_inference_endpoint(cfg)
    inference = cfg.get("inference", {})
    host = inference.get("host", "127.0.0.1")
    port = int(inference.get("port", 8787))
    try:
        reply = chat_completion(
            message,
            host=host,
            port=port,
            base_url=None if endpoint.is_local else endpoint.base_url,
            api_key=endpoint.api_key,
            model=model,
        )
    except InferenceClientError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(reply)


def _rag_settings(cfg: dict) -> dict:
    return cfg.get("rag", {})


def _rag_db_path(*, project: bool) -> Path:
    return default_index_path(project=project)


@rag_app.command("status")
def rag_status(
    project: bool = typer.Option(
        False,
        "--project",
        help="Show project RAG index (.akomagni/rag/) instead of central.",
    ),
) -> None:
    """Show RAG index location and document counts."""
    db_path = _rag_db_path(project=project)
    status = store_status(db_path)
    scope = "project" if project else "central"
    console.print(f"[bold]RAG ({scope})[/]")
    console.print(f"  Index : {status['path']}")
    console.print(f"  Sources: {status['sources']}")
    console.print(f"  Chunks : {status['chunks']}")


@rag_app.command("ingest")
def rag_ingest(
    path: str = typer.Argument(..., help="File or directory to ingest."),
    project: bool = typer.Option(
        False,
        "--project",
        help="Store in project index (.akomagni/rag/).",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Ingest text files recursively when path is a directory.",
    ),
) -> None:
    """Ingest markdown/text files into the hybrid RAG index."""
    cfg = load_config()
    rag_cfg = _rag_settings(cfg)
    db_path = _rag_db_path(project=project)
    try:
        results = ingest_path(
            Path(path),
            db_path=db_path,
            chunk_size=int(rag_cfg.get("chunk_size", 800)),
            overlap=int(rag_cfg.get("chunk_overlap", 120)),
            recursive=recursive,
        )
    except RagIngestError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    for result in results:
        replaced = f" (replaced {result.chunks_replaced})" if result.chunks_replaced else ""
        console.print(
            f"[green]Indexed[/] {result.chunks_added} chunk(s){replaced} — {result.source}"
        )


@rag_app.command("query")
def rag_query(
    text: str = typer.Argument(..., help="Search query."),
    project: bool = typer.Option(
        False,
        "--project",
        help="Search project RAG index.",
    ),
    limit: int = typer.Option(None, "--limit", "-n", help="Max results."),
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Hybrid BM25 + vector search over the RAG index."""
    cfg = load_config()
    rag_cfg = _rag_settings(cfg)
    db_path = _rag_db_path(project=project)
    hits = hybrid_query(
        text,
        db_path=db_path,
        limit=limit or int(rag_cfg.get("default_limit", 5)),
        rrf_k=int(rag_cfg.get("rrf_k", 60)),
    )
    if json_output:
        typer.echo(hits_to_json(hits))
        return
    if not hits:
        console.print("[yellow]No matches.[/] Ingest documents with: akomagni rag ingest <path>")
        raise typer.Exit(code=1)
    for index, hit in enumerate(hits, start=1):
        ranks = []
        if hit.bm25_rank is not None:
            ranks.append(f"bm25=#{hit.bm25_rank}")
        if hit.vector_rank is not None:
            ranks.append(f"vec=#{hit.vector_rank}")
        rank_text = f" ({', '.join(ranks)})" if ranks else ""
        preview = hit.content.replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "…"
        console.print(
            f"[bold]{index}.[/] score={hit.score:.4f}{rank_text}\n"
            f"  [dim]{hit.source}[/]\n"
            f"  {preview}"
        )


@config_app.command("init")
def config_init() -> None:
    """Créer ~/.akomagni/config.yaml avec les valeurs par défaut."""
    path = ensure_default_config()
    console.print(f"{_t('config.initialized')} : [bold]{path}[/]")


@config_app.command("language")
def config_language(
    lang: str | None = typer.Argument(
        None,
        help="Language code: en or fr (omit to show current).",
    ),
) -> None:
    """Show or set CLI output language."""
    import yaml

    from akomagni.core.config import CONFIG_PATH

    cfg = load_config()
    if lang is None:
        console.print(_t("config.language_current", code=_lang()))
        return
    code = lang.strip().lower().split("-")[0]
    if code not in {"en", "fr"}:
        console.print(f"[red]{_t('config.language_invalid', code=lang)}[/]")
        raise typer.Exit(code=1)
    merged = {**cfg, "language": code}
    CONFIG_PATH.write_text(
        yaml.dump(merged, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    console.print(f"[green]{_t('config.language_set', code=code)}[/]")


@config_app.command("extras")
def config_extras(
    pack: str = typer.Argument(..., help="Extra pack: inference, agent, train, or dev."),
) -> None:
    """Install optional dependency packs into the Akomagni Python environment."""
    _install_extras_pack(pack)


@app.command("extras")
def extras_alias(
    pack: str = typer.Argument(..., help="Extra pack: inference, agent, train, or dev."),
) -> None:
    """Alias for ``akomagni config extras``."""
    _install_extras_pack(pack)


def _install_extras_pack(pack: str) -> None:
    import subprocess
    import sys

    allowed = {"inference", "agent", "train", "dev"}
    name = pack.strip().lower()
    if name not in allowed:
        console.print(f"[red]Unknown pack:[/] {pack} (use: {', '.join(sorted(allowed))})")
        raise typer.Exit(code=1)
    console.print(f"[bold]Installing akomagni[{name}][/] …")
    result = subprocess.run(  # nosec B603
        [sys.executable, "-m", "pip", "install", f"akomagni[{name}]"],
        check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(code=1)
    console.print(f"[green]Installed[/] akomagni[{name}]")


@config_app.command("provider")
def config_provider(
    name: str = typer.Argument(..., help="Provider: local, rodium, or azure."),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Azure Foundry endpoint, e.g. https://RESOURCE.openai.azure.com/openai/v1/",
    ),
) -> None:
    """Switch inference provider (local llama-server, Rodium AI, or Azure Foundry)."""
    import yaml

    from akomagni.core.config import CONFIG_PATH
    from akomagni.inference.providers import apply_provider_preset

    provider = name.strip().lower()
    if provider not in {"local", "rodium", "azure"}:
        console.print(f"[red]Unknown provider:[/] {name} (use: local, rodium, azure)")
        raise typer.Exit(code=1)
    if provider == "azure" and not base_url:
        console.print(
            "[yellow]Azure requires --base-url[/] "
            "(https://YOUR-RESOURCE.openai.azure.com/openai/v1/)"
        )
        raise typer.Exit(code=1)

    cfg = load_config()
    try:
        merged = apply_provider_preset(cfg, provider, azure_base_url=base_url)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    CONFIG_PATH.write_text(
        yaml.dump(merged, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    console.print(f"[green]Inference provider set to[/] {provider}")
    if provider == "rodium":
        console.print("Set RODIUMAI_API_KEY (rd_sk_…) then: akomagni inference status")
    elif provider == "azure":
        console.print("Set AZURE_OPENAI_API_KEY then: akomagni inference status")
        console.print(
            "Install Microsoft Foundry Toolkit in VS Code: ms-windows-ai-studio.windows-ai-studio"
        )
    else:
        console.print("Run: akomagni serve --model <name>")


@config_app.command("show")
def config_show() -> None:
    """Afficher la configuration active."""
    cfg = load_config()
    import yaml

    console.print(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))


def _resolve_mcp_workspace(workspace: str | None) -> Path:
    return resolve_workspace(Path(workspace) if workspace else None)


def _mcp_tools(workspace: str | None = None) -> AgentTools:
    cfg = load_config().get("mcp", {})
    root = _resolve_mcp_workspace(workspace)
    return AgentTools(
        root,
        auto_approve=bool(cfg.get("auto_approve", False)),
        shell_timeout=int(cfg.get("shell_timeout", 30)),
    )


@mcp_app.command("serve")
def mcp_serve(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root for sandboxed tools.",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve/--no-auto-approve",
        help="Run destructive tools without approval (not recommended).",
    ),
) -> None:
    """Start the MCP stdio server for agent tools."""
    cfg = load_config().get("mcp", {})
    try:
        run_stdio_server(
            _resolve_mcp_workspace(workspace),
            auto_approve=auto_approve or bool(cfg.get("auto_approve", False)),
            shell_timeout=int(cfg.get("shell_timeout", 30)),
        )
    except RuntimeError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc


@mcp_app.command("pending")
def mcp_pending(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root for pending requests.",
    ),
) -> None:
    """List destructive MCP operations awaiting approval."""
    root = _resolve_mcp_workspace(workspace)
    pending = list_mcp_pending(workspace=root)
    if not pending:
        console.print("[dim]No pending MCP requests.[/]")
        return
    console.print(f"[bold]Pending MCP requests[/] ({root})")
    for item in pending:
        console.print(f"  [cyan]{item.request_id}[/]  {item.tool}  {item.summary}")


@mcp_app.command("approve")
def mcp_approve(
    request_id: str = typer.Argument(..., help="Pending request id."),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root for pending requests.",
    ),
) -> None:
    """Approve and execute a pending destructive MCP operation."""
    root = _resolve_mcp_workspace(workspace)
    tools = _mcp_tools(workspace)
    try:
        request = pop_request(request_id, workspace=root)
        result = tools.execute_pending(request)
    except (ApprovalError, ToolError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    if not result.ok:
        console.print(f"[red]Failed:[/] {result.output}")
        raise typer.Exit(code=1)
    console.print(f"[green]Approved[/] {request.tool}: {result.output}")


@mcp_app.command("reject")
def mcp_reject(
    request_id: str = typer.Argument(..., help="Pending request id."),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace root for pending requests.",
    ),
) -> None:
    """Reject a pending destructive MCP operation."""
    root = _resolve_mcp_workspace(workspace)
    try:
        reject_request(request_id, workspace=root)
    except ApprovalError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[yellow]Rejected[/] request `{request_id}`")


@train_app.command("plan")
def train_plan(
    model: str = typer.Option("qwen2.5-coder-7b", "--model", "-m", help="Base GGUF catalog name."),
) -> None:
    """Build a LoRA training plan from Akomagni Memory learnings."""
    from akomagni.train.lora import TrainError, build_train_plan, collect_learning_examples

    try:
        plan = build_train_plan(base_model=model)
        count = len(collect_learning_examples(plan.dataset_sources))
    except TrainError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[bold]Train plan[/]")
    console.print(f"  Base model : {plan.base_model}")
    console.print(f"  Examples   : {count}")
    console.print("  Sources    :")
    for src in plan.dataset_sources:
        console.print(f"    - {src}")
    console.print(f"  Output     : {plan.output_dir}")
    console.print(f"  [dim]{plan.notes}[/dim]")


@train_app.command("export")
def train_export(
    model: str = typer.Option("qwen2.5-coder-7b", "--model", "-m", help="Base GGUF catalog name."),
    output: str | None = typer.Option(None, "--output", "-o", help="JSONL output path."),
) -> None:
    """Export Memory learnings to JSONL for LoRA fine-tuning."""
    from akomagni.train.lora import TrainError, build_train_plan, export_jsonl

    try:
        plan = build_train_plan(base_model=model)
        dest = Path(output) if output else None
        dataset_path, count = export_jsonl(plan, dest=dest)
    except TrainError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Exported[/] {count} examples → {dataset_path}")


@train_app.command("bundle")
def train_bundle(
    model: str = typer.Option("qwen2.5-coder-7b", "--model", "-m", help="Base GGUF catalog name."),
) -> None:
    """Export dataset + train.yaml + README for external QLoRA trainers."""
    from akomagni.train.lora import TrainError, build_train_plan, prepare_train_bundle

    try:
        plan = build_train_plan(base_model=model)
        bundle = prepare_train_bundle(plan)
    except TrainError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[bold]Train bundle ready[/]")
    console.print(f"  Examples : {bundle.example_count}")
    console.print(f"  Dataset  : {bundle.dataset_path}")
    console.print(f"  Config   : {bundle.config_path}")
    console.print(f"  Readme   : {bundle.readme_path}")
    console.print("[dim]Next: akomagni config extras train && akomagni train run[/dim]")


@train_app.command("run")
def train_run(
    model: str = typer.Option("qwen2.5-coder-7b", "--model", "-m", help="Base catalog / HF model."),
) -> None:
    """Fine-tune with native QLoRA (CUDA) or LoRA fallback from Memory learnings."""
    from akomagni.train.lora import TrainError, build_train_plan
    from akomagni.train.runner import run_train

    try:
        plan = build_train_plan(base_model=model)
        console.print(f"[bold]Training[/] {plan.base_model} …")
        result = run_train(plan)
    except TrainError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[green]Training complete[/]")
    console.print(f"  Method   : {result.method}")
    console.print(f"  HF model : {result.hf_model_id}")
    console.print(f"  Examples : {result.example_count}")
    console.print(f"  Adapter  : {result.adapter_dir}")
    console.print(f"  Dataset  : {result.bundle.dataset_path}")


@ide_app.command("setup")
def ide_setup(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project root (default: current directory).",
    ),
    provider: str = typer.Option(
        "local",
        "--provider",
        "-p",
        help="Cloud guide: local, rodium, or azure.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing MCP config files."),
) -> None:
    """Write Cursor/VS Code MCP config, extensions, and cloud provider guide."""
    from akomagni.ide.setup import IDE_GUIDE_FILENAME, IdeSetupError, write_cursor_mcp_config

    root = Path(workspace) if workspace else Path.cwd()
    prov = provider.strip().lower()
    if prov not in {"local", "rodium", "azure"}:
        console.print(f"[red]Unknown provider:[/] {provider}")
        raise typer.Exit(code=1)
    try:
        result = write_cursor_mcp_config(root, overwrite=force, provider=prov)
    except IdeSetupError as exc:
        console.print(f"[red]{_t('error')}:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[bold]IDE setup complete[/]")
    console.print(f"  Workspace   : {result.workspace}")
    console.print(f"  Cursor MCP  : {result.cursor_config}")
    console.print(f"  VS Code MCP : {result.vscode_config}")
    if result.extensions_config:
        console.print(f"  Extensions  : {result.extensions_config}")
    if result.env_example:
        console.print(f"  Env template: {result.env_example}")
    if result.guide_path:
        console.print(f"  Guide       : {result.guide_path}")
    console.print(f"  Command     : {result.akomagni_command}")
    console.print("\nNext steps:")
    console.print("  1. akomagni config extras agent")
    console.print("  2. akomagni connect rodium   # or: akomagni connect foundry <url>")
    console.print("  3. akomagni ide open         # VS Code + Akomagni Chat sidebar")
    console.print("  4. Restart Cursor/VS Code and enable MCP server akomagni")
    console.print(f"  See {IDE_GUIDE_FILENAME} in your project for full instructions.")


@ide_app.command("open")
def ide_open(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project root to open (default: current directory).",
    ),
) -> None:
    """Open VS Code with Akomagni Chat extension and current project."""
    import shutil
    import subprocess

    from akomagni.inference.providers import AKOMAGNI_CHAT_EXTENSION, AKOMAGNI_CHAT_NAME

    root = Path(workspace) if workspace else Path.cwd()
    if not root.is_dir():
        console.print(f"[red]Workspace not found:[/] {root}")
        raise typer.Exit(code=1)

    code_cmd = shutil.which("code") or shutil.which("code.cmd")
    if not code_cmd:
        console.print("[red]VS Code CLI not found.[/] Install VS Code and enable 'code' in PATH.")
        console.print(
            f"Then install extension: [bold]{AKOMAGNI_CHAT_NAME}[/] ({AKOMAGNI_CHAT_EXTENSION})"
        )
        raise typer.Exit(code=1)

    ext_dir = Path(__file__).resolve().parents[3] / "vscode-extension"
    if (ext_dir / "package.json").is_file():
        subprocess.run(  # nosec B603
            [code_cmd, "--install-extension", str(ext_dir)],
            check=False,
        )

    subprocess.run([code_cmd, str(root)], check=False)  # nosec B603
    console.print(f"[green]Opened[/] {root} in VS Code")
    console.print("Click the Akomagni icon in the sidebar → Chat")
    console.print(
        f"If needed, install [bold]{AKOMAGNI_CHAT_NAME}[/] from Extensions ({AKOMAGNI_CHAT_EXTENSION})"
    )


@ide_app.command("status")
def ide_status_cmd(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Project root (default: current directory).",
    ),
) -> None:
    """Show IDE/MCP readiness for the workspace."""
    from akomagni.ide.setup import ide_status

    root = Path(workspace) if workspace else Path.cwd()
    status = ide_status(root)
    console.print("[bold]IDE status[/]")
    console.print(f"  Workspace           : {status['workspace']}")
    console.print(f"  Cursor MCP config   : {'yes' if status['cursor_config'] else 'no'}")
    console.print(f"  VS Code MCP config  : {'yes' if status['vscode_config'] else 'no'}")
    console.print(f"  Extensions config   : {'yes' if status.get('extensions_config') else 'no'}")
    console.print(
        f"  Agent extra         : {'installed' if status['agent_extra_installed'] else 'missing'}"
    )
    console.print(f"  Inference provider  : {status.get('inference_provider', 'local')}")
    console.print(
        "  API key set         : "
        f"{'yes' if status.get('inference_api_key_set') else 'no (cloud only)'}"
    )
    console.print(f"  akomagni command    : {status['akomagni_command']}")
    console.print(f"  Foundry Toolkit     : {status.get('foundry_toolkit_extension')}")
    console.print(f"  Native IDE          : {status['native_ide']}")
    if status.get("guide_path"):
        console.print(f"  Guide               : {status['guide_path']}")
    if not status["cursor_config"]:
        console.print("\nRun [bold]akomagni ide setup[/] to generate MCP config.")
