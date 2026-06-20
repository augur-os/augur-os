"""Plugin Events MCP tool registration (ADR-122).

Tools: plugin-events-list, plugin-events-acknowledge.
Reads and writes the plugin_events.json file maintained by plugin_watcher.py.
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import logger

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_runtime_dir
    from src.plugins.skill_discovery import discover_all_skills, invalidate_discovery_cache
except ImportError:
    import os
    import sys

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_runtime_dir() -> Path:
        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir)
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"

    def discover_all_skills(*, tiers=None):
        return []

    def invalidate_discovery_cache() -> None:
        return None


def _events_file() -> Path:
    return get_runtime_dir() / "plugin_events.json"


def _current_registry_keys() -> tuple[set[str], set[str]]:
    """Return current canonical skill keys and names."""
    invalidate_discovery_cache()
    skills: set[str] = set()
    skill_names: set[str] = set()
    for record in discover_all_skills(tiers=(0,)):
        hub = str(getattr(record, "hub", "") or "").strip()
        name = str(getattr(record, "name", "") or "").strip()
        if not name:
            continue
        skill_names.add(name)
        skills.add(name)
        source_root = str(getattr(record, "source_root", "") or "").strip()
        for scope in (hub, source_root):
            if not scope:
                continue
            skills.add(f"{scope}/{name}")
    return skills, skill_names


def _prune_contradictory_events(events: list[dict]) -> list[dict]:
    """Drop false removal events contradicted by the current canonical registry."""
    current_skills, current_skill_names = _current_registry_keys()
    filtered: list[dict] = []
    for event in events:
        if event.get("acknowledged", False):
            filtered.append(event)
            continue

        event_type = event.get("type")
        bundle = str(event.get("bundle") or "").strip()
        skill = str(event.get("skill") or "").strip()

        if event_type in {"bundle_added", "bundle_removed"}:
            continue
        if event_type == "skill_removed" and bundle and skill:
            if skill in current_skill_names or f"{bundle}/{skill}" in current_skills:
                continue
        filtered.append(event)
    return filtered


def _load_events() -> list[dict]:
    path = _events_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        pruned = _prune_contradictory_events(data)
        if pruned != data:
            _save_events(pruned)
        return pruned
    except Exception as exc:
        logger.warning("Failed to read plugin_events.json: %s", exc)
        return []


def _save_events(events: list[dict]) -> None:
    path = _events_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique tmp suffix per call so concurrent writers don't race the rename
    # (FileNotFoundError observed when one caller's replace moved the shared
    # .tmp file before another caller's replace ran).
    tmp = path.with_suffix(f".tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(events, indent=2), encoding="utf-8")
        # os.replace is atomic but raises PermissionError on Windows
        # (WinError 5/32) when the destination is momentarily open by another
        # process (a concurrent reader or AV scan). The lock is transient, so
        # retry with backoff before surfacing the failure.
        last_exc: PermissionError | None = None
        for attempt in range(10):
            try:
                tmp.replace(path)
                last_exc = None
                break
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.05 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def register_plugin_event_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register plugin event tools with the MCP server."""

    @mcp.tool(
        name="plugin-events-list",
        annotations=tool_annotations(
            {
                "title": "List Plugin Events",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def plugin_events_list_tool() -> str:
        """List unacknowledged plugin events (skill/bundle additions and removals).

        Returns JSON with count and events array. Each event has type, bundle,
        optional skill, timestamp, and acknowledged fields.
        """
        metrics.track_tool("plugin_events_list", skill="daemon")
        events = _load_events()
        unacknowledged = [e for e in events if not e.get("acknowledged", False)]
        if not unacknowledged:
            return json.dumps(
                {"count": 0, "events": [], "source": "live"},
                indent=2,
            )
        return json.dumps(
            {"count": len(unacknowledged), "events": unacknowledged, "source": "live"},
            indent=2,
        )

    @mcp.tool(
        name="plugin-events-acknowledge",
        annotations=tool_annotations(
            {
                "title": "Acknowledge Plugin Events",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def plugin_events_acknowledge_tool(
        timestamp: str | None = None,
        index: int | None = None,
        all: bool = False,
    ) -> str:
        """Mark plugin events as acknowledged.

        Args:
            timestamp: Acknowledge the event with this timestamp
            index: Acknowledge the event at this index
            all: Acknowledge all events
        """
        metrics.track_tool("plugin_events_acknowledge", skill="daemon")
        events = _load_events()
        acknowledged_count = 0

        for i, event in enumerate(events):
            if event.get("acknowledged", False):
                continue
            if all:
                event["acknowledged"] = True
                acknowledged_count += 1
            elif timestamp and event.get("timestamp") == timestamp:
                event["acknowledged"] = True
                acknowledged_count += 1
            elif index is not None and i == index:
                event["acknowledged"] = True
                acknowledged_count += 1

        _save_events(events)
        return json.dumps(
            {"acknowledged": acknowledged_count, "total": len(events)},
            indent=2,
        )

    logger.info("Registered plugin-events MCP tools")
