"""Claude Desktop adapter."""

from __future__ import annotations

import json as _json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, check_output, run  # nosec B404
from typing import Any, Optional

from src.config.paths import get_client_runtime_dir, get_project_root, get_python_executable

from ._plugin_pack import ensure_plugin_pack_formatters_path
from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType


class ClaudeDesktopAdapter(BaseAdapter):
    """Adapter for Claude Desktop."""

    def __init__(self):
        super().__init__("claude_desktop")

    def _resolve_command(self, command: list[str]) -> list[str]:
        """Resolve executable path to absolute when available."""
        if not command:
            raise ValueError("Command must not be empty")

        executable = command[0]
        if Path(executable).is_absolute():
            return command

        resolved = shutil.which(executable)
        if not resolved:
            return command

        return [resolved, *command[1:]]

    def _run_command(self, command: list[str], **kwargs: object) -> CompletedProcess:
        """Run subprocess command with resolved executable."""
        return run(self._resolve_command(command), **kwargs)  # nosec B603

    def _check_output_command(self, command: list[str], **kwargs: object) -> str:
        """Get command output with resolved executable."""
        return check_output(self._resolve_command(command), **kwargs)  # nosec B603

    def detect(self) -> dict[str, Any]:
        """Detect if Claude Desktop is installed/running."""
        installed = False
        running = False
        path = None
        error = None

        try:
            if platform.system() == "Darwin":
                # Check if app exists
                app_path = Path("/Applications/Claude.app")
                if app_path.exists():
                    installed = True
                    path = str(app_path)

                # Check if process is running - main process name is 'Claude'
                try:
                    output = self._check_output_command(["ps", "-ax", "-o", "comm="], text=True, encoding="utf-8")
                    if any(line.strip().endswith("/Contents/MacOS/Claude") for line in output.splitlines()):
                        running = True
                except Exception:
                    _ = None
            elif platform.system() == "Windows":
                # Windows detection
                app_data = Path(os.environ.get("LOCALAPPDATA", ""))
                claude_exe = app_data / "Programs" / "Claude" / "Claude.exe"
                if claude_exe.exists():
                    installed = True
                    path = str(claude_exe)

                try:
                    output = self._check_output_command(
                        ["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],
                        text=True,
                        stderr=DEVNULL,
                    )
                    if "Claude.exe" in output:
                        running = True
                except Exception:
                    _ = None

        except Exception as e:
            error = str(e)

        return {
            "installed": installed,
            "running": running,
            "path": path,
            "error": error,
        }

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Configure Claude Desktop for MCP, merging Augur entry if missing.

        ADR-030: Claude Desktop MCP config merge.
        Preserves existing mcpServers entries and adds/updates the Augur entry.
        """
        config_path = get_client_runtime_dir("claude-desktop") / "claude_desktop_config.json"

        exists = config_path.exists()

        # Load existing config or start fresh
        config: dict[str, Any] = {}
        if exists:
            try:
                config = _json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                config = {}

        servers = config.get("mcpServers", {})

        # Build the expected entry first so we can detect stale entries
        project_root = self._find_project_root()
        python_path = self._find_python()

        ensure_plugin_pack_formatters_path(project_root)
        from mcp_config import build_augur_mcp_servers, prune_augur_servers
        desired_servers = build_augur_mcp_servers(project_root, python_path, "claude_desktop")

        # Merge: preserve all existing servers, add augur
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        changed = False
        mcp_servers = config["mcpServers"]
        
        prune_augur_servers(mcp_servers)
        for k, v in desired_servers.items():
            if mcp_servers.get(k) != v:
                mcp_servers[k] = v
                changed = True

        if not changed:
            return {
                "success": True,
                "changed": False,
                "config_paths": [str(config_path)],
                "summary": "Claude Desktop is already configured with Augur MCP.",
            }

        # Write merged config
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                _json.dumps(config, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return {
                "success": True,
                "changed": True,
                "config_paths": [str(config_path)],
                "summary": "Augur MCP server added to Claude Desktop config.",
                "preserved_servers": [k for k in servers],
            }
        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "config_paths": [str(config_path)],
                "error": f"Failed to write config: {e}",
                "summary": f"Could not write Claude Desktop config at: {config_path}",
            }

    def _find_project_root(self) -> Path:
        """Find the Augur project root."""
        return get_project_root()

    def _find_python(self) -> str:
        """Find the Python executable, preferring the project venv."""
        return str(get_python_executable())

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Claude Desktop."""
        detection = self.detect()
        config_status = self.ensure_config()

        healthy = detection["installed"] and config_status["success"]
        status = "healthy" if healthy else ("not_configured" if detection["installed"] else "not_found")

        return {
            "healthy": healthy,
            "status": status,
            "checks": {
                "installed": (
                    detection["installed"],
                    "Installed" if detection["installed"] else "Not installed",
                ),
                "running": (
                    detection["running"],
                    "Running" if detection["running"] else "Not running",
                ),
                "mcp_config": (config_status["success"], config_status["summary"]),
            },
            "last_check": datetime.now().isoformat(),
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """Claude Desktop handles prompts via bridge."""
        return AdapterOutput(
            output_type=AdapterOutputType.CHAT_PROMPT,
            content=intent.params.get("prompt", ""),
            metadata={"ide": "claude_desktop", "action": intent.action},
        )

    def get_execution_mode(self) -> str:
        return "chat_prompt"

    def get_supported_fallbacks(self) -> list[str]:
        return ["chat_prompt"]
