"""Schedule/cron scope handlers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from . import _helpers

# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_schedule_create(params: dict[str, Any]) -> dict[str, Any]:
    plugin = params.get("plugin", "default")
    path = _helpers._get_state_dir() / "schedules" / plugin / "schedules.json"
    data = _helpers._read_json(path)
    schedules = data.setdefault("schedules", [])

    entry = {
        "id": str(uuid.uuid4()),
        "action_id": params.get("action_id"),
        "plugin": plugin,
        "schedule": params.get("schedule"),
        "label": params.get("label", ""),
        "enabled": params.get("enabled", True),
        "createdAt": datetime.now().isoformat(),
    }
    schedules.append(entry)
    _helpers._write_json(path, data)
    return {"success": True, "schedule": entry}


def _handle_schedule_update(params: dict[str, Any]) -> dict[str, Any]:
    plugin = params.get("plugin", "default")
    schedule_id = params.get("id")
    if not schedule_id:
        return {"success": False, "error": "Missing 'id' parameter"}

    path = _helpers._get_state_dir() / "schedules" / plugin / "schedules.json"
    data = _helpers._read_json(path)
    schedules = data.get("schedules", [])

    updates = params.get("updates", {})
    found = False
    for s in schedules:
        if s.get("id") == schedule_id:
            s.update(updates)
            s["updatedAt"] = datetime.now().isoformat()
            found = True
            break

    if not found:
        return {"success": False, "error": f"Schedule '{schedule_id}' not found"}

    _helpers._write_json(path, data)
    return {"success": True, "id": schedule_id}


def _handle_schedule_delete(params: dict[str, Any]) -> dict[str, Any]:
    plugin = params.get("plugin", "default")
    schedule_id = params.get("id")
    if not schedule_id:
        return {"success": False, "error": "Missing 'id' parameter"}

    path = _helpers._get_state_dir() / "schedules" / plugin / "schedules.json"
    data = _helpers._read_json(path)
    schedules = data.get("schedules", [])
    original_len = len(schedules)
    data["schedules"] = [s for s in schedules if s.get("id") != schedule_id]

    if len(data["schedules"]) == original_len:
        return {"success": False, "error": f"Schedule '{schedule_id}' not found"}

    _helpers._write_json(path, data)
    return {"success": True, "id": schedule_id, "deleted": True}


def _handle_schedule_run_now(params: dict[str, Any]) -> dict[str, Any]:
    plugin = params.get("plugin", "default")
    schedule_id = params.get("id")
    if not schedule_id:
        return {"success": False, "error": "Missing 'id' parameter"}

    # Record run-now request in history
    history_path = _helpers._get_state_dir() / "schedules" / "history.json"
    history = _helpers._read_json(history_path)
    entries = history.setdefault("entries", [])
    entries.append(
        {
            "id": schedule_id,
            "plugin": plugin,
            "action": "run-now",
            "timestamp": datetime.now().isoformat(),
        }
    )
    _helpers._write_json(history_path, history)

    return {"success": True, "id": schedule_id, "plugin": plugin, "action": "run-now"}


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_schedules(params: dict[str, Any]) -> dict[str, Any]:
    plugin = params.get("plugin")
    base = _helpers._get_state_dir() / "schedules"
    all_schedules: list[dict[str, Any]] = []

    if plugin:
        path = base / plugin / "schedules.json"
        data = _helpers._read_json(path)
        all_schedules.extend(data.get("schedules", []))
    else:
        if base.exists():
            for plugin_dir in sorted(base.iterdir()):
                if plugin_dir.is_dir():
                    path = plugin_dir / "schedules.json"
                    data = _helpers._read_json(path)
                    all_schedules.extend(data.get("schedules", []))

    return {"schedules": all_schedules}


def _read_schedule_history(params: dict[str, Any]) -> dict[str, Any]:
    days = params.get("days", 7)
    path = _helpers._get_state_dir() / "schedules" / "history.json"
    data = _helpers._read_json(path)
    entries = data.get("entries", [])
    return {
        "days": days,
        "entries": entries,
        "total_entries": len(entries),
    }
