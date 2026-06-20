"""AI bridge connection/scan/refresh scope handlers."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import _helpers

# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_bridge_connection_create(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    if not hub:
        return {"success": False, "error": "Missing 'hub' parameter"}

    path = _helpers._get_state_dir() / "bridge" / hub / "connections.json"
    data = _helpers._read_json(path)
    connections = data.setdefault("connections", [])

    entry = {
        "id": str(uuid.uuid4()),
        "hub": hub,
        "source_type": params.get("source_type"),
        "source_path": params.get("source_path"),
        "integrations": params.get("integrations", []),
        "ignored": params.get("ignored", []),
        "createdAt": datetime.now().isoformat(),
    }
    connections.append(entry)
    data["hub"] = hub
    data["total"] = len(connections)
    _helpers._write_json(path, data)
    return {"success": True, "connection": entry}


def _handle_bridge_connection_delete(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    connection_id = params.get("connection_id")
    if not hub or not connection_id:
        return {"success": False, "error": "Missing 'hub' or 'connection_id' parameter"}

    path = _helpers._get_state_dir() / "bridge" / hub / "connections.json"
    data = _helpers._read_json(path)
    connections = data.get("connections", [])
    original_len = len(connections)
    data["connections"] = [c for c in connections if c.get("id") != connection_id]

    if len(data["connections"]) == original_len:
        return {"success": False, "error": f"Connection '{connection_id}' not found"}

    data["total"] = len(data["connections"])
    _helpers._write_json(path, data)
    return {"success": True, "connection_id": connection_id, "deleted": True}


def _handle_bridge_scan(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    source_type = params.get("source_type")
    source_path = params.get("path", params.get("source_path", ""))
    if not hub or not source_type or not source_path:
        return {"success": False, "error": "Missing hub, source_type, or path"}

    scan_dir = Path(source_path)
    if not scan_dir.exists() or not scan_dir.is_dir():
        return {"success": False, "error": f"Path does not exist or is not a directory: {source_path}"}

    files: list[dict[str, Any]] = []
    integrations: list[str] = []
    for f in sorted(scan_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            ext = f.suffix.lower()
            files.append(
                {
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "extension": ext,
                }
            )
            if ext not in integrations:
                integrations.append(ext)

    # Persist scan result
    result_path = _helpers._get_state_dir() / "bridge" / hub / "last-scan.json"
    result = {
        "hub": hub,
        "source_type": source_type,
        "source_path": source_path,
        "status": "complete",
        "files": files,
        "integrations": integrations,
        "scannedAt": datetime.now().isoformat(),
    }
    _helpers._write_json(result_path, result)
    return result


def _handle_bridge_refresh(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    if not hub:
        return {"success": False, "error": "Missing 'hub' parameter"}

    conn_path = _helpers._get_state_dir() / "bridge" / hub / "connections.json"
    data = _helpers._read_json(conn_path)
    connections = data.get("connections", [])

    # Record refresh event
    refresh_path = _helpers._get_state_dir() / "bridge" / hub / "last-refresh.json"
    result = {
        "hub": hub,
        "refreshed": len(connections),
        "summaries": [
            {"id": c.get("id"), "source_type": c.get("source_type"), "status": "refreshed"} for c in connections
        ],
        "updated_at": datetime.now().isoformat(),
    }
    _helpers._write_json(refresh_path, result)
    return result


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_bridge_connections(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    if not hub:
        return {"hub": "", "connections": [], "total": 0}
    path = _helpers._get_state_dir() / "bridge" / hub / "connections.json"
    data = _helpers._read_json(path)
    connections = data.get("connections", [])
    return {"hub": hub, "connections": connections, "total": len(connections)}


def _read_bridge_summary(params: dict[str, Any]) -> dict[str, Any]:
    hub = params.get("hub")
    if not hub:
        return {"hub": None, "summaries": [], "connections": 0, "updated_at": None}

    conn_path = _helpers._get_state_dir() / "bridge" / hub / "connections.json"
    data = _helpers._read_json(conn_path)
    connections = data.get("connections", [])

    summaries = [
        {
            "id": c.get("id"),
            "source_type": c.get("source_type"),
            "source_path": c.get("source_path"),
            "integrations": c.get("integrations", []),
        }
        for c in connections
    ]

    return {
        "hub": hub,
        "summaries": summaries,
        "connections": len(connections),
        "updated_at": datetime.now().isoformat(),
    }
