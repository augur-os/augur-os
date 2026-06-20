"""Antigravity adapter."""

from __future__ import annotations

import platform
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, check_output, run  # nosec B404
from typing import Any, Optional

from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType
from src.lib.ai.instruction_generator import InstructionGenerator


class AntigravityAdapter(BaseAdapter):
    """Adapter for Antigravity."""

    def __init__(self):
        super().__init__("antigravity")
        self._instruction_generator = InstructionGenerator()

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
        """Detect if Antigravity is installed/running."""
        installed = False
        running = False
        path = None
        error = None

        try:
            if platform.system() == "Windows":
                # Windows detection
                import os

                # Check 1: Running process (if running, it must be installed)
                try:
                    # Use tasklist to find Antigravity.exe
                    cmd = ["tasklist", "/FI", "IMAGENAME eq Antigravity.exe", "/FO", "CSV", "/NH"]
                    result = self._run_command(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and "Antigravity.exe" in result.stdout:
                        running = True
                        installed = True
                except Exception:
                    _ = None

                # Check 2: Default install path (if not already found)
                if not installed:
                    local_app_data = os.environ.get("LOCALAPPDATA", "")
                    if local_app_data:
                        default_path = f"{local_app_data}\\Programs\\Antigravity\\Antigravity.exe"
                        if os.path.exists(default_path):
                            installed = True
                            path = default_path

                # Check 3: PATH (fallback)
                if not installed:
                    try:
                        result = self._run_command(["where", "antigravity"], capture_output=True, text=True)
                        if result.returncode == 0:
                            installed = True
                            path = result.stdout.strip().splitlines()[0]
                    except FileNotFoundError:
                        _ = None
            else:
                # POSIX detection
                try:
                    # Check for Antigravity command
                    result = self._run_command(["which", "antigravity"], capture_output=True, text=True)
                    if result.returncode == 0:
                        installed = True
                        path = result.stdout.strip()
                except FileNotFoundError:
                    _ = None

                # Check if running
                try:
                    output = self._check_output_command(["ps", "-ax", "-o", "comm="], text=True, stderr=DEVNULL)
                    running = any("antigravity" in line.lower() for line in output.splitlines())
                except FileNotFoundError:
                    _ = None

        except Exception as e:
            error = str(e)

        return {"installed": installed, "running": running, "path": path, "error": error}

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Antigravity may require workflow config."""
        # Placeholder for future config management
        return {
            "success": True,
            "changed": False,
            "config_paths": [],
            "backup_paths": [],
            "error": None,
            "summary": "Antigravity configuration managed via workflows",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for Antigravity integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()

        # Check 1: Config present
        checks["config_present"] = (True, "No config file required")

        # Check 2: Connectivity
        if detection.get("installed"):
            checks["connectivity"] = (True, "Antigravity is installed")
            if detection.get("running"):
                checks["connectivity"] = (True, "Antigravity is installed and running")
        else:
            checks["connectivity"] = (False, "Antigravity not found")
            overall_healthy = False

        # Check 3: Tool discovery (MCP support)
        checks["tool_list"] = (None, "Requires MCP connection")

        # Check 4: End-to-end
        try:
            test_intent = Intent(action="create_skill", params={"name": "test"})
            output = self.render_intent(test_intent)
            if output and output.content:
                checks["end_to_end"] = (True, "Can generate workflows")
            else:
                checks["end_to_end"] = (False, "Failed to generate workflows")
                overall_healthy = False
        except Exception as e:
            checks["end_to_end"] = (False, f"End-to-end check failed: {e}")
            overall_healthy = False

        if not overall_healthy:
            status = "not_configured" if not detection.get("installed") else "degraded"

        return {
            "healthy": overall_healthy,
            "status": status,
            "checks": checks,
            "last_check": datetime.now().isoformat(),
            "error": error,
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """Translate intent to Antigravity workflow YAML."""
        if intent.action == "create_skill":
            instruction = self._instruction_generator.generate_antigravity_workflow("create_skill", intent.params)
        else:
            instruction = self._instruction_generator.generate_antigravity_workflow(intent.action, intent.params)

        return AdapterOutput(
            output_type=AdapterOutputType.WORKFLOW_YAML,
            content=instruction.content,
            metadata={
                "filename": instruction.filename,
                "description": instruction.description,
                "format": instruction.format,
            },
        )

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "workflow"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return []
