"""Pure decision logic for the RAG watcher: debounce, coalesce, reconcile.

No watchdog, no filesystem, no sleeping — the shell (rag_watcher.py) feeds
events in and calls tick(); tests drive it with a fake clock and sync_fn.

Design note: on first launch _last_reconcile_date is None, so the watcher
runs a full reconcile if started after the reconcile hour — this doubles as
index-missing/stale-on-boot recovery. Keep this behavior.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable


class WatcherCore:
    def __init__(
        self,
        *,
        sync_fn: Callable[..., dict],
        clock: Callable[[], float],
        debounce_seconds: float = 3.0,
        reconcile_hour: int = 3,
        last_reconcile_date: str | None = None,
    ) -> None:
        self._sync_fn = sync_fn
        self._clock = clock
        self._debounce = debounce_seconds
        self._reconcile_hour = reconcile_hour
        self._lock = threading.Lock()
        self._pending: dict[str, float] = {}      # category -> last event monotonic time
        self._last_sync: dict[str, dict[str, Any]] = {}
        self._last_error: str | None = None
        self._last_reconcile_date: str | None = last_reconcile_date

    # -- event intake (called from watchdog handler thread) ------------------

    def record_event(self, category: str) -> None:
        with self._lock:
            self._pending[category] = self._clock()

    # -- main-loop tick -------------------------------------------------------

    def tick(self) -> dict | None:
        """Run due work: daily reconcile first, then debounced category sync."""
        today, hour = self._today_and_hour()
        if hour >= self._reconcile_hour and self._last_reconcile_date != today:
            result = self._run_sync(set(), full=True)
            if result is not None:
                self._last_reconcile_date = today
                return result
            # Reconcile blocked (lock held) or failed — fall through so pending
            # debounced categories are not starved; reconcile retries next tick.

        now = self._clock()
        with self._lock:
            due = {
                cat for cat, last in self._pending.items()
                if now - last >= self._debounce
            }
            for cat in due:
                del self._pending[cat]
        if not due:
            return None
        result = self._run_sync(due, full=False)
        if result is None:
            # Lock held or sync failed — requeue so nothing is dropped.
            # Backdate past the debounce window so the next tick retries
            # immediately instead of waiting another full window.
            with self._lock:
                for cat in due:
                    self._pending.setdefault(cat, now - self._debounce)
        return result

    def _run_sync(self, categories: set[str], *, full: bool) -> dict | None:
        try:
            from src.lib.index.sync_lock import SyncLockHeld
        except ImportError:
            SyncLockHeld = RuntimeError  # type: ignore[assignment]
        try:
            stats = self._sync_fn(categories, full=full)
        except SyncLockHeld:
            return None
        except Exception as exc:  # noqa: BLE001 — surfaced via status, never crash loop
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None
        self._last_error = None
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        for cat, count in (stats or {}).items():
            self._last_sync[cat] = {"count": count, "at": stamp}
        if full:
            self._last_sync["_full"] = {"count": sum((stats or {}).values()), "at": stamp}
        return stats

    # -- introspection ---------------------------------------------------------

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            pending = sorted(self._pending)
            last_sync = dict(self._last_sync)
        return {
            "pending": pending,
            "last_sync": last_sync,
            "last_error": self._last_error,
            "last_reconcile_date": self._last_reconcile_date,
        }

    # Separated so tests can monkeypatch wall-clock day/hour.
    def _today_and_hour(self) -> tuple[str, int]:
        now = datetime.now().astimezone()
        return now.strftime("%Y-%m-%d"), now.hour
