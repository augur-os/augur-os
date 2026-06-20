"""Codex CLI adapter."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .cli_agent_base import CliAgentAdapter
from src.config.paths import get_project_root
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType
from src.cli_config.manifest import ServerEntry, load_manifest
from src.cli_config.codex_runtime import build_codex_mcp_entry


PROJECT_ROOT = get_project_root()


def _load_toml(path: Path) -> tuple[dict[str, Any], Optional[str]]:
    if not path.exists():
        return {}, None
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return {}, str(e)


def _toml_format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_format_value(item) for item in value) + "]"
    return json.dumps(str(value))


def _toml_format_key(key: str) -> str:
    if re.match(r"^[A-Za-z0-9_-]+$", key):
        return key
    return json.dumps(key)


def _toml_join_key(parts: tuple[str, ...]) -> str:
    return ".".join(_toml_format_key(part) for part in parts)


def _toml_dump_table(prefix: tuple[str, ...], data: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in data.items() if not isinstance(v, dict)]
    lines.append(f"[{_toml_join_key(prefix)}]")
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{_toml_format_key(key)} = {_toml_format_value(value)}")
    lines.append("")

    for key, value in sorted(data.items(), key=lambda item: item[0]):
        if isinstance(value, dict):
            lines.extend(_toml_dump_table((*prefix, key), value))

    return lines


def _toml_dump_simple(config: dict[str, Any]) -> str:
    lines: list[str] = []
    scalar_items = [(k, v) for k, v in config.items() if not isinstance(v, dict)]
    for key, value in sorted(scalar_items, key=lambda item: item[0]):
        lines.append(f"{_toml_format_key(key)} = {_toml_format_value(value)}")

    table_items = [(k, v) for k, v in config.items() if isinstance(v, dict)]
    for key, value in sorted(table_items, key=lambda item: item[0]):
        lines.extend(_toml_dump_table((key,), value))

    return "\n".join(lines).rstrip() + "\n"


def _codex_args_for_entry(entry: ServerEntry) -> list[str]:
    args = list(entry.args)
    args.extend(entry.per_client_args.get("codex", []))
    return args


def _load_augur_server_entries(
    *,
    existing_server_ids: set[str] | None = None,
) -> list[ServerEntry]:
    manifest = load_manifest(PROJECT_ROOT / "config" / "system" / "mcp_servers.yaml")
    return manifest.all_augur_servers_for_client(
        "codex",
        existing_server_ids=existing_server_ids,
        include_project_scoped=True,
    )


def _build_codex_mcp_entry(entry: ServerEntry | None = None) -> dict[str, Any]:
    """Return a worktree-aware Codex MCP entry."""
    server_args = _codex_args_for_entry(entry) if entry else [
        "-m",
        "augur_core",
        "--client-id",
        "codex",
    ]
    return build_codex_mcp_entry(server_args, configured_root=PROJECT_ROOT)


def _build_codex_mcp_entries(
    *,
    existing_server_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        entry.id: _build_codex_mcp_entry(entry)
        for entry in _load_augur_server_entries(existing_server_ids=existing_server_ids)
    }


class CodexCliAdapter(CliAgentAdapter):
    """Adapter for OpenAI Codex CLI."""

    def __init__(self):
        super().__init__("codex_cli", "codex")

    def get_action_map(self) -> dict[str, str]:
        """Get mapping of intent actions to Codex CLI commands."""
        return {
            "run": "",
            "chat": "",
            "ask": "",
            "edit": "",
            "review": "",
            "debug": "",
            "help": "--help",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": [],
            "mcp_list": [],
            "prompt": ["-q", "respond with just the word ok"],
        }

    def detect(self) -> dict[str, Any]:
        """Detect if Codex CLI is available."""
        installed = False
        running = False
        path = None
        error = None

        try:
            resolved = shutil.which("codex")
            if resolved:
                installed = True
                path = resolved

            running = installed

        except Exception as e:
            error = str(e)

        return {"installed": installed, "running": running, "path": path, "error": error}

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Ensure Codex CLI MCP configuration is set up."""
        config_path = Path.home() / ".codex" / "config.toml"
        current_config, load_error = _load_toml(config_path)
        if load_error:
            return {
                "success": False,
                "changed": False,
                "config_paths": [str(config_path)] if config_path.exists() else [],
                "backup_paths": [],
                "error": f"Failed to parse Codex config: {load_error}",
                "summary": "Codex CLI config parse failed",
            }

        new_config = copy.deepcopy(current_config) if current_config else {}
        mcp_servers = new_config.get("mcp_servers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
            new_config["mcp_servers"] = mcp_servers

        current_augur = {
            server_id: entry
            for server_id, entry in mcp_servers.items()
            if server_id.startswith("augur")
        }
        desired_entries = _build_codex_mcp_entries(
            existing_server_ids=set(current_augur),
        )
        changed = current_augur != desired_entries

        if changed:
            for server_id in list(mcp_servers):
                if server_id.startswith("augur"):
                    del mcp_servers[server_id]
            mcp_servers.update(desired_entries)
            content = _toml_dump_simple(new_config)
            result = self._write_config_safely(config_path, content, format="text")
            if result["success"]:
                backup_paths = [result["backup_path"]] if result["backup_path"] else []
                self._config_paths = [config_path]
                return {
                    "success": True,
                    "changed": True,
                    "config_paths": [str(config_path)],
                    "backup_paths": backup_paths,
                    "error": None,
                    "summary": f"Updated Codex CLI config at {config_path}",
                }
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": result["error"],
                "summary": f"Failed to write Codex CLI config: {result['error']}",
            }

        # Codex auth can come from OPENAI_API_KEY or ~/.codex/auth.json
        has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_auth_file = (Path.home() / ".codex" / "auth.json").exists()
        auth_state = "present" if (has_api_key or has_auth_file) else "missing"

        self._config_paths = [config_path] if config_path.exists() else []
        return {
            "success": True,
            "changed": False,
            "config_paths": [str(config_path)] if config_path.exists() else [],
            "backup_paths": [],
            "error": None,
            "summary": f"Codex CLI configured (auth: {auth_state})",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Codex CLI integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()
        has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_auth_file = (Path.home() / ".codex" / "auth.json").exists()

        # Check 1: Config present (MCP config + API key)
        config_path = Path.home() / ".codex" / "config.toml"
        if config_path.exists():
            config, load_error = _load_toml(config_path)
            if load_error:
                checks["config_present"] = (False, f"Invalid config.toml: {load_error}")
                overall_healthy = False
            else:
                mcp_servers = config.get("mcp_servers") if isinstance(config, dict) else None
                current_augur = {
                    server_id: entry
                    for server_id, entry in (mcp_servers or {}).items()
                    if server_id.startswith("augur")
                } if isinstance(mcp_servers, dict) else {}
                desired_entries = _build_codex_mcp_entries(
                    existing_server_ids=set(current_augur),
                )
                if current_augur == desired_entries:
                    checks["config_present"] = (
                        True,
                        "MCP config contains split dynamic worktree-aware codex runtime args",
                    )
                else:
                    checks["config_present"] = (
                        False,
                        "MCP config missing current split Augur servers",
                    )
                    overall_healthy = False
        else:
            checks["config_present"] = (False, "Codex CLI config.toml not found")
            overall_healthy = False

        if has_api_key or has_auth_file:
            checks["api_key"] = (True, "Codex auth configured")
        else:
            checks["api_key"] = (False, "Neither OPENAI_API_KEY nor ~/.codex/auth.json found")
            overall_healthy = False

        # Check 2: Connectivity
        if detection.get("installed"):
            checks["connectivity"] = (True, "Codex CLI is installed")
        else:
            checks["connectivity"] = (False, "Codex CLI not found in PATH")
            overall_healthy = False

        # Check 3: Tool discovery
        checks["tool_list"] = (None, "Not applicable for CLI")

        # Check 4: End-to-end
        try:
            test_intent = Intent(action="help", params={})
            output = self.render_intent(test_intent)
            if output and output.content:
                checks["end_to_end"] = (True, "Can generate CLI commands")
            else:
                checks["end_to_end"] = (False, "Failed to generate CLI commands")
                overall_healthy = False
        except Exception as e:
            checks["end_to_end"] = (False, f"End-to-end check failed: {e}")
            overall_healthy = False

        if not overall_healthy:
            config_ok = checks.get("config_present", (True, ""))[0]
            if not detection.get("installed") or not config_ok:
                status = "not_configured"
            else:
                status = "degraded"

        return {
            "healthy": overall_healthy,
            "status": status,
            "checks": checks,
            "last_check": datetime.now().isoformat(),
            "error": error,
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """Translate intent to Codex CLI command."""
        action_map = self.get_action_map()

        cmd_action = action_map.get(intent.action, intent.action)
        params_str = " ".join(f"--{k}={v}" for k, v in intent.params.items() if not k.startswith("_"))

        command = f"codex {cmd_action} {params_str}".strip()

        content = f"""# Codex CLI Command

Run this command in your terminal:

```bash
{command}
```

## Parameters
{chr(10).join(f"- `{k}`: {v}" for k, v in intent.params.items()) if intent.params else "None"}

## Note
Ensure Codex CLI is authenticated (`codex login`) or OPENAI_API_KEY is set.
"""

        return AdapterOutput(
            output_type=AdapterOutputType.CLI_COMMAND,
            content=content,
            metadata={"command": command, "action": intent.action},
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "cli"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return []
