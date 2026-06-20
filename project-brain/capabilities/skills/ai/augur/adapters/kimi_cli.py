"""Adapter for Kimi CLI - AI coding agent by Moonshot AI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from .cli_agent_base import CliAgentAdapter
from ._plugin_pack import ensure_plugin_pack_formatters_path
from src.lib.ai.ide_intent import Intent
from src.config.paths import get_project_root


class KimiCliAdapter(CliAgentAdapter):
    """Adapter for Kimi CLI."""

    def __init__(self):
        super().__init__("kimi_cli", "kimi")

    def _ensure_data_directory(self, data_path: Path) -> None:
        """Ensure augur data directory exists with required subdirectories.

        Args:
            data_path: Path to data directory
        """
        if data_path.exists():
            return

        # Create data directory structure
        subdirs = [
            "plugins/dev",
            "plugins/orchestration",
            "plugins/consulting",
            "runtime",
            "ide-integration",
            "memory",
            "config/dashboard",
            "config/system",
        ]

        data_path.mkdir(parents=True, exist_ok=True)
        for subdir in subdirs:
            (data_path / subdir).mkdir(parents=True, exist_ok=True)

    def _resolve_augur_data(self) -> Path:
        """Resolve augur data directory, creating if necessary.

        Returns:
            Path to data directory
        """
        # Check environment variables first
        env_path = os.environ.get("AUGUR_ROOT")
        if env_path:
            data_path = Path(os.path.expanduser(env_path)).expanduser().resolve()
        else:
            # Use default location
            data_path = Path.home() / "augur-data"

        # Ensure directory exists
        self._ensure_data_directory(data_path)
        return data_path

    def _get_mcp_entries(self, project_root: Path, augur_data: Path) -> dict[str, Any]:
        """Get MCP server configuration entries for augur.

        Args:
            project_root: Path to project root
            augur_data: Path to data directory

        Returns:
            MCP server configuration entries
        """
        venv_python = project_root / ".venv" / "bin" / "python3"
        if venv_python.exists():
            python_cmd = str(venv_python)
        else:
            python_cmd = "python3"

        ensure_plugin_pack_formatters_path(project_root)
        from mcp_config import build_augur_mcp_servers
        return build_augur_mcp_servers(project_root, python_cmd, "kimi_cli")

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Verify Kimi CLI is available and configure MCP."""
        detection = self.detect()
        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": "Kimi CLI ('kimi') not found in PATH.",
                "summary": "To install, run: `pip install kimi-cli` or visit https://moonshotai.github.io/kimi-cli/",
            }

        try:
            config_dir = Path.home() / ".kimi"
            config_path = config_dir / "mcp.json"

            project_root = get_project_root()

            try:
                augur_data = self._resolve_augur_data()
            except Exception as e:
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [],
                    "backup_paths": [],
                    "error": f"Failed to setup data directory: {e}",
                    "summary": "Could not create augur data directory.",
                }

            desired_servers = self._get_mcp_entries(project_root, augur_data)

            current_config = self._read_config(config_path, format="json") or {}
            if not isinstance(current_config, dict):
                current_config = {}

            mcp_servers = current_config.get("mcpServers")
            if not isinstance(mcp_servers, dict):
                mcp_servers = {}
                current_config["mcpServers"] = mcp_servers

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
                        "error": None,
                        "summary": f"Updated Kimi MCP config at {config_path}",
                    }
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [],
                    "backup_paths": [],
                    "error": result["error"],
                    "summary": f"Failed to write Kimi config: {result['error']}",
                }

            return {
                "success": True,
                "changed": False,
                "config_paths": [str(config_path)] if config_path.exists() else [],
                "backup_paths": [],
                "error": None,
                "summary": "Kimi MCP config already up to date.",
            }

        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": f"Failed to check config: {e}",
                "summary": "Could not verify Kimi configuration.",
            }

    def get_action_map(self) -> dict[str, str]:
        """Get mapping of intent actions to Kimi CLI commands."""
        return {
            "run": "",
            "chat": "",
            "ask": "",
            "edit": "",
            "review": "",
            "debug": "",
            "mcp": "mcp",
            "login": "login",
            "info": "info",
            "web": "web",
            "term": "term",
            "acp": "acp",
            "help": "--help",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": ["info"],
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
                "code_review",
            ],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
