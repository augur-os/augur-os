"""IDE Adapter Registry - Initialize and register all adapters."""

from __future__ import annotations

from src.lib.ai.ide_intent import AdapterRegistry
from skills.ai.augur.adapters.antigravity import AntigravityAdapter
from skills.ai.augur.adapters.claude_code import ClaudeCodeAdapter
from skills.ai.augur.adapters.claude_desktop import ClaudeDesktopAdapter
from skills.ai.augur.adapters.cowork import CoworkAdapter
from skills.ai.augur.adapters.claude_sdk import ClaudeSDKAdapter
from skills.ai.augur.adapters.codex_cli import CodexCliAdapter
from skills.ai.augur.adapters.copilot_cli import CopilotCliAdapter
from skills.ai.augur.adapters.cursor import CursorAdapter
from skills.ai.augur.adapters.cursor_cli import CursorCliAdapter
from skills.ai.augur.adapters.juls import JulsAdapter
from skills.ai.augur.adapters.kimi_cli import KimiCliAdapter
from skills.ai.augur.adapters.ollama import OllamaAdapter
from skills.ai.augur.adapters.opencode import OpenCodeAdapter
from skills.ai.augur.adapters.vscode_copilot import VSCodeCopilotAdapter


def create_registry() -> AdapterRegistry:
    """Create and populate the adapter registry."""
    registry = AdapterRegistry()

    # Register IDE adapters
    registry.register(CursorAdapter())
    registry.register(VSCodeCopilotAdapter())
    registry.register(AntigravityAdapter())
    registry.register(ClaudeDesktopAdapter())
    registry.register(CoworkAdapter())

    # Register CLI adapters
    registry.register(ClaudeCodeAdapter())
    registry.register(CodexCliAdapter())
    registry.register(CopilotCliAdapter())
    registry.register(CursorCliAdapter())
    registry.register(JulsAdapter())
    registry.register(KimiCliAdapter())
    registry.register(OpenCodeAdapter())

    # Register SDK adapters
    registry.register(ClaudeSDKAdapter())

    # Register Local LLM adapters
    registry.register(OllamaAdapter())

    return registry


# Global registry instance
_registry: AdapterRegistry | None = None


def get_registry() -> AdapterRegistry:
    """Get the global adapter registry (singleton)."""
    global _registry
    if _registry is None:
        _registry = create_registry()
    return _registry
