"""Tests for src/lib/index/sync_lock.py -- PID-stamped stale-safe RAG sync lock."""

from __future__ import annotations

import json

import pytest

from src.lib.index.sync_lock import SyncLockHeld, sync_lock


def test_acquire_and_release(tmp_path):
    lock_path = tmp_path / "rag_sync.lock"
    with sync_lock(lock_path):
        assert lock_path.exists()
        data = json.loads(lock_path.read_text())
        assert data["pid"] > 0
    assert not lock_path.exists()


def test_second_acquire_raises(tmp_path):
    lock_path = tmp_path / "rag_sync.lock"
    with sync_lock(lock_path):
        with pytest.raises(SyncLockHeld):
            with sync_lock(lock_path):
                pass


def test_stale_lock_is_reclaimed(tmp_path):
    lock_path = tmp_path / "rag_sync.lock"
    # PID 2**22+5 is far above macOS/Linux pid_max — guaranteed dead.
    lock_path.write_text(json.dumps({"pid": 2**22 + 5, "acquired_at": "2020-01-01T00:00:00"}))
    with sync_lock(lock_path):
        data = json.loads(lock_path.read_text())
        assert data["pid"] != 2**22 + 5
    assert not lock_path.exists()


def test_release_on_exception(tmp_path):
    lock_path = tmp_path / "rag_sync.lock"
    with pytest.raises(ValueError):
        with sync_lock(lock_path):
            raise ValueError("boom")
    assert not lock_path.exists()
