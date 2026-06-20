#!/usr/bin/env python3
"""RAG watcher service — near-real-time index freshness (spec 2026-06-10).

Watches brain-registry-derived roots via watchdog (FSEvents on macOS),
debounces events per category, and runs the incremental sync engine.
Owns the daily full reconcile (03:00) — the fix for the nightly
knowledge-enrichment loop that required a Codex client schedule.

Usage:
    python3 rag_watcher.py            # one catch-up sync pass, then exit
    python3 rag_watcher.py --loop     # continuous (run by unified daemon)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_brain_registry_path, get_runtime_dir  # noqa: E402
from src.lib.index.incremental import WATCH_CATEGORIES, sync_categories  # noqa: E402
from src.lib.index.watch_roots import categories_for_path, resolve_watch_roots  # noqa: E402
from src.logging import get_entity_logger  # noqa: E402

from rag_watcher_core import WatcherCore  # noqa: E402

logger = get_entity_logger("rag_watcher")

TICK_SECONDS = 1.0
HEARTBEAT_EVERY = 15.0
STATE_FILE = get_runtime_dir() / "rag_watcher_state.json"


def _sync(categories: set[str], full: bool = False) -> dict:
    cats = set(categories) if categories else set(WATCH_CATEGORIES)
    return sync_categories(cats, project_root=PROJECT_ROOT, full=full)


def _write_state(core: WatcherCore, roots_count: int) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "heartbeat_at": datetime.now(tz=timezone.utc).isoformat(),
        "roots": roots_count,
        **core.status_snapshot(),
    }
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _safe_mtime(path: Path) -> float:
    """mtime of *path*, or 0.0 if it vanished between rglob and stat."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _load_last_reconcile_date() -> str | None:
    """Last persisted reconcile date from the state file, or None.

    Seeding WatcherCore with this prevents a full reindex_all on every daemon
    restart after the reconcile hour; genuinely stale categories are still
    recovered by the startup _catch_up diff.
    """
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        value = state.get("last_reconcile_date")
        return value if isinstance(value, str) else None
    except (OSError, json.JSONDecodeError):
        return None


def _catch_up(core: WatcherCore) -> None:
    """Enqueue categories whose newest source mtime beats their checksum stamp."""
    from src.config.paths import get_rag_dir

    checksums = get_rag_dir() / "_meta" / "checksums"
    for root in resolve_watch_roots():
        stamp_file = checksums / f"{root.category}.yaml"
        indexed_at = 0.0
        if stamp_file.exists():
            indexed_at = stamp_file.stat().st_mtime
        newest = max(
            (_safe_mtime(p) for p in root.path.rglob("*") if p.is_file()),
            default=0.0,
        )
        if newest > indexed_at:
            logger.info("Catch-up: %s stale (source newer than index)", root.category)
            core.record_event(root.category)


def _build_observer(core: WatcherCore):
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    roots = resolve_watch_roots()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            for attr in ("src_path", "dest_path"):
                raw = getattr(event, attr, None)
                if not raw:
                    continue
                for category in categories_for_path(Path(raw), roots):
                    core.record_event(category)

    observer = Observer()
    handler = Handler()
    watched_dirs = {str(r.path) for r in roots}
    for directory in sorted(watched_dirs):
        observer.schedule(handler, directory, recursive=True)
    # Watch the registry file's directory so attach/detach reloads roots live.
    registry_dir = get_brain_registry_path().parent
    registry_dir.mkdir(parents=True, exist_ok=True)

    reload_flag = {"reload": False}

    class RegistryHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            if Path(getattr(event, "src_path", "")).name == get_brain_registry_path().name:
                logger.info("Brain registry changed — flagging root reload")
                reload_flag["reload"] = True

    observer.schedule(RegistryHandler(), str(registry_dir), recursive=False)
    observer.start()
    logger.info("Watching %d roots (+registry)", len(watched_dirs))
    return observer, reload_flag, len(watched_dirs)


def run_loop() -> None:
    from src.lib.brain_registry import clear_cache

    core = WatcherCore(sync_fn=_sync, clock=time.monotonic,
                       last_reconcile_date=_load_last_reconcile_date())
    observer, reload_flag, roots_count = _build_observer(core)
    _catch_up(core)
    last_heartbeat = 0.0
    while True:
        try:
            if reload_flag["reload"]:
                reload_flag["reload"] = False
                observer.stop()
                observer.join(timeout=10)
                # clear_cache: sanctioned here — registry file just changed on
                # disk; forces re-read (docstring predates daemon reload use).
                clear_cache()
                try:
                    observer, reload_flag, roots_count = _build_observer(core)
                    # Newly attached brain roots sync now, not at daily reconcile.
                    _catch_up(core)
                except Exception as build_exc:  # noqa: BLE001 — keep watcher alive
                    logger.error(
                        "Observer rebuild failed, will retry: %s", build_exc, exc_info=True
                    )
                    reload_flag["reload"] = True  # re-trigger next tick
            core.tick()
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_EVERY:
                _write_state(core, roots_count)
                last_heartbeat = now
        except Exception as exc:  # noqa: BLE001 — service must not die on one bad tick
            logger.error("Watcher tick failed: %s", exc, exc_info=True)
        time.sleep(TICK_SECONDS)


def run_once() -> None:
    # reconcile_hour=24: run-once is a catch-up pass, never a surprise full rebuild.
    core = WatcherCore(sync_fn=_sync, clock=time.monotonic,
                       debounce_seconds=0.0, reconcile_hour=24,
                       last_reconcile_date=_load_last_reconcile_date())
    roots = resolve_watch_roots()
    _catch_up(core)
    core.tick()
    _write_state(core, roots_count=len(roots))
    print(json.dumps(core.status_snapshot(), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG index file watcher")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    args = parser.parse_args()
    if args.loop:
        run_loop()
    else:
        run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
