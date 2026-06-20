"""
MCP Context Types - ADR-030 Data Models

Leaf module holding the data classes, enums, and constants used by the
context manager. Kept separate from context_manager.py so the small,
stable type surface lives apart from the large ContextManager state machine.

This module MUST NOT import context_manager (acyclic: context_manager
imports context_types, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# ADR-030: Data Models
# =============================================================================


class AugurMode(str, Enum):
    """Operating mode for the augur."""

    DEV = "dev"
    OPS = "ops"


class ClientCapability(str, Enum):
    """Client skill support level."""

    FULL = "full"  # Claude, Cursor, Windsurf, Copilot
    LIMITED = "limited"  # Gemini, Codex
    NONE = "none"  # No skill support


# Client capability mapping
CLIENT_CAPABILITIES: dict[str, ClientCapability] = {
    "claude_code": ClientCapability.FULL,
    "cursor": ClientCapability.FULL,
    "windsurf": ClientCapability.FULL,
    "copilot": ClientCapability.FULL,
    "opencode": ClientCapability.FULL,
    "gemini": ClientCapability.LIMITED,
    "codex": ClientCapability.LIMITED,
    "antigravity": ClientCapability.LIMITED,
    "claude_desktop": ClientCapability.LIMITED,
    "cowork": ClientCapability.LIMITED,
    "web-chat": ClientCapability.NONE,  # ADR-250: page-scoped filtering
    "ollama": ClientCapability.NONE,
}

# ADR-250: The only client that needs page-scoped tool filtering.
WEB_CHAT_CLIENT = "web-chat"

# Default mode when none is configured
DEFAULT_MODE = "ops"

# Valid modes
VALID_MODES = {"dev", "ops"}


@dataclass
class Skill:
    """A skill that can be provided to an AI client."""

    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    mode: str | None = None  # "dev", "ops", or None (both)
    mcp_overlaps: list[str] = field(default_factory=list)  # MCP tools this skill replaces
    enabled: bool = True

    @property
    def is_dev_only(self) -> bool:
        return self.mode == "dev"

    @property
    def is_ops_only(self) -> bool:
        return self.mode == "ops"


@dataclass
class MCPToolState:
    """An MCP tool that may overlap with skills.

    Named MCPToolState to avoid collision with FastMCP's Tool class.
    """

    name: str
    description: str = ""
    enabled: bool = True
    disabled_reason: str | None = None


@dataclass
class UserSettings:
    """User-level overrides for context."""

    disabled_skills: list[str] = field(default_factory=list)
    enabled_skills: list[str] = field(default_factory=list)
    mcp_overrides: dict[str, bool] = field(default_factory=dict)  # tool_name -> enabled
    custom_settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class PageContext:
    """Context from the currently open web dashboard page."""

    page_id: str | None = None
    hub: str | None = None
    active_tools: list[str] = field(default_factory=list)


@dataclass
class MergedContext:
    """Result of the context merge algorithm."""

    mode: AugurMode
    enabled_skills: list[Skill] = field(default_factory=list)
    disabled_skills: list[Skill] = field(default_factory=list)
    enabled_mcp_tools: list[MCPToolState] = field(default_factory=list)
    disabled_mcp_tools: list[MCPToolState] = field(default_factory=list)
    page_context: PageContext | None = None
    merge_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mode": self.mode.value,
            "enabled_skills": [s.name for s in self.enabled_skills],
            "disabled_skills": [s.name for s in self.disabled_skills],
            "enabled_mcp_tools": [t.name for t in self.enabled_mcp_tools],
            "disabled_mcp_tools": [{"name": t.name, "reason": t.disabled_reason} for t in self.disabled_mcp_tools],
            "page": self.page_context.page_id if self.page_context else None,
            "merge_log": self.merge_log,
        }
