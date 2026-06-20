"""Query-time staleness gate for the RAG index (spec 2026-06-12-retrieval-freshness).

Heartbeat-gated: a live watcher (heartbeat younger than STALENESS_GATE_SECONDS)
means the index tracks the filesystem, so searches trust it. A dead or old
heartbeat triggers one inline, time-boxed incremental catch-up so queries never
silently run on a stale index. Deterministic, zero LLM calls.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.index.incremental import WATCH_CATEGORIES, sync_categories
from src.logging import get_entity_logger

logger = get_entity_logger("index_staleness")

STALENESS_GATE_SECONDS = 600
INLINE_SYNC_BUDGET_SECONDS = 5.0

# Last inline-sync attempt (time.monotonic). While the watcher stays dead, only
# the first query per gate window pays the sync; the rest get the warning only.
# Sentinel -inf == "never attempted": time.monotonic()'s origin is arbitrary
# (small on a freshly-booted machine), so a 0.0 default would make `now - 0.0 <
# GATE` spuriously true right after boot and suppress the first real sync.
_last_inline_attempt: float = float("-inf")
_attempt_lock = threading.Lock()


def _state_path() -> Path:
    return get_runtime_dir() / "rag_watcher_state.json"


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def index_staleness() -> tuple[bool, str | None]:
    """(is_stale, reason). The watcher heartbeat is the freshness signal."""
    try:
        state = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, "no watcher state file"
    heartbeat = _parse_ts(state.get("heartbeat_at"))
    if heartbeat is None:
        return True, "watcher heartbeat unreadable"
    age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    if age > STALENESS_GATE_SECONDS:
        return True, f"watcher heartbeat {age:.0f}s old"
    return False, None


def ensure_fresh_index(categories: set[str] | None = None) -> dict:
    """Freshness check + inline time-boxed catch-up. Never raises, never blocks >budget.

    Returns {"stale": bool, "synced": bool, "warning": str | None}.
    """
    stale, reason = index_staleness()
    if not stale:
        return {"stale": False, "synced": False, "warning": None}

    global _last_inline_attempt
    now = time.monotonic()
    with _attempt_lock:
        if now - _last_inline_attempt < STALENESS_GATE_SECONDS:
            return {
                "stale": True,
                "synced": False,
                "warning": (
                    f"index-staleness: {reason}; inline sync already attempted " "this window, results may be stale"
                ),
            }
        _last_inline_attempt = now

    done = threading.Event()
    outcome: dict = {}

    def _run() -> None:
        try:
            outcome["stats"] = sync_categories(
                set(categories or WATCH_CATEGORIES),
                project_root=get_project_root(),
            )
        except Exception as exc:  # noqa: BLE001 - degraded search beats no search
            outcome["error"] = str(exc)
        finally:
            done.set()

    worker = threading.Thread(target=_run, daemon=True, name="inline-rag-sync")
    worker.start()
    if not done.wait(INLINE_SYNC_BUDGET_SECONDS):
        logger.warning("inline sync exceeded %.0fs budget (%s)", INLINE_SYNC_BUDGET_SECONDS, reason)
        return {
            "stale": True,
            "synced": False,
            "warning": (
                f"index-staleness: {reason}; inline sync still running "
                f"(budget {INLINE_SYNC_BUDGET_SECONDS:.0f}s exceeded), results may be stale"
            ),
        }
    if "error" in outcome:
        logger.warning("inline sync failed: %s", outcome["error"])
        return {
            "stale": True,
            "synced": False,
            "warning": f"index-staleness: {reason}; inline sync failed: {outcome['error']}",
        }
    return {
        "stale": True,
        "synced": True,
        "warning": f"index-staleness: {reason}; recovered by inline sync",
    }
