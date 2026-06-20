"""Read config/system/wiki_signals.yaml with typed defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_TIER_CAPS = {"critical": 5, "high": 15, "medium": 30, "low": 50}


def _copilot_default_path() -> str:
    if os.name == "nt":
        return "~/AppData/Roaming/GitHub Copilot/sessions"
    return "~/Library/Application Support/GitHub Copilot/sessions"


def _chatgpt_default_path() -> str:
    if os.name == "nt":
        return "~/AppData/Roaming/ChatGPT/exports"
    return "~/Library/Application Support/ChatGPT/exports"


def _cursor_default_path() -> str:
    if os.name == "nt":
        return "~/AppData/Roaming/Cursor/conversations"
    return "~/Library/Application Support/Cursor/conversations"


def _default_client_memory() -> dict[str, Any]:
    return {
        "enabled": True,
        "clients": {
            "claude": {
                "enabled": True,
                "path": "~/.claude",
                "globs": ["projects/*/memory/*.md"],
                "tier": "critical",
            },
            "codex": {
                "enabled": True,
                "path": "~/.codex/sessions",
                "tier": "critical",
            },
            "gemini": {
                "enabled": True,
                "path": "~/.gemini/conversations",
                "tier": "high",
            },
            "copilot": {
                "enabled": True,
                "path": _copilot_default_path(),
                "tier": "high",
            },
            "chatgpt": {
                "enabled": True,
                "path": _chatgpt_default_path(),
                "tier": "high",
            },
            "cursor": {
                "enabled": True,
                "path": _cursor_default_path(),
                "tier": "high",
            },
        },
    }


@dataclass
class WikiSignalsConfig:
    mtime_window_minutes: int = 30
    tier_caps: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_TIER_CAPS))
    extraction_limit: int = 20
    include_logs: bool = False
    episodic: dict[str, Any] = field(default_factory=lambda: {"enabled": True, "path": None})
    client_memory: dict[str, Any] = field(default_factory=_default_client_memory)


def load_config(path: Path) -> WikiSignalsConfig:
    """Load wiki signal config, merging YAML values onto code defaults."""
    cfg = WikiSignalsConfig()
    if not path.is_file():
        return cfg
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return cfg

    if "mtime_window_minutes" in raw:
        cfg.mtime_window_minutes = max(0, int(raw["mtime_window_minutes"]))
    if "tier_caps" in raw and isinstance(raw["tier_caps"], dict):
        cfg.tier_caps.update({str(k): max(0, int(v)) for k, v in raw["tier_caps"].items()})
    if "extraction_limit" in raw:
        cfg.extraction_limit = max(0, int(raw["extraction_limit"]))
    if "include_logs" in raw:
        cfg.include_logs = bool(raw["include_logs"])

    episodic = raw.get("episodic")
    if isinstance(episodic, dict):
        cfg.episodic.update(episodic)

    client_memory = raw.get("client_memory")
    if isinstance(client_memory, dict):
        _merge_client_memory(cfg.client_memory, client_memory)

    _merge_legacy_client_memory(cfg.client_memory, raw)
    return cfg


def _merge_client_memory(target: dict[str, Any], value: dict[str, Any]) -> None:
    if "enabled" in value:
        target["enabled"] = bool(value["enabled"])
    raw_clients = value.get("clients")
    if not isinstance(raw_clients, dict):
        return
    clients = target.setdefault("clients", {})
    for name, spec in raw_clients.items():
        if isinstance(spec, dict):
            current = dict(clients.get(str(name), {}))
            current.update(spec)
            clients[str(name)] = current


def _merge_legacy_client_memory(target: dict[str, Any], raw: dict[str, Any]) -> None:
    """Map the old per-client fields into the neutral client_memory shape."""
    clients = target.setdefault("clients", {})
    legacy_map = {
        "memory_files": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "copilot": "copilot",
    }
    for legacy_key, client_name in legacy_map.items():
        value = raw.get(legacy_key)
        if isinstance(value, dict):
            current = dict(clients.get(client_name, {}))
            current.update(value)
            clients[client_name] = current
    external_clients = raw.get("external_clients")
    if isinstance(external_clients, dict):
        for name, spec in external_clients.items():
            if isinstance(spec, dict):
                current = dict(clients.get(str(name), {}))
                current.update(spec)
                clients[str(name)] = current
