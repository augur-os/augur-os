"""Tests that the claude-remote cache fetched_at surfaces into Browse metadata."""
from __future__ import annotations

import json


def test_load_claude_remote_schedules_emits_cache_fetched_at(tmp_path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude_remote import (
        load_claude_remote_schedules,
    )

    from src.config import paths as _paths
    monkeypatch.setattr(_paths, "get_cache_dir", lambda: tmp_path)
    cache = tmp_path / "claude-remote-routines.json"
    cache.write_text(
        json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_x",
                        "name": "Test",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/r",
                        "model": "m",
                        "repo": "r",
                        "last_run_at": None,
                        "next_run_at": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = load_claude_remote_schedules()
    assert len(rows) == 1
    assert rows[0].get("cache_fetched_at") == "2026-05-17T22:00:00Z"


def test_scheduled_execution_items_propagate_cache_freshness(tmp_path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    from src.config import paths as _paths
    monkeypatch.setattr(_paths, "get_cache_dir", lambda: tmp_path)
    (tmp_path / "claude-remote-routines.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-05-17T22:00:00Z",
                "routines": [
                    {
                        "id": "trig_x",
                        "name": "Test",
                        "cron_expression": "0 1 * * *",
                        "enabled": True,
                        "prompt_summary": "/r",
                        "model": "m",
                        "repo": "r",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = list_scheduled_execution_items()
    cloud = [r for r in rows if r["metadata"].get("source") == "claude-remote"]
    assert cloud, "expected at least one claude-remote row"
    assert cloud[0]["metadata"].get("cacheFetchedAt") == "2026-05-17T22:00:00Z"
