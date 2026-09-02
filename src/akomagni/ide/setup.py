"""Generate MCP and IDE configuration for Cursor / VS Code."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from akomagni.inference.providers import (
    FOUNDRY_TOOLKIT_EXTENSION,
    FOUNDRY_TOOLKIT_NAME,
)

IDE_GUIDE_FILENAME = "AKOMAGNI_IDE.md"
ENV_EXAMPLE_FILENAME = ".env.example"


class IdeSetupError(RuntimeError):
    """Raised when IDE/MCP setup cannot complete."""


@dataclass(frozen=True)
class IdeSetupResult:
    """Paths written during IDE/MCP setup."""

    workspace: Path
    cursor_config: Path
    vscode_config: Path
    akomagni_command: str
    extensions_config: Path | None = None
    env_example: Path | None = None
    guide_path: Path | None = None
    provider: str = "local"


def resolve_akomagni_command() -> str:
    """Prefer the akomagni executable on PATH."""
    return shutil.which("akomagni") or "akomagni"


def build_mcp_config(
    workspace: Path,
    *,
    akomagni_command: str | None = None,
) -> dict:
    """Build Cursor-compatible MCP server config for Akomagni agent tools."""
    command = akomagni_command or resolve_akomagni_command()
    workspace_arg = str(workspace.resolve())
    return {
        "mcpServers": {
            "akomagni": {
                "command": command,
                "args": ["mcp", "serve", "--workspace", workspace_arg],
            }
        }
    }


def build_vscode_extensions_recommendations(*, provider: str = "local") -> dict[str, list[str]]:
    """Recommend VS Code extensions for cloud AI workflows."""
    recommendations = [FOUNDRY_TOOLKIT_EXTENSION]
    if provider == "rodium":
        recommendations.append("openai.chatgpt")
    return {"recommendations": recommendations, "unwantedRecommendations": []}


def build_env_example(provider: str = "local") -> str:
    """Return a `.env.example` template for cloud providers."""
    lines = [
        "# Akomagni cloud inference — copy to .env and fill in values",
        "# Never commit real API keys to git.",
        "",
    ]
    if provider in {"rodium", "local"}:
        lines.extend(
            [
                "# Rodium AI — https://www.rodiumai.io/docs",
                "# OpenAI-compatible API at https://api.rodiumai.io/v1",
                "RODIUMAI_API_KEY=rd_sk_your_key_here",
                "",
            ]
        )
    if provider in {"azure", "local"}:
        lines.extend(
            [
                "# Azure AI Foundry — https://ai.azure.com/",
                "# Base URL: https://YOUR-RESOURCE.openai.azure.com/openai/v1/",
                "AZURE_OPENAI_API_KEY=your_azure_key_here",
                "AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/openai/v1/",
                "",
            ]
        )
    lines.extend(
        [
            "# Akomagni CLI provider selection:",
            "#   akomagni config provider rodium",
            "#   akomagni config provider azure --base-url https://YOUR-RESOURCE.openai.azure.com/openai/v1/",
            "#   akomagni config provider local",
        ]
    )
    return "\n".join(lines) + "\n"


def build_ide_guide(*, provider: str = "local") -> str:
    """Markdown guide for IDE + cloud provider setup."""
    lines = [
        "# Akomagni IDE setup",
        "",
        "This project is configured for Akomagni BMAD Flow + MCP agent tools.",
        "",
        "## 1. MCP sandbox (filesystem, shell, git)",
        "",
        "- Cursor: open **Settings → MCP** and enable server `akomagni`",
        "- VS Code: install agent extra (`akomagni config extras agent`) and enable MCP",
        "",
        "## 2. Cloud inference (optional)",
        "",
    ]
    if provider in {"rodium", "local"}:
        lines.extend(
            [
                "### Rodium AI (online, prepaid RODI)",
                "",
                "1. Create an API key at https://www.rodiumai.io/dashboard (`rd_sk_…`)",
                "2. Set `RODIUMAI_API_KEY` in your environment or `.env`",
                "3. Run `akomagni config provider rodium`",
                "4. Use `akomagni run cli` — models route via https://api.rodiumai.io/v1",
                "",
                "Docs: https://www.rodiumai.io/docs",
                "",
            ]
        )
    if provider in {"azure", "local"}:
        lines.extend(
            [
                "### Azure AI Foundry (enterprise cloud)",
                "",
                "1. Create a Foundry project at https://ai.azure.com/",
                "2. Deploy models and note deployment names + endpoint URL",
                "3. Set `AZURE_OPENAI_API_KEY` and configure base URL:",
                "   `akomagni config provider azure --base-url https://YOUR-RESOURCE.openai.azure.com/openai/v1/`",
                "4. Install **Microsoft Foundry Toolkit** in VS Code:",
                f"   Extension ID: `{FOUNDRY_TOOLKIT_EXTENSION}`",
                "5. Sign in to Azure in the Toolkit sidebar → Model Playground for chat",
                "",
                "Docs: https://learn.microsoft.com/azure/foundry/how-to/develop/get-started-projects-visual-studio-code",
                "",
            ]
        )
    lines.extend(
        [
            "## 3. Local inference (offline)",
            "",
            "```bash",
            "akomagni config provider local",
            "akomagni config extras inference",
            "akomagni model pull qwen2.5-coder-7b",
            "akomagni serve --model qwen2.5-coder-7b",
            "```",
            "",
            "## Commands",
            "",
            "- `akomagni ide status` — check MCP + provider readiness",
            '- `akomagni flow invoke "your task"` — route to BMAD agent',
            "- `akomagni run cli` — interactive chat with inference",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise IdeSetupError(
            f"{path} already exists — re-run with --force to overwrite, or merge manually."
        )
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise IdeSetupError(
            f"{path} already exists — re-run with --force to overwrite, or merge manually."
        )
    path.write_text(text, encoding="utf-8")


def write_cursor_mcp_config(
    workspace: Path | None = None,
    *,
    overwrite: bool = False,
    akomagni_command: str | None = None,
    provider: str = "local",
    write_guide: bool = True,
) -> IdeSetupResult:
    """Write MCP config, VS Code extensions, env template, and IDE guide."""
    root = (workspace or Path.cwd()).resolve()
    if not root.is_dir():
        raise IdeSetupError(f"workspace does not exist: {root}")

    command = akomagni_command or resolve_akomagni_command()
    payload = build_mcp_config(root, akomagni_command=command)
    text = json.dumps(payload, indent=2) + "\n"

    cursor_dir = root / ".cursor"
    vscode_dir = root / ".vscode"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    vscode_dir.mkdir(parents=True, exist_ok=True)

    cursor_config = cursor_dir / "mcp.json"
    vscode_config = vscode_dir / "mcp.json"

    for path in (cursor_config, vscode_config):
        if path.exists() and not overwrite:
            raise IdeSetupError(
                f"{path} already exists — re-run with --force to overwrite, or merge manually."
            )

    cursor_config.write_text(text, encoding="utf-8")
    vscode_config.write_text(text, encoding="utf-8")

    extensions_config = vscode_dir / "extensions.json"
    _write_json(
        extensions_config,
        build_vscode_extensions_recommendations(provider=provider),
        overwrite=overwrite,
    )

    env_example = root / ENV_EXAMPLE_FILENAME
    _write_text(env_example, build_env_example(provider=provider), overwrite=overwrite)

    guide_path = None
    if write_guide:
        guide_path = root / IDE_GUIDE_FILENAME
        _write_text(guide_path, build_ide_guide(provider=provider), overwrite=overwrite)

    return IdeSetupResult(
        workspace=root,
        cursor_config=cursor_config,
        vscode_config=vscode_config,
        akomagni_command=command,
        extensions_config=extensions_config,
        env_example=env_example,
        guide_path=guide_path,
        provider=provider,
    )


def ide_status(workspace: Path | None = None) -> dict[str, object]:
    """Summarize IDE/MCP readiness for the current workspace."""
    from akomagni.inference.endpoint import provider_status

    root = (workspace or Path.cwd()).resolve()
    cursor_config = root / ".cursor" / "mcp.json"
    vscode_config = root / ".vscode" / "mcp.json"
    extensions_config = root / ".vscode" / "extensions.json"
    guide_path = root / IDE_GUIDE_FILENAME

    agent_installed = True
    try:
        import mcp  # noqa: F401
    except ImportError:
        agent_installed = False

    prov = provider_status()
    return {
        "workspace": str(root),
        "cursor_config": cursor_config.exists(),
        "vscode_config": vscode_config.exists(),
        "extensions_config": extensions_config.exists(),
        "guide_path": str(guide_path) if guide_path.exists() else None,
        "agent_extra_installed": agent_installed,
        "akomagni_command": resolve_akomagni_command(),
        "inference_provider": prov["provider"],
        "inference_api_key_set": prov["api_key_set"],
        "foundry_toolkit_extension": FOUNDRY_TOOLKIT_EXTENSION,
        "foundry_toolkit_name": FOUNDRY_TOOLKIT_NAME,
        "native_ide": "planned-v1.0",
    }
