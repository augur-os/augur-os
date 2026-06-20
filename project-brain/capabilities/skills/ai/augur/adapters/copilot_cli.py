"""Adapter for GitHub Copilot CLI - agentic coding assistant in the terminal."""

from __future__ import annotations

from typing import Any, Optional

from .cli_agent_base import CliAgentAdapter
from src.lib.ai.ide_intent import Intent


class CopilotCliAdapter(CliAgentAdapter):
    """Adapter for GitHub Copilot CLI (`copilot` / `gh copilot`)."""

    def __init__(self):
        super().__init__("copilot_cli", "copilot")

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """GitHub Copilot CLI authenticates via gh auth; no MCP config needed."""
        detection = self.detect()
        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "config_paths": [],
                "backup_paths": [],
                "error": "GitHub Copilot CLI not available.",
                "summary": "Install with: `brew install copilot-cli`",
            }

        return {
            "success": True,
            "changed": False,
            "config_paths": [],
            "backup_paths": [],
            "error": None,
            "summary": "GitHub Copilot CLI configured via gh auth (no MCP config needed).",
        }

    def get_action_map(self) -> dict[str, str]:
        """Get mapping of intent actions to Copilot CLI commands."""
        return {
            "suggest": "suggest",
            "explain": "explain",
            "help": "--help",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": [],
            "mcp_list": [],
            "prompt": [],
        }

    def get_capabilities(self):
        """Get agent capabilities for routing."""
        from src.lib.ai.agent_capabilities import AgentCapabilities

        health = self.health_check()
        health_status = health.get("status", "unknown")

        return AgentCapabilities(
            agent_name=self.ide_name,
            agent_type="cli",
            has_sprint_context=False,
            has_slash_commands=False,
            has_factory_insights=False,
            can_execute_code=True,
            can_modify_files=True,
            specializations=[
                "code_generation",
                "debugging",
                "code_explanation",
            ],
            health_status=health_status,
            execution_mode=self.get_execution_mode(),
            supported_fallbacks=self.get_supported_fallbacks(),
        )
