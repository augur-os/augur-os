"""Tests for rag_watcher_core.WatcherCore — debounce, coalesce, reconcile."""
import sys
from pathlib import Path

REPO_ROOT = next(
    (p for p in Path(__file__).resolve().parents
     if (p / "pyproject.toml").exists() and (p / ".git").exists()),
    Path(__file__).resolve().parents[-1],
)
for _path in (REPO_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SCRIPTS_DIR = REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_watcher_core import WatcherCore


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _core(clock, sync_calls, *, fail_first=0, reconcile_hour=24,
          last_reconcile_date=None):
    # reconcile_hour=24 disables the daily reconcile (hour is always <= 23),
    # so debounce tests are not polluted by a wall-clock-dependent full sync.
    state = {"fails_left": fail_first}

    def sync_fn(categories, full=False):
        if state["fails_left"] > 0:
            state["fails_left"] -= 1
            from src.lib.index.sync_lock import SyncLockHeld
            raise SyncLockHeld("busy")
        sync_calls.append((frozenset(categories), full))
        return {c: 1 for c in categories}

    return WatcherCore(sync_fn=sync_fn, clock=clock, debounce_seconds=3.0,
                       reconcile_hour=reconcile_hour,
                       last_reconcile_date=last_reconcile_date)


def test_event_not_due_before_debounce_window():
    clock, calls = FakeClock(), []
    core = _core(clock, calls)
    core.record_event("vault")
    core.tick()
    assert calls == []          # only 0s elapsed
    clock.now += 3.1
    core.tick()
    assert calls == [(frozenset({"vault"}), False)]


def test_events_coalesce_across_categories():
    clock, calls = FakeClock(), []
    core = _core(clock, calls)
    core.record_event("vault")
    core.record_event("wiki")
    core.record_event("vault")
    clock.now += 3.1
    core.tick()
    assert calls == [(frozenset({"vault", "wiki"}), False)]


def test_lock_held_keeps_events_pending():
    clock, calls = FakeClock(), []
    core = _core(clock, calls, fail_first=1)
    core.record_event("vault")
    clock.now += 3.1
    core.tick()                  # SyncLockHeld — must not drop the event
    assert calls == []
    clock.now += 1.0
    core.tick()
    assert calls == [(frozenset({"vault"}), False)]


def test_daily_reconcile_runs_once(monkeypatch):
    clock, calls = FakeClock(), []
    core = _core(clock, calls, reconcile_hour=3)
    # Force "it is past reconcile hour and not yet run today"
    core._last_reconcile_date = "2026-06-09"
    monkeypatch.setattr(core, "_today_and_hour", lambda: ("2026-06-10", 4))
    core.tick()
    assert calls == [(frozenset(), True)]
    assert core.status_snapshot()["last_reconcile_date"] == "2026-06-10"
    core.tick()                  # same day: no second reconcile
    assert calls == [(frozenset(), True)]


def test_failed_reconcile_does_not_starve_pending_categories(monkeypatch):
    clock, calls = FakeClock(), []
    core = _core(clock, calls, fail_first=1, reconcile_hour=3)
    monkeypatch.setattr(core, "_today_and_hour", lambda: ("2026-06-10", 4))
    core.record_event("vault")
    clock.now += 3.1             # vault is past the debounce window
    # The reconcile attempt consumes the one SyncLockHeld failure, then the
    # tick falls through and the debounced vault sync still runs.
    core.tick()
    assert calls == [(frozenset({"vault"}), False)]
    assert core.status_snapshot()["last_reconcile_date"] is None


def test_seeded_reconcile_date_prevents_boot_full_sync(monkeypatch):
    # Persisted date from the state file means a daemon restart after the
    # reconcile hour must NOT trigger another full reindex the same day.
    clock, calls = FakeClock(), []
    core = _core(clock, calls, reconcile_hour=3, last_reconcile_date="2026-06-10")
    monkeypatch.setattr(core, "_today_and_hour", lambda: ("2026-06-10", 4))
    core.tick()
    assert calls == []


def test_stale_seeded_reconcile_date_still_reconciles(monkeypatch):
    clock, calls = FakeClock(), []
    core = _core(clock, calls, reconcile_hour=3, last_reconcile_date="2026-06-09")
    monkeypatch.setattr(core, "_today_and_hour", lambda: ("2026-06-10", 4))
    core.tick()
    assert calls == [(frozenset(), True)]
    assert core.status_snapshot()["last_reconcile_date"] == "2026-06-10"


def test_status_snapshot_reports_last_sync():
    clock, calls = FakeClock(), []
    core = _core(clock, calls)
    core.record_event("vault")
    clock.now += 3.1
    core.tick()
    snap = core.status_snapshot()
    assert snap["last_sync"]["vault"]["count"] == 1
    assert snap["pending"] == []
