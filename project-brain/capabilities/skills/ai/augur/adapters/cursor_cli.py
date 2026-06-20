"""Adapter for Cursor Agent CLI - AI coding agent from Cursor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from .cli_agent_base import CliAgentAdapter
from ._plugin_pack import ensure_plugin_pack_formatters_path
from src.lib.ai.ide_intent import Intent
from src.config.paths import get_project_root


class CursorCliAdapter(CliAgentAdapter):
    """Adapter for Cursor Agent CLI."""

    def __init__(self):
        super().__init__("cursor_cli", "cursor-agent")

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Verify Cursor Agent CLI is available and configure MCP."""
        detection = self.detect()
        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": "Cursor Agent CLI ('cursor-agent') not found in PATH.",
                "summary": "To install, run: `npm install -g @anthropic-ai/cursor-agent-cli` or visit https://docs.cursor.com/agent",
            }

        try:
            config_path = Path.home() / ".cursor" / "mcp.json"

            project_root = get_project_root()
            venv_python = project_root / ".venv" / "bin" / "python3"
            if venv_python.exists():
                python_cmd = str(venv_python)
            else:
                python_cmd = "python3"

            ensure_plugin_pack_formatters_path(project_root)
            from mcp_config import build_augur_mcp_servers, prune_augur_servers
            desired_servers = build_augur_mcp_servers(project_root, python_cmd, "cursor")

            current_config = self._read_config(config_path, format="json") or {}
            if not isinstance(current_config, dict):
                current_config = {}

            mcp_servers = current_config.get("mcpServers")
            if not isinstance(mcp_servers, dict):
                mcp_servers = {}
                current_config["mcpServers"] = mcp_servers

            changed = False
            backup_paths = []

            prune_augur_servers(mcp_servers)
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
                        "error": None,
                        "summary": f"Updated Cursor Agent MCP config at {config_path}",
                    }
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [],
                    "backup_paths": [],
                    "error": result["error"],
                    "summary": f"Failed to write Cursor config: {result['error']}",
                }

            return {
                "success": True,
                "changed": False,
                "config_paths": [str(config_path)] if config_path.exists() else [],
                "backup_paths": [],
                "error": None,
                "summary": "Cursor Agent MCP config already up to date.",
            }

        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": f"Failed to check config: {e}",
                "summary": "Could not verify Cursor Agent configuration.",
            }

    def get_action_map(self) -> dict[str, str]:
        """Get mapping of intent actions to Cursor Agent CLI commands."""
        return {
            "run": "agent",
            "chat": "agent",
            "ask": "agent --mode=ask",
            "plan": "agent --mode=plan",
            "edit": "agent",
            "review": "agent --mode=plan",
            "debug": "agent",
            "mcp": "mcp",
            "models": "models",
            "status": "status",
            "help": "help",
            "resume": "resume",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": ["status"],
            "mcp_list": ["mcp", "list"],
            "prompt": ["-p", "respond with just the word 'ok'"],
        }

    def get_capabilities(self):
        """Get agent capabilities for routing."""
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
                "planning",
                "code_review",
            ],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
