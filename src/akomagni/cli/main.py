"""Akomagni CLI — doctor, serve, flow, memory."""

from __future__ import annotations

import typer
from rich.console import Console

from akomagni import __version__
from akomagni.core.config import ensure_default_config, load_config
from akomagni.core.doctor import run_doctor
from akomagni.flow.orchestrator import route_message
from akomagni.inference.server import serve_stub
from akomagni.memory.store import memory_status

app = typer.Typer(
    name="akomagni",
    help="Akomagni — poste de travail IA local (code, design, image, business).",
    no_args_is_help=True,
)
console = Console()
run_app = typer.Typer(help="Lancer un mode Akomagni.")
memory_app = typer.Typer(help="Akomagni Memory — centrale + projet.")
flow_app = typer.Typer(help="Akomagni Flow — orchestration agents BMAD.")
config_app = typer.Typer(help="Configuration ~/.akomagni/config.yaml")

app.add_typer(run_app, name="run")
app.add_typer(memory_app, name="memory")
app.add_typer(flow_app, name="flow")
app.add_typer(config_app, name="config")


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
def run_cli() -> None:
    """Mode CLI interactif (stub v0.1)."""
    ensure_default_config()
    console.print("[bold]Akomagni CLI[/] — tape ton message (Ctrl+C pour quitter).")
    while True:
        try:
            message = console.input("[cyan]›[/] ")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        if not message.strip():
            continue
        decision = route_message(message)
        console.print(f"[dim]{decision.badge}[/] → skill `{decision.skill}` ({decision.confidence:.0%})")
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
    message: str = typer.Argument(..., help="Message utilisateur à router."),
) -> None:
    """Tester le routage Akomagni Flow (agent + skill)."""
    decision = route_message(message)
    console.print(f"{decision.badge}  agent={decision.agent_id}  skill={decision.skill}")
    console.print(decision.hint)


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
