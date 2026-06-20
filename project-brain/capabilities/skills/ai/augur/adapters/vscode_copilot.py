"""VS Code / GitHub Copilot adapter."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, check_output  # nosec B404
from typing import Any, Optional

from .base import BaseAdapter
from src.lib.ai.ide_intent import Intent, AdapterOutput, AdapterOutputType
from src.lib.ai.instruction_generator import InstructionGenerator

logger = logging.getLogger(__name__)


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


class VSCodeCopilotAdapter(BaseAdapter):
    """Adapter for VS Code / GitHub Copilot."""

    def __init__(self):
        super().__init__("vscode_copilot")
        self._instruction_generator = InstructionGenerator()

    def detect(self) -> dict[str, Any]:
        """Detect if VS Code is installed/running."""
        installed = False
        running = False
        path = None
        error = None

        try:
            # Check for VS Code
            vscode_paths = [
                Path.home() / "Applications" / "Visual Studio Code.app",
                Path("/Applications/Visual Studio Code.app"),
            ]

            for vscode_path in vscode_paths:
                if vscode_path.exists():
                    installed = True
                    path = str(vscode_path)
                    break

            # Check if running
            try:
                output = check_output(
                    _resolve_command(["ps", "-ax", "-o", "comm="]), text=True, stderr=DEVNULL
                )  # nosec B603
                running = any("Code" in line for line in output.splitlines())
            except (OSError, ValueError) as exc:
                logger.debug("Failed to detect running VS Code process: %s", exc)

            # Check for Copilot extension
            copilot_installed = False
            vscode_extensions = [
                Path.home() / ".vscode" / "extensions",
                Path.home() / ".vscode-insiders" / "extensions",
            ]
            for ext_path in vscode_extensions:
                if ext_path.exists():
                    try:
                        extensions = [d.name for d in ext_path.iterdir() if d.is_dir()]
                        copilot_installed = any("github.copilot" in ext.lower() for ext in extensions)
                        if copilot_installed:
                            break
                    except (OSError, ValueError) as exc:
                        logger.debug("Failed scanning VS Code extensions at %s: %s", ext_path, exc)

        except Exception as e:
            error = str(e)

        return {
            "installed": installed,
            "running": running,
            "path": path,
            "copilot_installed": copilot_installed if 'copilot_installed' in locals() else False,
            "error": error,
        }

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Ensure VS Code settings are configured (future: MCP support)."""
        # For now, VS Code doesn't have MCP config like Cursor
        # This is a placeholder for future MCP support
        return {
            "success": True,
            "changed": False,
            "config_paths": [],
            "backup_paths": [],
            "error": None,
            "summary": "VS Code configuration managed via extensions (MCP support coming)",
        }

    def health_check(self) -> dict[str, Any]:
        """Run health checks for VS Code/Copilot integration."""
        checks: dict[str, tuple[bool | None, str]] = {}
        overall_healthy = True
        status = "healthy"
        error = None

        detection = self.detect()

        # Check 1: Config present (not applicable yet for VS Code MCP)
        checks["config_present"] = (None, "MCP config not yet supported for VS Code")

        # Check 2: Connectivity
        if detection.get("running"):
            checks["connectivity"] = (True, "VS Code is running")
        else:
            checks["connectivity"] = (False, "VS Code is not running")

        # Check 3: Tool discovery
        checks["tool_list"] = (None, "Requires MCP support (coming soon)")

        # Check 4: End-to-end
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
            status = "degraded"

        return {
            "healthy": overall_healthy,
            "status": status,
            "checks": checks,
            "last_check": datetime.now().isoformat(),
            "error": error,
        }

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """Translate intent to Copilot-specific format."""
        if intent.action == "create_skill":
            instruction = self._instruction_generator.generate_copilot_instructions("create_skill", intent.params)
        else:
            instruction = self._instruction_generator.generate_copilot_instructions(intent.action, intent.params)

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
        return "chat_prompt"  # VS Code uses chat prompts

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return []  # No fallbacks yet
