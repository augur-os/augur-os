"""Per-client adapters for `aug config sync`."""

from __future__ import annotations

from src.cli_config.adapters.base import ClientConfigAdapter, ConfigDiff
from src.cli_config.adapters.claude import ClaudeAdapter
from src.cli_config.adapters.codex import CodexAdapter
from src.cli_config.adapters.copilot import CopilotAdapter
from src.cli_config.adapters.gemini import GeminiAdapter

ALL_ADAPTERS: tuple[ClientConfigAdapter, ...] = (
    ClaudeAdapter(),
    CodexAdapter(),
    GeminiAdapter(),
    CopilotAdapter(),
)

__all__ = [
    "ALL_ADAPTERS",
    "ClaudeAdapter",
    "ClientConfigAdapter",
    "CodexAdapter",
    "ConfigDiff",
    "CopilotAdapter",
    "GeminiAdapter",
]
