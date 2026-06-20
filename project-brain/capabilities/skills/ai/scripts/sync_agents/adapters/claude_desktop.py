"""sync_agents/adapters/claude_desktop.py — Claude Desktop adapter."""
from __future__ import annotations
from pathlib import Path

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    logger,
)
from ..engine import write_generated_file


class ClaudeDesktopAdapter(BaseAdapter):
    adapter_name = "claude_desktop"

    def get_managed_files(self) -> list[str]:
        return [
            "CLAUDE.md",
        ]

    def detect_installed(self) -> bool:
        import platform
        if platform.system() == "Darwin":
            return (Path("/Applications/Claude.app").exists() or 
                    (Path.home() / "Applications/Claude.app").exists())
        elif platform.system() == "Windows":
            import os
            app_data = os.environ.get("LOCALAPPDATA")
            if app_data:
                return (Path(app_data) / "Programs" / "Claude" / "Claude.exe").exists()
        return False

    def sync_rules(self, content: str) -> None:
        # Claude Desktop shares CLAUDE.md with Claude Code
        # We don't need to do anything here if Claude Code is also enabled,
        # but for completeness we'll ensure it exists.
        target = PROJECT_ROOT / "CLAUDE.md"
        from ..templates import render_rules_projection
        final_content = render_rules_projection(content)
        write_generated_file(
            target,
            final_content,
            source=SOURCE_RULES_LABEL,
        )
