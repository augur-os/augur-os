"""Claude remote (cloud) scheduled routine cache loader.

Reads `<cache_dir>/claude-remote-routines.json`, a snapshot of remote
routines created via the Claude Code `/schedule` skill (which uses
the RemoteTrigger API). The cache is written by sync operations; this
module is a pure reader so Browse stays fast and credential-free.

Cache schema::

    {
      "fetched_at": "<iso8601>",
      "routines": [
        {
          "id": "<routine id>",
          "name": "<display name>",
          "cron_expression": "<cron in UTC>",
          "enabled": true,
          "prompt_summary": "<one-line prompt>",
          "model": "<model id>",
          "repo": "<git url>",
          "last_run_at": "<iso8601 or null>",
          "next_run_at": "<iso8601 or null>"
        }
      ]
    }
"""

from __future__ import annotations

import json
from typing import Any

from src.config import paths as path_config


def load_claude_remote_schedules() -> list[dict[str, Any]]:
    """Load cached Claude remote routines as normalized schedule rows."""
    cache_path = path_config.get_cache_dir() / "claude-remote-routines.json"
    if not cache_path.is_file():
        return []

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    rows: list[dict[str, Any]] = []
    cache_fetched_at = str(payload.get("fetched_at") or "")
    for routine in payload.get("routines", []):
        if not isinstance(routine, dict):
            continue
        routine_id = str(routine.get("id", ""))
        if not routine_id:
            continue
        drift_status = str(routine.get("drift_status") or "in-sync")
        rows.append(
            {
                "id": f"claude-remote:{routine_id}",
                "cache_fetched_at": cache_fetched_at,
                "native_id": routine_id,
                "title": str(routine.get("name", routine_id)),
                "source": "claude-remote",
                "kind": "remote-routine",
                "workspace": str(routine.get("repo", "")),
                "schedule_human": str(routine.get("cron_expression", "")),
                "prompt_summary": str(routine.get("prompt_summary", "")),
                "prompt_body": str(routine.get("prompt_summary", "")),
                "source_path": str(cache_path),
                "model": str(routine.get("model", "")),
                "status": "active" if routine.get("enabled", True) else "disabled",
                "last_run_at": routine.get("last_run_at"),
                "next_run_at": routine.get("next_run_at"),
                "managed_by": "augur",
                "drift_status": drift_status,
                "raw_schedule": {
                    "type": "cron",
                    "value": str(routine.get("cron_expression", "")),
                },
                "warnings": [],
            }
        )
    return rows
