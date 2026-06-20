"""Adapter for ~/.codex/config.toml MCP servers section.

Codex stores MCP servers as `[mcp_servers.<id>]` TOML tables with
`command` and `args`. The adapter writes the current split Augur MCP
topology from `config/system/mcp_servers.yaml` and removes retired
managed Augur entries such as the old `augur` monolith.

Per Track 2 spec: only entries with id matching `augur*` are managed.
Other servers (context7, claude-in-chrome, etc.) are preserved verbatim.
"""

from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path

# tomllib is stdlib in 3.11+; tomli_w writes (we add this dependency).
import tomllib  # type: ignore[import-not-found]

try:
    import tomli_w  # type: ignore[import-not-found]
except ImportError as e:
    raise ImportError("tomli_w is required for the codex adapter. Add to dependencies: `uv add tomli_w`.") from e

from src.cli_config.codex_runtime import build_codex_mcp_entry
from src.cli_config.adapters.base import ConfigDiff
from src.cli_config.manifest import Manifest, ServerEntry


class CodexAdapter:
    name = "codex"

    def default_config_path(self) -> Path:
        return Path.home() / ".codex" / "config.toml"

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        path = config_path or self.default_config_path()
        existing = self._read(path) if path.exists() else {}
        existing_servers = existing.get("mcp_servers") or {}

        # Filter to augur-* entries only
        existing_augur = {sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")}

        entries = manifest.all_augur_servers_for_client(
            self.name,
            existing_server_ids=set(existing_augur),
        )
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
        existing_servers = dict(existing.get("mcp_servers") or {})

        existing_augur = {sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")}

        # Drop all augur-* servers, then re-add from manifest (idempotent, no merge).
        for sid in list(existing_servers):
            if sid.startswith("augur"):
                del existing_servers[sid]

        entries = manifest.all_augur_servers_for_client(
            self.name,
            existing_server_ids=set(existing_augur),
        )
        for entry in entries:
            existing_servers[entry.id] = self._render_entry(entry)

        existing["mcp_servers"] = existing_servers

        backup: Path | None = self._backup(path) if path.exists() else None
        self._write(path, existing)
        return backup

    @staticmethod
    def _read(path: Path) -> dict:
        with path.open("rb") as fh:
            return tomllib.load(fh)

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            tomli_w.dump(data, fh)
        tmp.replace(path)

    @staticmethod
    def _backup(path: Path) -> Path:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, backup)
        return backup

    @staticmethod
    def _render_entry(entry: ServerEntry) -> dict:
        """Translate a ServerEntry into the dict shape Codex expects."""
        args = list(entry.args)
        args.extend(entry.per_client_args.get("codex", []))
        return build_codex_mcp_entry(
            args,
            startup_timeout_sec=entry.startup_timeout_sec,
        )
