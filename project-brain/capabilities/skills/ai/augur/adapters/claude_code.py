from __future__ import annotations

from typing import Any, Optional
from .cli_agent_base import CliAgentAdapter
from src.lib.ai.ide_intent import Intent


class ClaudeCodeAdapter(CliAgentAdapter):
    """Adapter for Claude Code (CLI)."""

    def __init__(self):
        super().__init__("claude_code", "claude")

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """Verify if Claude Code CLI is available and configured."""
        detection = self.detect()
        if not detection.get("installed"):
            return {
                "success": False,
                "changed": False,
                "error": "Claude Code CLI ('claude') not found in PATH.",
                "summary": "To install Claude Code, run: `npm install -g @anthropic-ai/claude-code`.",
            }

        # Check configuration
        try:
            import json
            from pathlib import Path
            from src.config.paths import get_project_root

            config_path = Path.home() / ".claude.json"
            if not config_path.exists():
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [str(config_path)],
                    "error": "Claude Code config not found.",
                    "summary": "Please run `claude mcp` to initialize configuration.",
                }

            content = json.loads(config_path.read_text())
            project_root = str(get_project_root())

            # Check if project is configured
            projects = content.get("projects", {})
            if project_root not in projects:
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [str(config_path)],
                    "error": "Project not configured in Claude Code.",
                    "summary": f"Augur not configured for {project_root}.",
                }

            servers = projects[project_root].get("mcpServers", {})
            if "augur" not in servers and "augur" not in servers:
                return {
                    "success": False,
                    "changed": False,
                    "config_paths": [str(config_path)],
                    "error": "Augur MCP not found in project config.",
                    "summary": "Augur MCP server is not added to this project's Claude Code config.",
                }

            return {
                "success": True,
                "changed": False,
                "config_paths": [str(config_path)],
                "summary": "Claude Code is installed and configured for this project.",
            }

        except Exception as e:
            return {
                "success": False,
                "changed": False,
                "error": f"Failed to check config: {e}",
                "summary": "Could not verify Claude Code configuration.",
            }

    def get_action_map(self) -> dict[str, str]:
        """
        Get mapping of intent actions to Claude Code CLI commands.

        Returns:
            Dict mapping action names to CLI command strings
        """
        return {
            "create_skill": "create-skill",
            "analyze_skill": "analyze-skill",
            "generate_dashboard": "generate-dashboard",
            "chat": "chat",
            "ask": "ask",
            "edit": "edit",
            "review": "review",
            "help": "--help",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--version"],
            "auth": [],
            "mcp_list": ["mcp", "list"],
            "prompt": ["-p", "respond with just the word 'ok'", "--output-format", "text"],
        }
