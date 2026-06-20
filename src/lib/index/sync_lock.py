"""PID-stamped, stale-safe file lock coordinating RAG sync runs.

Holders: rag_watcher syncs, `aug rag sync`, and the nightly reconcile.
A lock left behind by a dead process is reclaimed automatically.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class SyncLockHeld(RuntimeError):
    """Another live process holds the RAG sync lock."""


def _pid_alive(pid: int) -> bool:
    """Return True if a process with this PID currently exists."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by someone else
    except OSError:
        return False
    return True


def _try_create(lock_path: Path) -> bool:
    """Atomically create the PID-stamped lock file; False if it already exists."""
    payload = json.dumps({"pid": os.getpid(), "acquired_at": datetime.now(tz=timezone.utc).isoformat()})
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, payload.encode("utf-8"))
    except BaseException:
        os.close(fd)
        lock_path.unlink(missing_ok=True)
        raise
    os.close(fd)
    return True


@contextmanager
def sync_lock(lock_path: Path) -> Iterator[None]:
    """Acquire the sync lock or raise SyncLockHeld if a live holder exists."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if not _try_create(lock_path):
        try:
            holder = json.loads(lock_path.read_text(encoding="utf-8"))
            holder_pid = int(holder.get("pid", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            holder_pid = 0
        if _pid_alive(holder_pid):
            # Any live holder counts — including our own pid (non-reentrant),
            # so a nested or concurrent same-process acquire fails loudly.
            raise SyncLockHeld(f"RAG sync lock held by pid {holder_pid}")
        # Stale (dead holder or unreadable) — reclaim.
        lock_path.unlink(missing_ok=True)
        if not _try_create(lock_path):
            raise SyncLockHeld("RAG sync lock contended during stale reclaim")
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
