"""IDE Intent Model - Canonical representation of Augur actions for IDE execution.

This module defines the vendor-agnostic "intent" model that Augur uses
to express what it wants to do, and the adapter interface that translates
intents into IDE-specific execution formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AdapterOutputType(str, Enum):
    """Types of outputs that adapters can produce."""

    MCP_CALL = "mcp_call"
    CHAT_PROMPT = "chat_prompt"
    CLI_COMMAND = "cli_command"
    WORKFLOW_YAML = "workflow_yaml"
    CONFIG_PATCH = "config_patch"
    SDK_CALL = "sdk_call"


@dataclass
class Intent:
    """Canonical representation of what Augur wants to do."""

    action: str  # e.g., "create_skill", "analyze_skill", "generate_dashboard"
    params: dict[str, Any] = field(default_factory=dict)
    context: Optional[dict[str, Any]] = None  # Additional context (workspace, user preferences, etc.)
    workspace: Optional[str] = None  # Workspace path if relevant


@dataclass
class AdapterOutput:
    """Output from an IDE adapter - the IDE-specific execution format."""

    output_type: AdapterOutputType
    content: str  # The actual content (prompt, command, YAML, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional metadata (filename, tool name, etc.)

    # For MCP calls
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None

    # For config patches
    config_path: Optional[str] = None
    backup_path: Optional[str] = None


class IDEAdapter:
    """Base interface for IDE-specific adapters."""

    def __init__(self, ide_name: str):
        self.ide_name = ide_name

    def detect(self) -> dict[str, Any]:
        """
        Detect if this IDE is installed/running.

        Returns:
            dict with keys: installed (bool), running (bool), path (str|None), error (str|None)
        """
        raise NotImplementedError

    def ensure_config(self, intent: Optional[Intent] = None) -> dict[str, Any]:
        """
        Auto-manage IDE configuration files.
        Creates backups before writing.

        Args:
            intent: Optional intent that might require config changes

        Returns:
            dict with keys: success (bool), changed (bool), config_paths (list[str]),
                          backup_paths (list[str]), error (str|None), summary (str)
        """
        raise NotImplementedError

    def health_check(self) -> dict[str, Any]:
        """
        Run health checks for this IDE integration.

        Returns:
            dict with keys:
            - healthy (bool): Overall health status
            - status (str): "healthy", "degraded", "not_configured", "error"
            - checks (dict): Individual check results
              - config_present (bool, str): Config files exist and parse
              - connectivity (bool, str): Can reach IDE/bridge
              - tool_list (bool, str): Can list tools/resources (if supported)
              - end_to_end (bool, str): End-to-end smoke test passes
            - last_check (str): ISO timestamp
            - error (str|None): Error message if unhealthy
        """
        raise NotImplementedError

    def render_intent(self, intent: Intent) -> AdapterOutput:
        """
        Translate an Intent into IDE-specific execution format.

        Args:
            intent: The canonical intent to translate

        Returns:
            AdapterOutput with the IDE-specific format
        """
        raise NotImplementedError

    def get_execution_mode(self) -> str:
        """
        Get the primary execution mode for this adapter.

        Returns:
            One of: "mcp", "chat_prompt", "cli", "workflow", "config_only", "sdk", "api", "file_dispatch"
        """
        raise NotImplementedError

    def get_supported_fallbacks(self) -> list[str]:
        """
        Get list of supported fallback execution modes.

        Returns:
            List of execution mode strings (subset of get_execution_mode return values)
        """
        raise NotImplementedError


class AdapterRegistry:
    """Registry for IDE adapters."""

    def __init__(self):
        self._adapters: dict[str, IDEAdapter] = {}

    def register(self, adapter: IDEAdapter) -> None:
        """Register an adapter."""
        self._adapters[adapter.ide_name] = adapter

    def get(self, ide_name: str) -> Optional[IDEAdapter]:
        """Get an adapter by IDE name."""
        return self._adapters.get(ide_name)

    def list_all(self) -> list[str]:
        """List all registered IDE names."""
        return list(self._adapters.keys())

    def get_all(self) -> list[IDEAdapter]:
        """Get all registered adapters."""
        return list(self._adapters.values())

    def find_best_adapter(self, intent: Intent, preferred_ide: Optional[str] = None) -> Optional[IDEAdapter]:
        """
        Find the best adapter for an intent.

        Args:
            intent: The intent to execute
            preferred_ide: Preferred IDE name (if any)

        Returns:
            Best matching adapter, or None if none available
        """
        # If preferred IDE is specified and available, use it
        if preferred_ide:
            adapter = self.get(preferred_ide)
            if adapter:
                return adapter

        # Otherwise, return first available adapter
        adapters = self.get_all()
        if adapters:
            return adapters[0]

        return None
