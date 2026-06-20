"""Adapter for ~/.claude/settings.json mcpServers section.

Claude Code stores MCP servers as JSON object under top-level "mcpServers"
key. Each server entry is `{"command": str, "args": [str], "env": {...}}`.

Per Track 2 spec: only entries with id matching `augur*` are managed.
"""

from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

from src.cli_config.adapters._paths import render_entry_dict
from src.cli_config.adapters.base import ConfigDiff
from src.cli_config.manifest import Manifest, ServerEntry


class ClaudeAdapter:
    name = "claude"

    def default_config_path(self) -> Path:
        return Path.home() / ".claude" / "settings.json"

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        path = config_path or self.default_config_path()
        existing = self._read(path) if path.exists() else {}
        existing_servers = dict(existing.get("mcpServers") or {})

        existing_augur = {sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")}
        entries = self._managed_entries(manifest, existing_server_ids=set(existing_augur))
        wanted_by_id = {e.id: self._render_entry(e) for e in entries}

        added: list[ServerEntry] = []
        updated: list[ServerEntry] = []
        for entry in entries:
            current = existing_augur.get(entry.id)
            wanted = wanted_by_id[entry.id]
            if current is None:
                added.append(entry)
            elif current != wanted:
                updated.append(entry)

        removed = [sid for sid in existing_augur if sid not in wanted_by_id]
        return ConfigDiff(added=added, updated=updated, removed=removed)

    def apply(self, manifest: Manifest, config_path: Path | None = None) -> Path | None:
        path = config_path or self.default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = self._read(path) if path.exists() else {}
        existing_servers = dict(existing.get("mcpServers") or {})

        existing_augur = {sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")}

        for sid in list(existing_servers):
            if sid.startswith("augur"):
                del existing_servers[sid]
        for entry in self._managed_entries(manifest, existing_server_ids=set(existing_augur)):
            existing_servers[entry.id] = self._render_entry(entry)
        existing["mcpServers"] = existing_servers

        backup: Path | None = self._backup(path) if path.exists() else None
        self._write(path, existing)
        return backup

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text())

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(path)

    @staticmethod
    def _backup(path: Path) -> Path:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, backup)
        return backup

    def _managed_entries(
        self,
        manifest: Manifest,
        *,
        existing_server_ids: set[str] | None = None,
    ) -> list[ServerEntry]:
        return manifest.all_augur_servers_for_client(
            self.name,
            existing_server_ids=existing_server_ids,
        )

    @staticmethod
    def _render_entry(entry: ServerEntry) -> dict:
        return render_entry_dict(entry, client="claude")
