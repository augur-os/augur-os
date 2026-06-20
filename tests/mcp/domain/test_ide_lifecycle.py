"""Tests for IDE agent session lifecycle (ADR-254 Gate 5).

ADR-254 Section 1.2 specifies:
  - IDE agents: session created at MCP connect, deleted at MCP disconnect
  - CLI: session created at first tool call, deleted via atexit
  - Dashboard: session created at page load, deleted via beforeunload
  - Safety net: nightly daemon prunes files older than 1 hour

This module tests the session lifecycle integration used by the MCP server
and CLI, verifying that sessions are created, read, and cleaned up correctly
across the full lifecycle.
"""

from __future__ import annotations

import json


from src.mcp.augur_framework.tools.domain.sessions import (
    create_session,
    delete_session,
    prune_stale_sessions,
    read_session,
)
from src.mcp.augur_framework.tools.domain.discovery import read_signals


class TestIDESessionLifecycle:
    """End-to-end lifecycle tests for IDE/MCP agent sessions."""

    def test_mcp_session_create_and_read(self, tmp_path):
        """MCP connect creates a session file that can be read back."""
        session_id = "mcp-12345"
        data = create_session(
            tmp_path,
            session_id=session_id,
            source="mcp",
        )
        assert data["session_id"] == session_id
        assert data["source"] == "mcp"

        stored = read_session(tmp_path, session_id)
        assert stored is not None
        assert stored["session_id"] == session_id
        assert stored["source"] == "mcp"
        assert "started_at" in stored
        assert "last_activity" in stored

    def test_mcp_session_delete_on_disconnect(self, tmp_path):
        """MCP disconnect (atexit) deletes the session file."""
        session_id = "mcp-12345"
        create_session(tmp_path, session_id=session_id, source="mcp")
        assert (tmp_path / f"{session_id}.json").exists()

        # Simulate atexit cleanup (same pattern as server.py line 869)
        delete_session(tmp_path, session_id)
        assert not (tmp_path / f"{session_id}.json").exists()

        # read_session returns None after deletion
        assert read_session(tmp_path, session_id) is None

    def test_cli_session_lifecycle(self, tmp_path):
        """CLI session: created at discover, deleted via atexit."""
        session_id = "cli-99999"
        create_session(tmp_path, session_id=session_id, source="cli")
        assert (tmp_path / f"{session_id}.json").exists()

        stored = read_session(tmp_path, session_id)
        assert stored["source"] == "cli"

        delete_session(tmp_path, session_id)
        assert not (tmp_path / f"{session_id}.json").exists()

    def test_dashboard_session_lifecycle(self, tmp_path):
        """Dashboard session: created at page load, cleaned via sendBeacon."""
        session_id = "dashboard-1709901234567"
        create_session(
            tmp_path,
            session_id=session_id,
            source="dashboard",
            hub="career",
            skill="career",
        )
        assert (tmp_path / f"{session_id}.json").exists()

        stored = read_session(tmp_path, session_id)
        assert stored["source"] == "dashboard"
        assert stored["hub"] == "career"
        assert stored["skill"] == "career"

        delete_session(tmp_path, session_id)
        assert not (tmp_path / f"{session_id}.json").exists()


class TestParallelSessionIsolation:
    """Verify parallel sessions don't contaminate each other (ADR-254 §1.2)."""

    def test_parallel_sessions_independent(self, tmp_path):
        """Two sessions with different hubs don't interfere."""
        create_session(
            tmp_path,
            session_id="mcp-100",
            source="mcp",
            hub="career",
        )
        create_session(
            tmp_path,
            session_id="mcp-200",
            source="mcp",
            hub="finance",
        )

        s1 = read_session(tmp_path, "mcp-100")
        s2 = read_session(tmp_path, "mcp-200")

        assert s1["hub"] == "career"
        assert s2["hub"] == "finance"

        # Delete one, other survives
        delete_session(tmp_path, "mcp-100")
        assert read_session(tmp_path, "mcp-100") is None
        assert read_session(tmp_path, "mcp-200") is not None

    def test_discovery_reads_correct_session(self, tmp_path):
        """read_signals with session_id reads that session's focus state."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Write per-session focus files (simulating what the API route does)
        career_focus = {"hub": "career", "skill": "career", "session_id": "dash-1"}
        (sessions_dir / "dash-1.json").write_text(json.dumps(career_focus))

        finance_focus = {"hub": "finance", "skill": "finance", "session_id": "dash-2"}
        (sessions_dir / "dash-2.json").write_text(json.dumps(finance_focus))

        # Global fallback
        (tmp_path / "focus_state.json").write_text(json.dumps({"hub": "ai", "source": "global"}))

        # Each session reads its own state
        signals_1 = read_signals(tmp_path, session_id="dash-1")
        assert signals_1["focus_state"]["hub"] == "career"

        signals_2 = read_signals(tmp_path, session_id="dash-2")
        assert signals_2["focus_state"]["hub"] == "finance"

        # No session_id falls back to global
        signals_global = read_signals(tmp_path)
        assert signals_global["focus_state"]["hub"] == "ai"


class TestSessionPruning:
    """Safety net: stale session pruning (ADR-254 §1.2)."""

    def test_prune_removes_stale_sessions(self, tmp_path):
        """Nightly daemon prunes sessions older than 1 hour."""
        import os
        import time

        create_session(tmp_path, "stale-1", "mcp")
        create_session(tmp_path, "stale-2", "cli")
        create_session(tmp_path, "fresh", "mcp")

        # Backdate stale sessions
        old_time = time.time() - 7200  # 2 hours ago
        for name in ["stale-1", "stale-2"]:
            path = tmp_path / f"{name}.json"
            os.utime(path, (old_time, old_time))

        pruned = prune_stale_sessions(tmp_path, max_age_seconds=3600)
        assert pruned == 2
        assert not (tmp_path / "stale-1.json").exists()
        assert not (tmp_path / "stale-2.json").exists()
        assert (tmp_path / "fresh.json").exists()

    def test_prune_empty_dir_returns_zero(self, tmp_path):
        """Pruning empty directory returns 0."""
        assert prune_stale_sessions(tmp_path) == 0

    def test_prune_nonexistent_dir_returns_zero(self, tmp_path):
        """Pruning non-existent directory returns 0."""
        assert prune_stale_sessions(tmp_path / "nope") == 0


class TestAtexitRegistration:
    """Verify atexit pattern matches server.py usage."""

    def test_atexit_cleanup_pattern(self, tmp_path):
        """The atexit lambda pattern from server.py correctly cleans up."""
        session_id = "mcp-atexit-test"
        create_session(tmp_path, session_id=session_id, source="mcp")
        assert (tmp_path / f"{session_id}.json").exists()

        # Simulate the atexit lambda pattern from server.py:
        #   atexit.register(lambda: delete_session(sessions_dir, session_id))
        cleanup = lambda: delete_session(tmp_path, session_id)  # noqa: E731
        cleanup()

        assert not (tmp_path / f"{session_id}.json").exists()
