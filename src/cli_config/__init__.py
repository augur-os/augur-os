"""Augur CLI: config-sync subcommand.

Reads config/system/mcp_servers.yaml and writes corresponding entries
to user-tier AI client configs (Claude Code, Codex, Gemini).

Wired into the `aug` CLI inline from src/cli.py:main().
"""

from __future__ import annotations
