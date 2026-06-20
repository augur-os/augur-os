"""System scope handlers — telemetry, self-heal, insights, feedback, MCP usage."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from . import _helpers

# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_agent_telemetry_record(params: dict[str, Any]) -> dict[str, Any]:
    """Record agent telemetry via the performance ledger (ADR-460)."""
    from src.lib.runtime.performance_ledger import TaskRecord, record_task

    record = TaskRecord(
        agent=params.get("agent") or "unknown",
        tier=params.get("tier") or "standard",
        outcome=params.get("outcome") or "unknown",
        duration_seconds=float(params.get("duration_seconds") or params.get("durationSeconds") or 0),
    )
    record_task(record)
    return {"success": True, "recorded": True, "id": record.id}


def _handle_self_heal_event(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "self-heal" / "events.json"
    data = _helpers._read_json(path)
    events = data.setdefault("events", [])
    events.append(
        {
            "source": params.get("source"),
            "category": params.get("category"),
            "severity": params.get("severity"),
            "message": params.get("message"),
            "context": params.get("context", {}),
            "timestamp": datetime.now().isoformat(),
        }
    )
    # Keep last 500 events
    if len(events) > 500:
        data["events"] = events[-500:]
    _helpers._write_json(path, data)
    return {"ok": True}


def _handle_prompt_feedback(params: dict[str, Any]) -> dict[str, Any]:
    prompt_name = params.get("prompt_name") or params.get("promptId")
    if not prompt_name:
        return {"success": False, "error": "Missing 'prompt_name' parameter"}
    rating = params.get("rating")
    if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
        return {"success": False, "error": "rating must be a number between 1 and 5"}

    from src.config.paths import get_runtime_dir

    feedback_dir = get_runtime_dir() / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    safe_name = prompt_name.replace("/", "_").replace("\\", "_")
    path = feedback_dir / f"{safe_name}.json"

    # Read existing feedback (list) or start fresh
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    else:
        existing = []

    entry = {
        "timestamp": datetime.now().isoformat(),
        "rating": rating,
        "comment": params.get("comment") or params.get("feedback"),
        "session_id": params.get("session_id") or params.get("actionId"),
    }
    existing.append(entry)
    _helpers._write_json(path, existing)
    return {"success": True, "total_entries": len(existing)}


def _handle_prepare_execution(params: dict[str, Any]) -> dict[str, Any]:
    backlog_path = params.get("backlog_path")
    if not backlog_path:
        return {"success": False, "error": "Missing 'backlog_path' parameter"}

    path = _helpers._get_state_dir() / "adaptive-growth" / "prepare-execution.json"
    data = _helpers._read_json(path)
    data["backlog_path"] = backlog_path
    data["status"] = "prepared"
    data["preparedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "backlog_path": backlog_path, "status": "prepared"}


def _handle_prepare_task(params: dict[str, Any]) -> dict[str, Any]:
    backlog_path = params.get("backlog_path")
    task_index = params.get("task_index")
    if not backlog_path:
        return {"success": False, "error": "Missing 'backlog_path' parameter"}
    if task_index is None:
        return {"success": False, "error": "Missing 'task_index' parameter"}

    path = _helpers._get_state_dir() / "adaptive-growth" / "prepare-task.json"
    data = _helpers._read_json(path)
    data["backlog_path"] = backlog_path
    data["task_index"] = task_index
    data["status"] = "prepared"
    data["preparedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "backlog_path": backlog_path, "task_index": task_index}


def _handle_mcp_tool_usage(params: dict[str, Any]) -> dict[str, Any]:
    """Record an MCP tool usage event to {state_dir}/mcp/tool-usage.json."""
    tool = params.get("tool")
    if not tool:
        return {"success": False, "error": "Missing 'tool' parameter"}

    path = _helpers._get_state_dir() / "mcp" / "tool-usage.json"
    data = _helpers._read_json(path)
    stats = data.setdefault("stats", {})

    entry = stats.setdefault(tool, {"count": 0, "lastUsed": ""})
    entry["count"] = entry.get("count", 0) + 1
    entry["lastUsed"] = datetime.now().isoformat()

    # Track per-page usage when page is provided
    page = params.get("page", "/")
    pages = entry.setdefault("pages", {})
    pages[page] = pages.get(page, 0) + 1

    data["recordCount"] = sum(s.get("count", 0) for s in stats.values())
    _helpers._write_json(path, data)
    return {"success": True, "recorded": True, "tool": tool}


def _handle_agent_rules_sync(_params: dict[str, Any]) -> dict[str, Any]:
    """Trigger agent config sync by writing a marker file for the daemon.

    The marker signals that agent rules/config have changed and downstream
    generated files (IDE integrations, prompts, etc.) need regeneration.
    """
    marker_path = _helpers._get_state_dir() / "sync" / "agent-rules-sync.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "requested": True,
        "requestedAt": datetime.now().isoformat(),
        "status": "pending",
    }
    _helpers._write_json(marker_path, marker)
    return {"success": True, "action": "sync-triggered", "marker": str(marker_path)}


def _handle_insights_dismiss(params: dict[str, Any]) -> dict[str, Any]:
    insight_id = params.get("id")
    if not insight_id:
        return {"success": False, "error": "Missing 'id' parameter"}

    path = _helpers._get_state_dir() / "insights" / "dismissed.json"
    data = _helpers._read_json(path)
    dismissed = data.setdefault("dismissed", [])
    dismissed.append(
        {
            "id": insight_id,
            "dismissedAt": datetime.now().isoformat(),
        }
    )
    _helpers._write_json(path, data)
    return {"success": True, "id": insight_id, "action": "dismissed"}


def _handle_insights_accept(params: dict[str, Any]) -> dict[str, Any]:
    insight_id = params.get("id")
    if not insight_id:
        return {"success": False, "error": "Missing 'id' parameter"}

    path = _helpers._get_state_dir() / "insights" / "accepted.json"
    data = _helpers._read_json(path)
    accepted = data.setdefault("accepted", [])
    accepted.append(
        {
            "id": insight_id,
            "acceptedAt": datetime.now().isoformat(),
        }
    )
    _helpers._write_json(path, data)
    return {"success": True, "id": insight_id, "action": "accepted"}


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_adaptive_growth_summary(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "adaptive-growth" / "prepare-execution.json"
    data = _helpers._read_json(path)
    return {
        "dir": str(_helpers._get_state_dir() / "adaptive-growth"),
        "backlog": data if data else None,
        "recurringIncidents": [],
        "promotedTodos": [],
    }


def _read_adaptive_growth_backlogs(_params: dict[str, Any]) -> dict[str, Any]:
    base = _helpers._get_state_dir() / "adaptive-growth"
    backlogs: list[dict[str, Any]] = []
    if base.exists():
        for f in sorted(base.iterdir()):
            if f.is_file() and f.suffix == ".json" and f.stem != "prepare-execution":
                backlogs.append({"name": f.stem, "path": str(f)})
    return {
        "dir": str(base),
        "backlogs": backlogs,
        "recurringIncidents": [],
        "promotedTodos": [],
    }


def _read_prompt_feedback(params: dict[str, Any]) -> dict[str, Any]:
    prompt_name = params.get("prompt_name")
    if not prompt_name:
        return {"success": False, "error": "Missing 'prompt_name' parameter"}

    from src.config.paths import get_runtime_dir

    feedback_dir = get_runtime_dir() / "feedback"
    safe_name = prompt_name.replace("/", "_").replace("\\", "_")
    path = feedback_dir / f"{safe_name}.json"

    if not path.exists():
        return {"success": True, "feedback": [], "stats": {"count": 0, "averageRating": 0}}

    try:
        feedback = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(feedback, list):
            feedback = []
    except Exception:
        feedback = []

    count = len(feedback)
    avg = round(sum(e.get("rating", 0) for e in feedback) / count * 10) / 10 if count > 0 else 0

    return {
        "success": True,
        "feedback": feedback,
        "stats": {"count": count, "averageRating": avg},
    }


def _read_mcp_tool_usage(_params: dict[str, Any]) -> dict[str, Any]:
    """Read aggregated MCP tool usage stats from {state_dir}/mcp/tool-usage.json."""
    path = _helpers._get_state_dir() / "mcp" / "tool-usage.json"
    data = _helpers._read_json(path)
    return {
        "stats": data.get("stats", {}),
        "recordCount": data.get("recordCount", 0),
    }


def _read_insights_context(params: dict[str, Any]) -> dict[str, Any]:
    page = params.get("page", "")
    dismissed_path = _helpers._get_state_dir() / "insights" / "dismissed.json"
    accepted_path = _helpers._get_state_dir() / "insights" / "accepted.json"
    dismissed = _helpers._read_json(dismissed_path).get("dismissed", [])
    accepted = _helpers._read_json(accepted_path).get("accepted", [])
    dismissed_ids = {d.get("id") for d in dismissed}
    accepted_ids = {a.get("id") for a in accepted}

    # Read pending insights
    pending_path = _helpers._get_state_dir() / "insights" / "pending.json"
    pending_data = _helpers._read_json(pending_path)
    all_insights = pending_data.get("insights", [])
    pending_insights = [i for i in all_insights if i.get("id") not in dismissed_ids and i.get("id") not in accepted_ids]

    return {
        "page": page,
        "skill": "",
        "bundle": None,
        "tabs": [],
        "actions": [],
        "dataFiles": [],
        "usageStats": {},
        "pendingInsights": pending_insights,
    }
