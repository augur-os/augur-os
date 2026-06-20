"""Lock file management for the dashboard monitor.

Handles build lock detection (flock-based and JSON-based), lock creation,
and stale lock cleanup.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import run  # nosec B404

from ._base import (
    LOCK_FILE_MAX_AGE_MINUTES,
    get_runtime_dir,
    logger,
)

if os.name == "nt":
    import msvcrt

    LOCK_EX = 1
    LOCK_UN = 8
    LOCK_NB = 4

    def _flock(lock_fd: int, operation: int) -> None:
        os.lseek(lock_fd, 0, os.SEEK_END)
        if os.lseek(lock_fd, 0, os.SEEK_CUR) == 0:
            os.write(lock_fd, b"0")
        os.lseek(lock_fd, 0, os.SEEK_SET)
        if operation & LOCK_UN:
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
        elif operation & LOCK_NB:
            msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
        else:
            msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)

else:
    import fcntl

    LOCK_EX = fcntl.LOCK_EX
    LOCK_UN = fcntl.LOCK_UN
    LOCK_NB = fcntl.LOCK_NB

    def _flock(lock_fd: int, operation: int) -> None:
        fcntl.flock(lock_fd, operation)


def get_locks_dir() -> Path:
    """Get the locks directory."""
    locks_dir = get_runtime_dir() / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir


def is_build_process_running() -> bool:
    """Detect active Next.js build processes via process table.

    This is the primary guard against interfering with builds. Unlike lock
    files, process detection cannot go stale -- if the process is alive, the
    build is running.

    IMPORTANT: The pattern must NOT match .next/dev/build/ worker paths
    (e.g. postcss.js) -- those are normal dev-server subprocesses, not builds.
    We check the full command line for 'next build' as a command invocation.
    """
    try:
        result = run(  # nosec B603 B607
            ["pgrep", "-fl", "next"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            build_pids = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) == 2:
                    pid, cmd = parts
                    if "next build" in cmd and ".next/" not in cmd:
                        build_pids.append(pid)
            if build_pids:
                logger.info(f"Active build process detected (PIDs: {build_pids})")
                return True
    except Exception as e:
        logger.debug(f"Build process check failed: {e}")

    return False


def is_build_lock_held() -> bool:
    """Check if another process holds the build flock.

    Uses non-blocking flock probe -- if we can acquire the lock, nobody
    else has it (we immediately release). If we can't, someone holds it.
    Unlike JSON lock files, flock is kernel-managed and never stale.
    """
    lock_file = get_locks_dir() / "dashboard_build.flock"
    if not lock_file.exists():
        return False
    try:
        fd = os.open(str(lock_file), os.O_RDWR)
        try:
            _flock(fd, LOCK_EX | LOCK_NB)
            _flock(fd, LOCK_UN)
            return False
        except (IOError, OSError):
            return True
        finally:
            os.close(fd)
    except FileNotFoundError:
        return False


def get_build_lock_info() -> dict | None:
    """Read build lock metadata (who holds it, since when)."""
    meta_file = get_locks_dir() / "dashboard_build.flock.meta"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text())
        except Exception:
            return None
    return None


def is_rebuild_in_progress() -> bool:
    """Check if a rebuild/reload is intentionally in progress.

    Two-layer detection:
    1. Process detection (primary) -- checks for live `next build` processes
    2. Lock files (secondary) -- explicit locks from reload/recovery operations
    """
    # Layer 0: Build flock -- kernel-managed, never stale
    if is_build_lock_held():
        logger.info("Build flock held by another process, skipping recovery")
        return True

    # Layer 1: Process detection -- no lock file needed
    if is_build_process_running():
        return True

    # Layer 2: Lock files -- for reload/recovery coordination
    locks_dir = get_locks_dir()

    lock_files = [
        locks_dir / "dashboard_rebuild.lock",
        locks_dir / "dashboard_reload.lock",
    ]

    for lock_file in lock_files:
        if lock_file.exists():
            try:
                lock_data = json.loads(lock_file.read_text())
                started = datetime.fromisoformat(lock_data.get("started", ""))
                age = datetime.now() - started

                if age < timedelta(minutes=LOCK_FILE_MAX_AGE_MINUTES):
                    logger.info(
                        f"Rebuild lock active: {lock_file.name} (age: {age})"
                    )
                    return True
                else:
                    logger.warning(f"Removing stale lock: {lock_file.name}")
                    lock_file.unlink()
            except Exception as e:
                logger.warning(f"Invalid lock file {lock_file}: {e}")
                lock_file.unlink(missing_ok=True)

    return False


def create_lock(lock_type: str, reason: str = "auto") -> Path:
    """Create a lock file for an operation."""
    locks_dir = get_locks_dir()
    lock_file = locks_dir / f"dashboard_{lock_type}.lock"

    lock_data = {
        "started": datetime.now().isoformat(),
        "reason": reason,
        "pid": os.getpid(),
    }

    lock_file.write_text(json.dumps(lock_data, indent=2))
    return lock_file


def remove_lock(lock_type: str) -> None:
    """Remove a lock file."""
    locks_dir = get_locks_dir()
    lock_file = locks_dir / f"dashboard_{lock_type}.lock"
    lock_file.unlink(missing_ok=True)
