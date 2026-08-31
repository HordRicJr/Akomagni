"""Akomagni CLI — doctor, serve, flow, memory."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from akomagni import __version__
from akomagni.core.config import MODELS_DIR, ensure_default_config, load_config
from akomagni.core.doctor import run_doctor
from akomagni.core.registry import list_catalog, recommend_models
from akomagni.core.router import classify_domain
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import load_state
from akomagni.inference.chat import plan_inference_chat, try_chat_with_inference
from akomagni.inference.client import InferenceClientError, chat_completion, check_health
from akomagni.inference.llama import list_local_models
from akomagni.inference.pull import ModelPullError, pull_model
from akomagni.inference.server import serve as start_inference_server
from akomagni.inference.worker import hot_swap_model, read_worker_state, stop_worker
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

app.add_typer(run_app, name="run")
app.add_typer(memory_app, name="memory")
app.add_typer(flow_app, name="flow")
app.add_typer(config_app, name="config")
app.add_typer(skill_app, name="skill")
app.add_typer(model_app, name="model")
app.add_typer(router_app, name="router")
app.add_typer(inference_app, name="inference")
app.add_typer(rag_app, name="rag")


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
    report = run_doctor()
    if json_output:
        import json

        console.print_json(json.dumps(report, indent=2))
        return
    from rich.markup import escape

    for line in report["summary"].splitlines():
        if line.startswith("  Profil recommandé"):
            console.print(f"  Profil recommandé : [bold]{report['profile']}[/bold]")
        elif line.startswith("  Modèles suggérés"):
            console.print(f"  Modèles suggérés  : {', '.join(report['models'])}")
        elif "[bold]" in line:
            console.print(line.replace("[bold]", "").replace("[/bold]", ""))
        else:
            console.print(escape(line))


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
    model_override = inf_cfg.get("default_model")

    console.print("[bold]Akomagni CLI[/] — type a message (Ctrl+C to quit).")
    inference_online = False
    if inference:
        status = check_health(host=host, port=port)
        inference_online = status.online
        if inference_online:
            console.print(f"[dim]Inference online — {status.base_url}[/]")
        else:
            console.print("[dim]Inference offline — routing only (run: akomagni serve)[/]")

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
            reply = try_chat_with_inference(
                message,
                decision,
                host=host,
                port=port,
                model=model_override,
                auto_swap=auto_swap,
                rag_context=rag_context,
            )
            if reply:
                console.print(f"\n[bold]Akomagni[/]\n{reply}\n")
                if auto_capture:
                    preview = build_capture_text(message, reply)
                    console.print("[dim]Memory capture preview:[/]")
                    console.print(preview[:240] + ("…" if len(preview) > 240 else ""))
                    try:
                        answer = console.input("Save to memory? [y/N/later] ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        console.print()
                        break
                    if answer in {"y", "yes"}:
                        saved = maybe_prompt_capture(
                            message,
                            reply,
                            global_=capture_global,
                            approved=True,
                        )
                        console.print(f"[green]Saved to memory:[/] {saved}")
                    elif answer in {"l", "later", "pending"}:
                        proposal = propose_capture(
                            message,
                            reply,
                            global_=capture_global,
                        )
                        console.print(
                            f"[yellow]Queued pending capture[/] `{proposal.capture_id}` "
                            f"(akomagni memory approve {proposal.capture_id})"
                        )
            else:
                console.print("[yellow]Inference call failed — route/session kept.[/]")


@run_app.command("agent")
def run_agent() -> None:
    """Mode agent (stub — même routeur qu'en CLI pour v0.1)."""
    run_cli()


@run_app.command("ide")
def run_ide() -> None:
    """Ouvrir Akomagni IDE (fork VS Code — pas encore intégré en v0.1)."""
    console.print(
        "[yellow]Akomagni IDE[/] : build depuis [bold]ide/[/] (fork Code-OSS) — à venir.\n"
        "En attendant : [bold]akomagni run cli[/] ou [bold]akomagni serve[/]."
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
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    scope = "central" if global_ else "project"
    console.print(f"[green]Saved ({scope}):[/] {path}")


@memory_app.command("promote")
def memory_cmd_promote() -> None:
    """Promote project memory into central learnings."""
    try:
        result = promote_project_memory()
    except MemoryError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]Promoted[/] {result.files_copied} file(s)\n"
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
        console.print("[dim]No pending captures.[/]")
        return
    scope = "central" if global_ else "project"
    console.print(f"[bold]Pending captures ({scope})[/]")
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
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Approved and saved:[/] {path}")


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
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[yellow]Rejected[/] capture `{capture_id}`")


@flow_app.command("route")
def flow_route(
    message: str = typer.Argument(..., help="User message to route."),
) -> None:
    """Test Akomagni Flow routing (agent + skill)."""
    decision = route_message(message)
    console.print(f"{decision.badge}  agent={decision.agent_id}  skill={decision.skill}")
    console.print(decision.hint)


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
    console.print(f"[bold green]Session written:[/] {result.session_path}")
    if result.skill:
        console.print(f"Skill: {result.skill.path}")
    else:
        console.print(
            "[yellow]Warning:[/] skill files not found. Run inside a BMAD project "
            "or install skills to ~/.akomagni/skills/"
        )
    if execute and result.run_result is not None:
        if result.run_result.success:
            console.print(f"[bold green]Workflow rendered:[/] {result.run_result.workflow_path}")
        else:
            console.print(f"[yellow]Skill exec failed:[/] {result.run_result.error}")
    state = load_state(result.project_root)
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
            "[yellow]No skills found.[/] Install BMAD or link skills to ~/.akomagni/skills/"
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
        console.print(f"[red]Skill not found:[/] {skill_id}")
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
    console.print(f"Profile: [bold]{rec['profile']}[/bold]")
    console.print(f"Models : {', '.join(rec['models'])}")
    console.print(f"Cache  : {rec['models_dir']}")
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
        console.print("[green]Inference worker stopped.[/]")
    else:
        console.print("[dim]No background worker running.[/]")


@inference_app.command("worker")
def inference_worker() -> None:
    """Show background worker state."""
    state = read_worker_state()
    if state is None:
        console.print("[dim]No background worker state.[/]")
        return
    console.print(f"PID   : {state.pid}")
    console.print(f"Model : {state.model_path}")
    console.print(f"API   : http://{state.host}:{state.port}/v1")


@inference_app.command("status")
def inference_status() -> None:
    """Check whether the local OpenAI-compatible API is online."""
    cfg = load_config()
    inference = cfg.get("inference", {})
    host = inference.get("host", "127.0.0.1")
    port = int(inference.get("port", 8787))
    status = check_health(host=host, port=port)
    if status.online:
        console.print(f"[green]Online[/] — {status.base_url}")
        if status.models:
            console.print(f"Models: {', '.join(status.models)}")
    else:
        console.print(f"[red]Offline[/] — {status.base_url}")
        if status.error:
            console.print(status.error)
        raise typer.Exit(code=1)


@inference_app.command("chat")
def inference_chat(
    message: str = typer.Argument(..., help="User message to send to the model."),
    model: str | None = typer.Option(None, "--model", "-m", help="Model id override."),
) -> None:
    """Send one message to /v1/chat/completions and print the reply."""
    cfg = load_config()
    inference = cfg.get("inference", {})
    host = inference.get("host", "127.0.0.1")
    port = int(inference.get("port", 8787))
    try:
        reply = chat_completion(message, host=host, port=port, model=model)
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
    console.print(f"Config initialisée : [bold]{path}[/]")


@config_app.command("show")
def config_show() -> None:
    """Afficher la configuration active."""
    cfg = load_config()
    import yaml

    console.print(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))
