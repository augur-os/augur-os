"""Adapter for OpenCode CLI - AI coding assistant."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from .cli_agent_base import CliAgentAdapter
from ._plugin_pack import ensure_plugin_pack_formatters_path
from src.lib.ai.ide_intent import Intent
from src.config.paths import get_project_root


class OpenCodeAdapter(CliAgentAdapter):
    """Adapter for OpenCode (CLI)."""

    def __init__(self):
        super().__init__("opencode", "opencode")

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Verify if OpenCode CLI is available and configured."""
        detection = self.detect()
        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "error": "OpenCode CLI ('opencode') not found in PATH.",
                "summary": "To install OpenCode, run: `brew install opencode` or visit https://opencode.ai",
            }

        try:
            # OpenCode reads config from ~/.config/opencode/config.json
            config_dir = Path.home() / ".config" / "opencode"
            config_path = config_dir / "config.json"

            project_root = get_project_root()
            venv_python = project_root / ".venv" / "bin" / "python3"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = "python3"

            ensure_plugin_pack_formatters_path(project_root)
            from mcp_config import build_augur_mcp_servers
            servers = build_augur_mcp_servers(project_root, python_cmd, "opencode")
            desired_servers = {}
            for k, v in servers.items():
                desired_servers[k] = {
                    "type": "local",
                    "command": [v["command"]] + v["args"],
                    "enabled": True,
                    "environment": v["env"],
                }

            current_config = self._read_config(config_path, format="json") or {}
            if not isinstance(current_config, dict):
                current_config = {}

            # Ensure $schema is present
            if "$schema" not in current_config:
                current_config["$schema"] = "https://opencode.ai/config.json"

            mcp_servers = current_config.get("mcp")
            if not isinstance(mcp_servers, dict):
                mcp_servers = {}
                current_config["mcp"] = mcp_servers

            changed = False
            backup_paths = []
            
            for k in list(mcp_servers.keys()):
                if k.startswith("augur") and k not in desired_servers:
                    del mcp_servers[k]
                    changed = True

            for k, v in desired_servers.items():
                if mcp_servers.get(k) != v:
                    mcp_servers[k] = v
                    changed = True

            if changed:
                result = self._write_config_safely(
                    config_path,
                    json.dumps(current_config, indent=2),
                    format="json",
                )
                if result["success"]:
                    if result["backup_path"]:
                        backup_paths.append(result["backup_path"])
                    return {
                        "success": True,
                        "changed": True,
                        "config_paths": [str(config_path)],
                        "backup_paths": backup_paths,
                        "summary": f"Updated OpenCode MCP config at {config_path}",
                    }
                return {
                    "success": False,
                    "changed": False,
                    "error": result["error"],
                    "summary": f"Failed to write OpenCode config: {result['error']}",
                }

            return {
                "success": True,
                "changed": False,
                "config_paths": [str(config_path)] if config_path.exists() else [],
                "summary": "OpenCode MCP config already up to date. Run `opencode auth` to configure providers if needed.",
            }

        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "error": f"Failed to check config: {e}",
                "summary": "Could not verify OpenCode configuration.",
            }

    def get_action_map(self) -> dict[str, str]:
        """
        Get mapping of intent actions to OpenCode CLI commands.

        Returns:
            Dict mapping action names to CLI command strings
        """
        return {
            "run": "run",
            "chat": "run",
            "ask": "run",
            "edit": "run",
            "review": "run",
            "debug": "debug",
            "mcp": "mcp",
            "models": "models",
            "stats": "stats",
            "help": "--help",
            "pr": "pr",
            "github": "github",
            "session": "session",
            "serve": "serve",
            "web": "web",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": [],
            "mcp_list": ["mcp", "list"],
            "prompt": ["-p", "respond with just the word 'ok'"],
        }

    def get_capabilities(self):
        """
        Get agent capabilities for routing.

        Returns:
            AgentCapabilities object
        """
        from src.lib.ai.agent_capabilities import AgentCapabilities

        health = self.health_check()
        health_status = health.get("status", "unknown")

        return AgentCapabilities(
            agent_name=self.ide_name,
            agent_type="cli",
            has_sprint_context=True,
            has_slash_commands=True,
            has_factory_insights=True,
            can_execute_code=True,
            can_modify_files=True,
            specializations=[
                "code_generation",
                "debugging",
                "testing",
                "github",
                "pr_review",
            ],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
