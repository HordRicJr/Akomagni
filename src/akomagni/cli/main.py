"""Akomagni CLI — doctor, serve, flow, memory."""

from __future__ import annotations

import typer
from rich.console import Console

from akomagni import __version__
from akomagni.core.config import ensure_default_config, load_config
from akomagni.core.doctor import run_doctor
from akomagni.core.registry import recommend_models
from akomagni.flow.orchestrator import route_message
from akomagni.flow.state import load_state
from akomagni.inference.server import serve_stub
from akomagni.memory.store import memory_status
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

app.add_typer(run_app, name="run")
app.add_typer(memory_app, name="memory")
app.add_typer(flow_app, name="flow")
app.add_typer(config_app, name="config")
app.add_typer(skill_app, name="skill")
app.add_typer(model_app, name="model")


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
    host: str = typer.Option("127.0.0.1", help="Hôte API OpenAI-compatible."),
    port: int = typer.Option(8787, help="Port API."),
) -> None:
    """Démarrer le serveur d'inférence local (stub v0.1)."""
    serve_stub(host=host, port=port)


@run_app.command("cli")
def run_cli(
    invoke: bool = typer.Option(
        True,
        "--invoke/--no-invoke",
        help="Write Akomagni Flow session files for each message.",
    ),
) -> None:
    """Interactive CLI — routes messages and optionally creates skill sessions."""
    ensure_default_config()
    console.print("[bold]Akomagni CLI[/] — type a message (Ctrl+C to quit).")
    while True:
        try:
            message = console.input("[cyan]›[/] ")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        if not message.strip():
            continue
        if invoke:
            result = invoke_skill(message)
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
        else:
            decision = route_message(message)
            console.print(
                f"[dim]{decision.badge}[/] → `{decision.skill}` ({decision.confidence:.0%})"
            )
            console.print(decision.hint)


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
    open_session: bool = typer.Option(
        False,
        "--open",
        help="Print session path prominently for copy-paste.",
    ),
) -> None:
    """Route a message and write a BMAD activation session file."""
    result = invoke_skill(message, skill_override=skill)
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


@model_app.command("recommend")
def model_recommend() -> None:
    """Recommend models for this machine (uses akomagni doctor)."""
    rec = recommend_models()
    console.print(f"Profile: [bold]{rec['profile']}[/bold]")
    console.print(f"Models : {', '.join(rec['models'])}")
    console.print(f"Cache  : {rec['models_dir']}")
    console.print("\n[dim]akomagni model pull — coming in v0.2[/dim]")


@model_app.command("list")
def model_list() -> None:
    """List model profiles from config."""
    cfg = load_config()
    profiles = cfg.get("models", {}).get("profiles", {})
    for name, models in profiles.items():
        console.print(f"[bold]{name}[/]: {', '.join(models)}")


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
