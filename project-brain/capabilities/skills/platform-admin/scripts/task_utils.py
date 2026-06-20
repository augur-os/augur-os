"""
Task utilities for nightly executor and agent task management.

Provides src/lib functions for:
- Task file parsing (frontmatter + body)
- Task availability checking
- Priority scoring
- Backlog directory resolution

Author: Augur Contributors
Version: 0.1.0
"""

from __future__ import annotations

import os
import sys
import warnings
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from bootstrap_paths import ensure_project_paths

if os.name == "nt":
    import msvcrt

    LOCK_EX = 1
    LOCK_UN = 8
    LOCK_NB = 4

    def _flock(lock_file, operation: int) -> None:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write("0")
            lock_file.flush()
        lock_file.seek(0)
        if operation & LOCK_UN:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        elif operation & LOCK_NB:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)

else:
    import fcntl

    LOCK_EX = fcntl.LOCK_EX
    LOCK_UN = fcntl.LOCK_UN
    LOCK_NB = fcntl.LOCK_NB

    def _flock(lock_file, operation: int) -> None:
        fcntl.flock(lock_file, operation)

try:
    import yaml
except ImportError:
    yaml = None


def resolve_user_data_base() -> Path:
    """Resolve the user data base directory.

    Checks environment variables first, then falls back to src/lib config.
    """
    env = os.environ.get("AUGUR_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    try:
        ensure_project_paths(__file__)
        from src.config.paths import get_runtime_dir

        return get_runtime_dir()
    except Exception:
        return Path.cwd()


def backlog_dir() -> Path:
    """Get the primary backlog directory for agent tasks."""
    return resolve_user_data_base() / "agent-tasks" / "backlog"


def all_backlog_dirs() -> list[Path]:
    """Get all backlog directories that may contain tasks.

    Returns only directories that exist on disk.
    """
    candidates = [
        backlog_dir(),
    ]
    return [d for d in candidates if d.exists()]


def read_task(filepath: Path) -> tuple[dict[str, Any], str]:
    """Read a task file and return (frontmatter, body).

    Args:
        filepath: Path to the task markdown file

    Returns:
        Tuple of (frontmatter dict, body text)
    """
    content = filepath.read_text(encoding="utf-8")

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3 and yaml:
            frontmatter = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return frontmatter, body

    return {}, content


def write_task(filepath: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write a task file with frontmatter and body.

    Args:
        filepath: Path to the task markdown file
        frontmatter: YAML frontmatter dictionary
        body: Markdown body content
    """
    if yaml:
        yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    else:
        # Fallback to simple serialization
        lines = []
        for key, value in frontmatter.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"{key}: {value}")
        yaml_content = "\n".join(lines)

    content = f"---\n{yaml_content}---\n\n{body}"
    filepath.write_text(content, encoding="utf-8")


def task_title(body: str, default: str = "Untitled") -> str:
    """Extract task title from body content.

    Looks for the first H1 header or returns the default.

    Args:
        body: Markdown body content
        default: Default title if not found

    Returns:
        Task title string
    """
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return default


def priority_score(priority: str) -> int:
    """Convert priority string to numeric score (lower = higher priority).

    Args:
        priority: Priority string (critical, high, medium, low)

    Returns:
        Integer score (0=critical, 1=high, 2=medium, 3=low, 4=unknown)
    """
    priority_map = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return priority_map.get(priority.lower().strip(), 4)


def parse_created(created_str: str) -> datetime:
    """Parse created timestamp from frontmatter.

    Args:
        created_str: ISO format date string

    Returns:
        datetime object (defaults to epoch if parsing fails)
    """
    if not created_str:
        return datetime.fromtimestamp(0)

    try:
        # Handle various ISO formats
        created_str = created_str.replace("Z", "+00:00")
        if "T" in created_str:
            return datetime.fromisoformat(created_str)
        else:
            return datetime.strptime(created_str, "%Y-%m-%d")
    except Exception:
        return datetime.fromtimestamp(0)


def is_task_available(frontmatter: dict[str, Any], stale_hours: int = 2) -> bool:
    """Check if a task is available for execution.

    A task is available if:
    - status is 'ready'
    - not claimed, or claim is stale (older than stale_hours)

    Args:
        frontmatter: Task frontmatter dictionary
        stale_hours: Hours after which a claim becomes stale

    Returns:
        True if task is available
    """
    status = str(frontmatter.get("status", "")).lower().strip()
    if status != "ready":
        return False

    execution = frontmatter.get("execution") or {}
    exec_status = str(execution.get("status", "")).lower().strip()

    # Terminal states — never pick up again
    if exec_status in ["completed", "failed"]:
        return False

    # Active states — only pick up if claim is stale
    if exec_status in ["claimed", "in-progress", "blocked"]:
        claimed_at = execution.get("claimed_at")
        if claimed_at:
            try:
                claimed_str = str(claimed_at).replace("Z", "+00:00")
                claimed_time = datetime.fromisoformat(claimed_str)
                # Make both timezone-naive for comparison
                if claimed_time.tzinfo:
                    claimed_time = claimed_time.replace(tzinfo=None)
                age_seconds = (datetime.now() - claimed_time).total_seconds()
                if age_seconds < stale_hours * 3600:
                    return False  # Still valid claim
            except Exception:
                return False

    return True


@contextmanager
def task_lock(task_path: Path, timeout: float = 10.0) -> Generator[None, None, None]:
    """Acquire an exclusive file lock for a task to prevent concurrent modification.

    Uses a .lock sidecar file with fcntl.flock(). The lock is released when the
    context manager exits, preventing race conditions between parallel executors.

    Args:
        task_path: Path to the task markdown file
        timeout: Seconds to wait for lock acquisition before raising

    Raises:
        TimeoutError: If the lock cannot be acquired within timeout
    """
    lock_path = task_path.with_suffix(".lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")  # noqa: SIM115
        import time

        deadline = time.monotonic() + timeout
        while True:
            try:
                _flock(lock_fd, LOCK_EX | LOCK_NB)
                break
            except (IOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Could not acquire lock for {task_path} within {timeout}s")
                time.sleep(0.2)
        yield
    finally:
        if lock_fd is not None:
            try:
                _flock(lock_fd, LOCK_UN)
                lock_fd.close()
            except Exception as e:
                warnings.warn(
                    f"Failed to release task lock for {task_path}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )
            try:
                lock_path.unlink(missing_ok=True)
            except Exception as e:
                warnings.warn(
                    f"Failed to remove lock file {lock_path}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )
