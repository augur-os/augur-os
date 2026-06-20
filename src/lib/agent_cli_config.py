"""Shared CLI agent configuration resolver.

Runtime routing chooses the client. The vault CLI registry chooses the command.
This keeps passive agent work, MCP oneshot calls, and retry helpers from growing
separate hardcoded defaults.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.config import paths as config_paths

CLIENT_TO_CLI_ID: dict[str, str] = {
    "claude-code": "claude",
    "claude_code": "claude",
    "claude-desktop": "claude",
    "claude_desktop": "claude",
    "cursor": "cursor-cli",
    "copilot": "copilot-cli",
}


@dataclass(frozen=True)
class AgentCliConfig:
    cli_id: str
    command: list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    source: str = "implicit"
    config_path: str | None = None
    error: str | None = None


def canonical_cli_id(client_id: str) -> str:
    """Map UI/client ids to cli_agents.yaml ids."""
    normalized = client_id.strip().lower()
    return CLIENT_TO_CLI_ID.get(normalized, normalized)


def _resolve_client_routing(action_id: str) -> Any | None:
    try:
        from src.mcp.augur_framework.tools.infrastructure.client_resolver import (
            ClientResolver,
        )

        return ClientResolver().resolve(action_id)
    except Exception:
        return None


def load_cli_agents() -> tuple[Path | None, dict[str, Any]]:
    config_path = config_paths.get_vault_config_dir() / "ai" / "cli_agents.yaml"
    if not config_path.exists():
        return config_path, {}
    try:
        import yaml  # type: ignore

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return config_path, {}

    agents = raw.get("agents")
    return config_path, agents if isinstance(agents, dict) else {}


def configured_agent_command(
    agent_data: Any,
    command_fields: Iterable[str] = ("print_cmd", "cmd"),
) -> list[str] | None:
    if not isinstance(agent_data, dict):
        return None
    for key in command_fields:
        value = agent_data.get(key)
        if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
            return [item.strip() for item in value]
    return None


def configured_agent_env(agent_data: Any) -> dict[str, str]:
    if not isinstance(agent_data, dict):
        return {}
    raw_env = agent_data.get("env")
    if not isinstance(raw_env, dict):
        return {}
    return {str(key): str(value) for key, value in raw_env.items() if isinstance(key, str) and isinstance(value, str)}


def first_configured_agent(
    agents: dict[str, Any],
    command_fields: Iterable[str] = ("print_cmd", "cmd"),
) -> str | None:
    for cli_id, agent_data in agents.items():
        if isinstance(cli_id, str) and cli_id.strip() and configured_agent_command(agent_data, command_fields):
            return cli_id.strip()
    return None


def resolve_agent_cli_config(
    action_id: str | None = None,
    *,
    command_fields: Iterable[str] = ("print_cmd", "cmd"),
    allow_local: bool = False,
) -> AgentCliConfig:
    """Resolve an agent CLI from runtime routing and cli_agents.yaml.

    Explicit routing wins when configured. Without a route, the first usable
    command in cli_agents.yaml is the implicit default. No fallback is read from
    config/system/llm.yaml.
    """
    config_path, agents = load_cli_agents()
    routed = _resolve_client_routing(action_id) if action_id else None
    source = getattr(routed, "source", "implicit") if routed is not None else "implicit"
    routed_client = getattr(routed, "client_id", "") if routed is not None else ""
    routed_type = getattr(routed, "client_type", "") if routed is not None else ""

    if source != "implicit" and routed_client:
        cli_id = canonical_cli_id(routed_client)
        if (routed_type == "local" or cli_id == "ollama") and not allow_local:
            return AgentCliConfig(
                cli_id=cli_id or "ollama",
                source=source,
                config_path=str(config_path) if config_path else None,
                error=(
                    "configured default client resolves to local Ollama; "
                    "passive agent execution requires a remote or IDE CLI agent"
                ),
            )

        agent_data = agents.get(cli_id)
        if not isinstance(agent_data, dict):
            return AgentCliConfig(
                cli_id=cli_id,
                source=source,
                config_path=str(config_path) if config_path else None,
                error=(
                    f"configured default client '{routed_client}' maps to CLI agent "
                    f"'{cli_id}', but that agent is not in cli_agents.yaml"
                ),
            )

        command = configured_agent_command(agent_data, command_fields)
        if command is None:
            fields = ", ".join(command_fields)
            return AgentCliConfig(
                cli_id=cli_id,
                source=source,
                config_path=str(config_path) if config_path else None,
                error=f"CLI agent '{cli_id}' does not define any of: {fields}",
            )

        return AgentCliConfig(
            cli_id=cli_id,
            command=command,
            env=configured_agent_env(agent_data),
            source=source,
            config_path=str(config_path) if config_path else None,
        )

    cli_id = first_configured_agent(agents, command_fields)
    if not cli_id:
        return AgentCliConfig(
            cli_id="",
            source="cli_agents",
            config_path=str(config_path) if config_path else None,
            error="no usable CLI command found in cli_agents.yaml",
        )

    agent_data = agents.get(cli_id)
    return AgentCliConfig(
        cli_id=cli_id,
        command=configured_agent_command(agent_data, command_fields),
        env=configured_agent_env(agent_data),
        source="cli_agents",
        config_path=str(config_path) if config_path else None,
    )


def _normalize_cli_id(value: str) -> str:
    raw = value.strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".cmd", ".exe", ".bat", ".com"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    return canonical_cli_id(raw)


def resolve_cli_path(cli_name: str) -> str | None:
    normalized = _normalize_cli_id(cli_name)
    if normalized == "claude":
        claude_exe = (
            Path.home()
            / "AppData"
            / "Roaming"
            / "npm"
            / "node_modules"
            / "@anthropic-ai"
            / "claude-code"
            / "bin"
            / "claude.exe"
        )
        if claude_exe.exists():
            return str(claude_exe)

    resolved = shutil.which(cli_name)
    if resolved:
        return resolved

    home = Path.home()
    candidates = [
        home / "AppData" / "Roaming" / "npm" / f"{cli_name}.cmd",
        home / "AppData" / "Roaming" / "npm" / cli_name,
        home / ".local" / "bin" / cli_name,
        Path("/usr/local/bin") / cli_name,
        Path("/opt/homebrew/bin") / cli_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def build_agent_command(
    cli_path: str,
    cli_name: str,
    prompt: str,
    *,
    configured_command: list[str] | None = None,
    job_dir: Path | None = None,
) -> list[str]:
    normalized = _normalize_cli_id(cli_name)

    if configured_command:
        cmd = [cli_path, *configured_command[1:]]
        if normalized == "claude":
            if "--output-format" in cmd and "stream-json" in cmd and "--verbose" not in cmd:
                cmd.append("--verbose")
            if not any(arg == "--dangerously-skip-permissions" for arg in cmd):
                if "--permission-mode" in cmd:
                    permission_index = cmd.index("--permission-mode")
                    del cmd[permission_index : permission_index + 2]
                cmd.append("--dangerously-skip-permissions")
            if job_dir is not None and not any(arg.startswith("--add-dir") for arg in cmd):
                cmd.append(f"--add-dir={job_dir}")
        return [*cmd, prompt]

    if normalized == "claude":
        cmd = [
            cli_path,
            "--print",
            "--output-format",
            "text",
            "--permission-mode",
            "acceptEdits",
        ]
        if job_dir is not None:
            cmd.append(f"--add-dir={job_dir}")
        return [*cmd, prompt]
    if normalized == "gemini":
        return [cli_path, "-p", prompt]
    if normalized == "codex":
        return [cli_path, "exec", "--skip-git-repo-check", prompt]
    return [cli_path, "--print", prompt]


def get_cli_candidate_ids(
    *,
    command_fields: Iterable[str] = ("cmd", "print_cmd"),
) -> list[str]:
    """Return CLI ids from cli_agents.yaml in configured order."""
    _, agents = load_cli_agents()
    return [
        cli_id.strip()
        for cli_id, agent_data in agents.items()
        if isinstance(cli_id, str) and cli_id.strip() and configured_agent_command(agent_data, command_fields)
    ]
