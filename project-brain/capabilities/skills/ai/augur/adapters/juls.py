"""Jules CLI adapter (Google's async coding agent)."""

from __future__ import annotations


from .cli_agent_base import CliAgentAdapter


class JulsAdapter(CliAgentAdapter):
    """Adapter for Jules (Google's async coding agent CLI)."""

    def __init__(self):
        super().__init__("jules", "jules")

    def get_action_map(self) -> dict[str, str]:
        """
        Get mapping of intent actions to Jules CLI commands.

        Jules commands:
        - new: Create a new coding session
        - remote list --session: List sessions
        - remote show: Show session details
        - remote apply: Apply session changes
        """
        return {
            "run": "new",
            "chat": "new",
            "ask": "new",
            "edit": "new",
            "review": "new",
            "test": "new",
            "create_skill": "new",
            "list": "remote list --session",
            "help": "--help",
        }

    def get_live_test_commands(self) -> dict[str, list[str]]:
        return {
            "version": ["--help"],
            "auth": ["remote", "list", "--session"],
            "mcp_list": [],
            "prompt": [],
        }

    def get_execution_mode(self) -> str:
        """Get primary execution mode."""
        return "cli"

    def get_supported_fallbacks(self) -> list[str]:
        """Get supported fallback modes."""
        return ["chat_prompt"]
