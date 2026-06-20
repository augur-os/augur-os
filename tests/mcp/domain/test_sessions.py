"""Tests for per-session focus state management (ADR-254)."""

import json
import os
import time


from src.mcp.augur_framework.tools.domain.sessions import (
    create_session,
    delete_session,
    prune_stale_sessions,
    read_session,
    update_session_tool,
)


def test_create_session_writes_file(tmp_path):
    data = create_session(tmp_path, "cli-100", "cli", hub="finance", skill="finance")
    path = tmp_path / "cli-100.json"
    assert path.exists()
    stored = json.loads(path.read_text())
    assert stored["session_id"] == "cli-100"
    assert stored["source"] == "cli"
    assert stored["hub"] == "finance"
    assert stored["skill"] == "finance"
    assert stored["recent_tools"] == []
    assert "started_at" in stored
    assert "last_activity" in stored
    assert data == stored


def test_update_session_appends_tool(tmp_path):
    create_session(tmp_path, "s1", "ide")
    update_session_tool(tmp_path, "s1", "finance-summary")
    update_session_tool(tmp_path, "s1", "finance-transactions")
    data = read_session(tmp_path, "s1")
    assert data["recent_tools"] == ["finance-summary", "finance-transactions"]


def test_update_session_keeps_last_20_tools(tmp_path):
    create_session(tmp_path, "s2", "cli")
    for i in range(25):
        update_session_tool(tmp_path, "s2", f"tool-{i}")
    data = read_session(tmp_path, "s2")
    assert len(data["recent_tools"]) == 20
    # Should keep the last 20 (tool-5 through tool-24)
    assert data["recent_tools"][0] == "tool-5"
    assert data["recent_tools"][-1] == "tool-24"


def test_delete_session_removes_file(tmp_path):
    create_session(tmp_path, "s3", "cli")
    assert (tmp_path / "s3.json").exists()
    delete_session(tmp_path, "s3")
    assert not (tmp_path / "s3.json").exists()


def test_delete_session_missing_file_no_error(tmp_path):
    # Should not raise
    delete_session(tmp_path, "nonexistent")


def test_read_session_returns_data(tmp_path):
    create_session(tmp_path, "s4", "dashboard", hub="career", skill="career_status")
    data = read_session(tmp_path, "s4")
    assert data is not None
    assert data["session_id"] == "s4"
    assert data["source"] == "dashboard"
    assert data["hub"] == "career"
    assert data["skill"] == "career_status"


def test_read_session_missing_returns_none(tmp_path):
    result = read_session(tmp_path, "does-not-exist")
    assert result is None


def test_prune_stale_sessions(tmp_path):
    # Create two sessions
    create_session(tmp_path, "old-1", "cli")
    create_session(tmp_path, "old-2", "cli")
    create_session(tmp_path, "fresh", "cli")

    # Backdate old sessions by setting mtime to 2 hours ago
    old_time = time.time() - 7200
    for name in ["old-1", "old-2"]:
        path = tmp_path / f"{name}.json"
        os.utime(path, (old_time, old_time))

    pruned = prune_stale_sessions(tmp_path, max_age_seconds=3600)
    assert pruned == 2
    assert not (tmp_path / "old-1.json").exists()
    assert not (tmp_path / "old-2.json").exists()
    assert (tmp_path / "fresh.json").exists()
