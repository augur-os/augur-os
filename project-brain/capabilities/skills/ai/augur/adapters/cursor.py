"""Cursor IDE adapter."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, check_output  # nosec B404
from typing import Any, Optional

from src.config.paths import get_project_root
from ._plugin_pack import ensure_plugin_pack_formatters_path
from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType
from src.lib.ai.instruction_generator import InstructionGenerator

logger = logging.getLogger(__name__)


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


class CursorAdapter(BaseAdapter):
    """Adapter for Cursor IDE."""

    def __init__(self):
        super().__init__("cursor")
        self._instruction_generator = InstructionGenerator()

    def detect(self) -> dict[str, Any]:
        """Detect if Cursor is installed/running."""
        installed = False
        running = False
        path = None
        error = None

        try:
            # Check for Cursor app on macOS
            cursor_paths = [
                Path.home() / "Applications" / "Cursor.app",
                Path("/Applications/Cursor.app"),
            ]

            for cursor_path in cursor_paths:
                if cursor_path.exists():
                    installed = True
                    path = str(cursor_path)
                    break

            # Check if running
            try:
                output = check_output(
                    _resolve_command(["ps", "-ax", "-o", "comm="]), text=True, stderr=DEVNULL
                )  # nosec B603
                running = any("Cursor" in line for line in output.splitlines())
            except (OSError, ValueError) as exc:
                logger.debug("Failed to detect running Cursor process: %s", exc)

        except Exception as e:
            error = str(e)

        return {"installed": installed, "running": running, "path": path, "error": error}

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Ensure Cursor MCP configuration is set up."""
        cursor_dir = Path.home() / ".cursor"
        mcp_config_path = cursor_dir / "mcp.json"

        project_root = get_project_root()
        # Check for virtual environment
        venv_python = project_root / ".venv" / "bin" / "python3"
        if venv_python.exists():
            python_cmd = str(venv_python)
        else:
            python_cmd = "python3"

        ensure_plugin_pack_formatters_path(project_root)
        from mcp_config import build_augur_mcp_servers, prune_augur_servers
        desired_servers = build_augur_mcp_servers(project_root, python_cmd, "cursor")

        # Read existing config and merge (preserve other MCP servers)
        current_config = self._read_config(mcp_config_path, format="json") or {}
        if not isinstance(current_config, dict):
            current_config = {}

        mcp_servers = current_config.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            mcp_servers = {}
            current_config["mcpServers"] = mcp_servers

        backup_paths = []
        
        prune_augur_servers(mcp_servers)
        for k, v in desired_servers.items():
            if mcp_servers.get(k) != v:
                mcp_servers[k] = v
            result = self._write_config_safely(mcp_config_path, json.dumps(current_config, indent=2), format="json")
            if result["success"]:
                if result["backup_path"]:
                    backup_paths.append(result["backup_path"])
                self._config_paths = [mcp_config_path]
                return {
                    "success": True,
                    "changed": True,
                    "config_paths": [str(mcp_config_path)],
                    "backup_paths": backup_paths,
                    "error": None,
                    "summary": f"Updated Cursor MCP config at {mcp_config_path}",
                }
            else:
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [],
                    "backup_paths": [],
                    "error": result["error"],
                    "summary": f"Failed to write Cursor MCP config: {result['error']}",
                }

        return {
            "success": True,
            "changed": False,
            "config_paths": [str(mcp_config_path)],
            "backup_paths": [],
            "error": None,
            "summary": "Cursor MCP config already up to date",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Cursor integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        # Check 1: Config present
        cursor_dir = Path.home() / ".cursor"
        mcp_config_path = cursor_dir / "mcp.json"
        if mcp_config_path.exists():
            try:
                config = json.loads(mcp_config_path.read_text())
                if "mcpServers" in config and "augur" in config["mcpServers"]:
                    checks["config_present"] = (True, "MCP config exists and contains 'exo' server")
                else:
                    checks["config_present"] = (False, "MCP config exists but missing 'exo' server")
                    overall_healthy = False
            except Exception as e:
                checks["config_present"] = (False, f"MCP config exists but invalid: {e}")
                overall_healthy = False
        else:
            checks["config_present"] = (False, "MCP config file not found")
            overall_healthy = False

        # Check 2: Connectivity (check if Cursor is running)
        detection = self.detect()
        if detection.get("running"):
            checks["connectivity"] = (True, "Cursor is running")
        else:
            checks["connectivity"] = (False, "Cursor is not running")
            # Don't fail overall health if just not running

        # Check 3: Tool discovery (would require MCP connection - skip for now)
        checks["tool_list"] = (None, "Requires active MCP connection")

        # Check 4: End-to-end (generate instruction and verify path)
        try:
            test_intent = Intent(action="help", params={})
            output = self.render_intent(test_intent)
            if output and output.content:
                checks["end_to_end"] = (True, "Can generate instructions")
            else:
                checks["end_to_end"] = (False, "Failed to generate instructions")
                overall_healthy = False
        except Exception as e:
            checks["end_to_end"] = (False, f"End-to-end check failed: {e}")
            overall_healthy = False

        if not overall_healthy:
            if not checks.get("config_present", (True, ""))[0]:
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
        """Translate intent to Cursor-specific format."""
        # Use existing instruction generator
        if intent.action == "create_skill":
            instruction = self._instruction_generator.generate_cursor_instructions("create_skill", intent.params)
        elif intent.action == "analyze_skill":
            instruction = self._instruction_generator.generate_cursor_instructions("analyze_skill", intent.params)
        elif intent.action == "generate_dashboard":
            instruction = self._instruction_generator.generate_cursor_instructions("generate_dashboard", intent.params)
        else:
            instruction = self._instruction_generator.generate_cursor_instructions(intent.action, intent.params)

        return AdapterOutput(
            output_type=AdapterOutputType.CHAT_PROMPT,
            content=instruction.content,
            metadata={
                "filename": instruction.filename,
                "description": instruction.description,
                "format": instruction.format,
            },
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "mcp"  # Cursor supports MCP

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return ["chat_prompt"]  # Can fall back to chat prompt
