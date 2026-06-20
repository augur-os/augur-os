"""sync_agents/adapters/ — IDE adapter registry."""
from .claude_code import ClaudeCodeAdapter
from .claude_desktop import ClaudeDesktopAdapter
from .cline import ClineAdapter
from .cursor import CursorAdapter
from .windsurf import WindsurfAdapter
from .copilot import CopilotAdapter
from .gemini import GeminiAdapter
from .opencode import OpenCodeAdapter
from .kimi import KimiAdapter
from .antigravity import AntigravityAdapter
from .codex import CodexAdapter
from .cowork import CoworkAdapter
from .codex_plugin import CodexPluginAdapter
from .gemini_plugin import GeminiPluginAdapter

__all__ = [
    "ClaudeCodeAdapter",
    "ClaudeDesktopAdapter",
    "ClineAdapter",
    "CursorAdapter",
    "WindsurfAdapter",
    "CopilotAdapter",
    "GeminiAdapter",
    "OpenCodeAdapter",
    "KimiAdapter",
    "AntigravityAdapter",
    "CodexAdapter",
    "CoworkAdapter",
    "CodexPluginAdapter",
    "GeminiPluginAdapter",
]
