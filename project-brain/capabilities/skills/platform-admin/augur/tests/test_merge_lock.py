"""Tests for merge_lock.py — dev-merge lock manager."""
from __future__ import annotations

import json
import os
import importlib.util
import sys
from argparse import Namespace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "merge_lock.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_lock(lock_path: Path, data: dict) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(data, indent=2) + "\n")


def _read_lock(lock_path: Path) -> dict | None:
    if not lock_path.exists():
        return None
    return json.loads(lock_path.read_text())


# ---------------------------------------------------------------------------
# Import helpers — we patch _get_lock_path to use tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture()
def lock_mod():
    """Import the module under test."""
    module_name = "platform_admin_merge_lock_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def lock_path(tmp_path):
    """Return a temporary lock path and ensure parent exists."""
    lp = tmp_path / "locks" / "dev-merge.lock"
    lp.parent.mkdir(parents=True, exist_ok=True)
    return lp


# ---------------------------------------------------------------------------
# _read_lock
# ---------------------------------------------------------------------------


class TestReadLock:
    def test_returns_none_when_no_file(self, lock_mod, tmp_path):
        result = lock_mod._read_lock(tmp_path / "nonexistent.lock")
        assert result is None

    def test_returns_none_for_invalid_json(self, lock_mod, lock_path):
        lock_path.write_text("not json")
        result = lock_mod._read_lock(lock_path)
        assert result is None

    def test_returns_none_when_tool_missing(self, lock_mod, lock_path):
        lock_path.write_text(json.dumps({"pid": 1}))
        result = lock_mod._read_lock(lock_path)
        assert result is None

    def test_returns_data_when_valid(self, lock_mod, lock_path):
        data = {"tool": "codex", "pid": 123}
        lock_path.write_text(json.dumps(data))
        result = lock_mod._read_lock(lock_path)
        assert result["tool"] == "codex"


# ---------------------------------------------------------------------------
# _is_stale
# ---------------------------------------------------------------------------


class TestIsStale:
    def test_stale_when_no_acquired_at(self, lock_mod):
        assert lock_mod._is_stale({"tool": "codex"}) is True

    def test_not_stale_when_recent(self, lock_mod):
        recent = datetime.now(timezone.utc).isoformat()
        assert lock_mod._is_stale({"tool": "codex", "acquired_at": recent}) is False

    def test_stale_when_old(self, lock_mod):
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert lock_mod._is_stale({"tool": "codex", "acquired_at": old}) is True

    def test_stale_when_bad_timestamp(self, lock_mod):
        assert lock_mod._is_stale({"tool": "codex", "acquired_at": "garbage"}) is True


# ---------------------------------------------------------------------------
# _owner_matches
# ---------------------------------------------------------------------------


class TestOwnerMatches:
    def test_empty_existing_always_matches(self, lock_mod):
        assert lock_mod._owner_matches("", "anything") is True

    def test_same_owner_matches(self, lock_mod):
        assert lock_mod._owner_matches("abc123", "abc123") is True

    def test_different_owner_does_not_match(self, lock_mod):
        assert lock_mod._owner_matches("abc", "xyz") is False

    def test_empty_provided_does_not_match_nonempty_existing(self, lock_mod):
        assert lock_mod._owner_matches("abc", "") is False


# ---------------------------------------------------------------------------
# _detect_owner
# ---------------------------------------------------------------------------


class TestDetectOwner:
    def test_returns_empty_when_no_env(self, lock_mod):
        with patch.dict(os.environ, {}, clear=True):
            result = lock_mod._detect_owner()
            assert result == ""

    def test_returns_env_value(self, lock_mod):
        with patch.dict(os.environ, {"DEV_MERGE_OWNER": "my-session"}, clear=False):
            result = lock_mod._detect_owner()
            assert result == "my-session"


class TestAcquireRelease:
    def test_acquire_and_release_round_trip(self, lock_mod, lock_path, monkeypatch, capsys):
        monkeypatch.setattr(lock_mod, "_get_lock_path", lambda: lock_path)

        acquire = lock_mod.cmd_acquire(
            Namespace(tool="codex", owner="owner-1", branch="main", wait=0)
        )
        assert acquire == 0
        assert _read_lock(lock_path)["owner"] == "owner-1"
        assert "ACQUIRED:" in capsys.readouterr().out

        release = lock_mod.cmd_release(Namespace(tool="codex", owner="owner-1"))
        assert release == 0
        assert not lock_path.exists()
        assert "RELEASED:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Heartbeat: last_updated_at is the source of truth for idle/staleness
# ---------------------------------------------------------------------------


class TestHeartbeatField:
    def test_acquire_sets_last_updated_at_equal_to_acquired_at(
        self, lock_mod, lock_path, monkeypatch
    ):
        monkeypatch.setattr(lock_mod, "_get_lock_path", lambda: lock_path)
        lock_mod.cmd_acquire(Namespace(tool="codex", owner="owner-1", branch="main", wait=0))
        data = _read_lock(lock_path)
        assert "last_updated_at" in data
        assert data["last_updated_at"] == data["acquired_at"]

    def test_update_refreshes_last_updated_at_only(
        self, lock_mod, lock_path, monkeypatch
    ):
        monkeypatch.setattr(lock_mod, "_get_lock_path", lambda: lock_path)
        # Plant a lock whose acquired_at is in the past so we can prove the
        # heartbeat field moved while acquired_at stayed put.
        old_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        _write_lock(
            lock_path,
            {
                "tool": "codex",
                "pid": 1,
                "owner": "owner-1",
                "branch": "main",
                "step": "starting",
                "acquired_at": old_iso,
                "last_updated_at": old_iso,
            },
        )
        assert (
            lock_mod.cmd_update(
                Namespace(tool="codex", owner="owner-1", step="step-2")
            )
            == 0
        )
        data = _read_lock(lock_path)
        assert data["acquired_at"] == old_iso  # untouched
        assert data["last_updated_at"] != old_iso  # bumped
        # Bumped to roughly now — assert delta is small.
        bumped = datetime.fromisoformat(data["last_updated_at"])
        assert (datetime.now(timezone.utc) - bumped).total_seconds() < 5


class TestIsStaleHeartbeat:
    def test_uses_last_updated_at_when_present(self, lock_mod):
        """Lock acquired long ago but heartbeated recently is NOT stale."""
        old = (datetime.now(timezone.utc) - timedelta(hours=11)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        assert lock_mod._is_stale(
            {"tool": "codex", "acquired_at": old, "last_updated_at": recent}
        ) is False

    def test_stale_when_heartbeat_old_even_if_acquired_recent(self, lock_mod):
        """Heartbeat is authoritative — a fresh acquired_at can't mask an idle holder.

        (This shape shouldn't occur in practice — acquire always sets the two
        fields equal — but it pins the contract: heartbeat is what we check.)
        """
        recent = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert lock_mod._is_stale(
            {"tool": "codex", "acquired_at": recent, "last_updated_at": old}
        ) is True

    def test_falls_back_to_acquired_at_for_legacy_lock(self, lock_mod):
        """Locks written by older versions have no last_updated_at — still work."""
        recent = datetime.now(timezone.utc).isoformat()
        assert lock_mod._is_stale({"tool": "codex", "acquired_at": recent}) is False
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert lock_mod._is_stale({"tool": "codex", "acquired_at": old}) is True


# ---------------------------------------------------------------------------
# Display: acquired vs idle make a stuck lock distinguishable from a busy one
# ---------------------------------------------------------------------------


class TestFormatLockInfo:
    def test_shows_both_acquired_and_idle_when_heartbeat_present(self, lock_mod):
        old = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        info = lock_mod._format_lock_info(
            {
                "tool": "claude-code",
                "owner": "abc123",
                "pid": 42,
                "branch": "main",
                "step": "merging",
                "acquired_at": old,
                "last_updated_at": recent,
            }
        )
        assert "acquired=15m ago" in info
        assert "idle=0s" in info

    def test_omits_idle_for_legacy_lock_without_heartbeat(self, lock_mod):
        """Back-compat: no last_updated_at → no `idle=` field."""
        recent = datetime.now(timezone.utc).isoformat()
        info = lock_mod._format_lock_info(
            {"tool": "claude-code", "pid": 1, "branch": "main", "acquired_at": recent}
        )
        assert "acquired=0s ago" in info
        assert "idle=" not in info
