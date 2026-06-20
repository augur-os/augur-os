"""Scheduled execution browse contract helpers."""

from __future__ import annotations

import json
from typing import Any

from .scheduled_sources import (
    load_augur_internal_schedules,
    load_claude_remote_schedules,
    load_claude_schedules,
    load_codex_schedules,
)


def list_scheduled_execution_records(search: str | None = None) -> list[dict[str, Any]]:
    """Return normalized scheduled execution records."""

    records = [
        *load_augur_internal_schedules(),
        *load_codex_schedules(),
        *load_claude_schedules(),
        *load_claude_remote_schedules(),
    ]
    if not search:
        return records

    needle = search.strip().lower()
    return [
        record
        for record in records
        if needle in record.get("title", "").lower()
        or needle in record.get("prompt_summary", "").lower()
        or needle in record.get("source", "").lower()
    ]


def list_scheduled_execution_items(search: str | None = None) -> list[dict[str, Any]]:
    """Return normalized browse rows for scheduled executions."""

    items: list[dict[str, Any]] = []
    for record in list_scheduled_execution_records(search):
        row_id = record["id"]
        drift_status = record.get("drift_status", "unknown")
        source = record.get("source", "")
        actions: list[dict[str, Any]] = []
        # Conflict-resolution actions are armed per drift status:
        #   codex-edited / cloud-edited → both (user surface edit vs Augur seed)
        #   seed-evolved                → Push only (Adopt would revert intent)
        # Other statuses (in-sync, external, ...) → no actions.
        supports_conflict = source in ("codex", "claude-remote")
        arms_adopt = supports_conflict and drift_status in (
            "codex-edited",
            "cloud-edited",
        )
        arms_push = supports_conflict and drift_status in (
            "codex-edited",
            "cloud-edited",
            "seed-evolved",
        )
        if arms_adopt:
            actions.append(
                {
                    "id": f"adopt-{row_id}",
                    "label": "Adopt surface version",
                    "type": "mcp-tool",
                    "target": "routine-adopt-cloud",
                    "args": {"routine_id": row_id},
                }
            )
        if arms_push:
            actions.append(
                {
                    "id": f"push-{row_id}",
                    "label": "Push my version",
                    "type": "mcp-tool",
                    "target": "routine-push-local",
                    "args": {"routine_id": row_id},
                }
            )
        items.append(
            {
                "id": row_id,
                "title": record["title"],
                "description": record.get("prompt_summary", ""),
                "hub": "system",
                "type": "scheduled-executions",
                "source_path": record.get("source_path", ""),
                "actions": actions,
                "metadata": {
                    "source": source,
                    "kind": record.get("kind", ""),
                    "status": record.get("status", "unknown"),
                    "schedule": record.get("schedule_human", ""),
                    "workspace": record.get("workspace", ""),
                    "model": record.get("model", ""),
                    "lastRun": record.get("last_run_at"),
                    "nextRun": record.get("next_run_at"),
                    "managed_by": record.get("managed_by", "unknown"),
                    "drift_status": drift_status,
                    "cacheFetchedAt": record.get("cache_fetched_at", ""),
                },
            }
        )
    return items


def get_scheduled_execution_detail_impl(execution_id: str) -> str:
    """Return one scheduled execution detail payload."""

    for record in list_scheduled_execution_records():
        if record.get("id") == execution_id:
            return json.dumps({"success": True, "detail": record})
    return json.dumps({"success": False, "error": f"Scheduled execution '{execution_id}' not found"})


def refresh_codex_routines_impl() -> str:
    """Rescan ~/.codex/automations/ and return drift-classified routine rows.

    Server-side only — pure file scan, no external API. Compares each installed
    automation.toml against current Augur seeds; emits managed_by + drift_status
    per entry. Use when the user manually edits Codex automations and wants the
    Browse view re-synced from disk truth.
    """
    items = list_scheduled_execution_items()
    codex_items = [it for it in items if it["metadata"].get("source") == "codex"]
    return json.dumps(
        {
            "success": True,
            "count": len(codex_items),
            "items": codex_items,
        }
    )


def refresh_cloud_routines_impl() -> str:
    """Refresh the Claude remote routines cache via a `claude` CLI subprocess.

    Server-side Python cannot easily obtain the Anthropic OAuth token, so we
    delegate to a one-shot `claude --print` subprocess which inherits the
    user's existing auth. The subprocess uses RemoteTrigger to list current
    remote routines and writes them back to the cache file in Augur's
    normalized schema.
    """
    import shutil as _shutil
    import subprocess as _subprocess
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from src.config.paths import get_cache_dir
    from src.mcp.augur_shared.safe_subprocess import safe_run

    claude_bin = _shutil.which("claude")
    if not claude_bin:
        return json.dumps(
            {
                "success": False,
                "error": "claude CLI not found on PATH; install Claude Code to enable cloud refresh.",
            }
        )

    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "claude-remote-routines.json"

    prompt = (
        "Refresh the Augur Claude-remote routines cache. Steps: (1) call the "
        "RemoteTrigger tool with action='list'; (2) parse the `data` array of "
        "triggers; (3) write a single JSON file at "
        f"{cache_path} with this exact schema and no surrounding prose: "
        '{"fetched_at": "<ISO8601 UTC>", "routines": [{"id": "<trigger id>", '
        '"name": "<trigger name>", "cron_expression": "<cron>", "enabled": '
        '<bool>, "prompt_summary": "<first message content first line>", '
        '"model": "<session model>", "repo": "<git url>", "last_run_at": null, '
        '"next_run_at": "<next_run_at>", "drift_status": "in-sync"}]}. '
        "Use the Write tool to write the file. Reply with only the literal "
        'string "OK" on success or "ERR: <reason>" on failure.'
    )

    try:
        result = safe_run(
            [claude_bin, "--print", prompt],
            capture_output=True,
            timeout=120,
            text=True,
            check=False,
        )
    except _subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "claude --print refresh timed out after 120s"})

    if result.returncode != 0:
        return json.dumps(
            {
                "success": False,
                "error": f"claude --print exited {result.returncode}",
                "stderr": result.stderr[-500:],
            }
        )

    if not cache_path.is_file():
        return json.dumps(
            {
                "success": False,
                "error": "claude --print finished but cache file was not written",
                "stdout": result.stdout[-200:],
            }
        )

    items = list_scheduled_execution_items()
    cloud_items = [it for it in items if it["metadata"].get("source") == "claude-remote"]
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = str(payload.get("fetched_at", _dt.now(_tz.utc).isoformat()))
    except Exception:
        fetched_at = _dt.now(_tz.utc).isoformat()

    return json.dumps(
        {
            "success": True,
            "count": len(cloud_items),
            "fetched_at": fetched_at,
            "items": cloud_items,
        }
    )
