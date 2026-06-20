"""Staleness gate tests (spec 2026-06-12-retrieval-freshness)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone


def _write_state(path, heartbeat_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"heartbeat_at": heartbeat_at}), encoding="utf-8")


def test_fresh_heartbeat_skips_sync(tmp_path, monkeypatch) -> None:
    from src.lib.index import staleness

    state = tmp_path / "rag_watcher_state.json"
    _write_state(state, datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: state)
    called = []
    monkeypatch.setattr(staleness, "sync_categories", lambda *a, **k: called.append(1))

    result = staleness.ensure_fresh_index()
    assert result == {"stale": False, "synced": False, "warning": None}
    assert not called


def test_dead_heartbeat_triggers_inline_sync(tmp_path, monkeypatch) -> None:
    from src.lib.index import staleness

    state = tmp_path / "rag_watcher_state.json"
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_state(state, old)
    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: state)
    called = []
    monkeypatch.setattr(staleness, "sync_categories", lambda *a, **k: called.append(1) or {"synced": 1})

    result = staleness.ensure_fresh_index()
    assert result["stale"] is True
    assert result["synced"] is True
    assert "recovered by inline sync" in result["warning"]
    assert called


def test_missing_state_file_is_stale(tmp_path, monkeypatch) -> None:
    from src.lib.index import staleness

    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(staleness, "sync_categories", lambda *a, **k: {})
    result = staleness.ensure_fresh_index()
    assert result["stale"] is True


def test_sync_failure_returns_warning_not_exception(tmp_path, monkeypatch) -> None:
    from src.lib.index import staleness

    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: tmp_path / "missing.json")

    def boom(*a, **k):
        raise RuntimeError("index locked")

    monkeypatch.setattr(staleness, "sync_categories", boom)
    result = staleness.ensure_fresh_index()
    assert result["synced"] is False
    assert "index locked" in result["warning"]


def test_inline_sync_attempted_once_per_gate_window(tmp_path, monkeypatch) -> None:
    """While the watcher stays dead, only the first query pays the inline sync."""
    from src.lib.index import staleness

    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: tmp_path / "missing.json")
    called = []
    monkeypatch.setattr(staleness, "sync_categories", lambda *a, **k: called.append(1) or {})

    first = staleness.ensure_fresh_index()
    second = staleness.ensure_fresh_index()
    assert len(called) == 1
    assert first["synced"] is True
    assert second["synced"] is False
    assert "inline sync already attempted" in second["warning"]


def test_sync_overrun_returns_stale_warning(tmp_path, monkeypatch) -> None:
    from src.lib.index import staleness

    monkeypatch.setattr(staleness, "_last_inline_attempt", float("-inf"))
    monkeypatch.setattr(staleness, "_state_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(staleness, "INLINE_SYNC_BUDGET_SECONDS", 0.05)

    def slow(*a, **k):
        time.sleep(0.5)
        return {}

    monkeypatch.setattr(staleness, "sync_categories", slow)
    result = staleness.ensure_fresh_index()
    assert result["synced"] is False
    assert "still running" in result["warning"]
