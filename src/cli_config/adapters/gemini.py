"""Adapter for ~/.gemini/settings.json mcpServers section.

Same shape as Claude's adapter; only the default config path and the
``client`` identifier passed to ``render_entry_dict`` differ.
"""

from __future__ import annotations

from pathlib import Path

from src.cli_config.adapters._paths import render_entry_dict
from src.cli_config.adapters.claude import ClaudeAdapter
from src.cli_config.manifest import Manifest, ServerEntry


class GeminiAdapter(ClaudeAdapter):
    name = "gemini"

    def default_config_path(self) -> Path:
        return Path.home() / ".gemini" / "settings.json"

    def _managed_entries(
        self,
        manifest: Manifest,
        *,
        existing_server_ids: set[str] | None = None,
    ) -> list[ServerEntry]:
        return [
            entry
            for entry in manifest.all_augur_servers_for_client(
                self.name,
                existing_server_ids=existing_server_ids,
            )
            if not entry.bundle
        ]

    @staticmethod
    def _render_entry(entry: ServerEntry) -> dict:
        return render_entry_dict(entry, client="gemini")
