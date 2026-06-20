#!/usr/bin/env python3
"""
Dev-merge lock manager — prevents concurrent merge operations across tools/sessions.

Lock file path:
  <state>/locks/dev-merge.lock

Using the main repo root (first `git worktree list` entry) keeps one shared lock
across all worktrees for the same repository.

Usage:
    python3 merge_lock.py acquire --tool codex [--owner session-id] [--branch main] [--wait 30]
    python3 merge_lock.py release --tool codex [--owner session-id]
    python3 merge_lock.py status
    python3 merge_lock.py update --tool codex [--owner session-id] --step "step-4: merge"
    python3 merge_lock.py break-lock
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


STALE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes

if os.name == "nt":
    import msvcrt

    LOCK_EX = 1
    LOCK_UN = 8
    LOCK_NB = 4

    def _flock(lock_fd: int, operation: int) -> None:
        """Small cross-platform fd lock wrapper for the dev-merge lock file."""
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


def _get_project_root() -> Path:
    """Walk up from script location to find repo root."""
    path = Path(__file__).resolve()
    for parent in [path, *path.parents]:
        if (parent / ".git").exists() or (parent / ".git").is_file():
            return parent
    return Path.cwd()


def _get_main_repo_root(project_root: Path) -> Path:
    """Resolve primary repo root shared by all worktrees."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "worktree", "list", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return project_root

    if proc.returncode != 0:
        return project_root

    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            candidate = Path(line.removeprefix("worktree ").strip()).resolve()
            if candidate.exists():
                return candidate
            break
    return project_root


def _get_shared_state_dir(main_repo: Path) -> Path:
    """Resolve canonical shared state directory for all worktrees."""
    try:
        if str(main_repo) not in sys.path:
            sys.path.insert(0, str(main_repo))
        from src.config.paths import get_state_dir

        return get_state_dir()
    except Exception:
        env_state = os.getenv("AUGUR_STATE")
        if env_state:
            return Path(env_state)
        return Path.home() / "Library" / "Application Support" / "Augur" / "state"


def _get_lock_path() -> Path:
    """Lock file lives in shared state so worktrees share one lock."""
    main_repo = _get_main_repo_root(_get_project_root())
    lock_dir = _get_shared_state_dir(main_repo) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "dev-merge.lock"


def _read_lock(lock_path: Path) -> dict | None:
    """Read lock file contents. Returns None if no lock or invalid."""
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text())
        if not isinstance(data, dict) or "tool" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _detect_owner() -> str:
    """Best-effort per-session owner token from known adapter env vars."""
    for key in (
        "DEV_MERGE_OWNER",
        "CODEX_THREAD_ID",
        "CLAUDE_SESSION_ID",
        "CLAUDE_THREAD_ID",
        "CURSOR_SESSION_ID",
        "WINDSURF_SESSION_ID",
        "OPENCODE_SESSION_ID",
    ):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def _owner_token_path() -> Path:
    """Sidecar file that persists the owner token across ephemeral shell calls."""
    return _get_lock_path().with_suffix(".owner")


def _owner_matches(existing_owner: str, provided_owner: str) -> bool:
    """Legacy locks without owner fall back to tool-only semantics."""
    existing = (existing_owner or "").strip()
    provided = (provided_owner or "").strip()
    if not existing:
        return True
    return bool(provided) and existing == provided


def _is_stale(lock_data: dict) -> bool:
    """Check if lock is stale by idle time since last heartbeat.

    Staleness is keyed off `last_updated_at` (refreshed by `cmd_update`), so
    long-running workflows that periodically call `update --step ...` self-
    extend the lock. Locks written by older versions without the heartbeat
    field fall back to `acquired_at` so we keep back-compat.

    PID-based staleness is intentionally NOT used: merge_lock.py runs as a
    short-lived CLI process, so os.getpid() is always dead by the time any
    subsequent check runs. Only time-based staleness is reliable.
    """
    timestamp = lock_data.get("last_updated_at") or lock_data.get("acquired_at", "")
    if not timestamp:
        return True
    try:
        ts = datetime.fromisoformat(timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
        return elapsed > STALE_TIMEOUT_SECONDS
    except (ValueError, TypeError):
        return True


def _write_lock(
    lock_path: Path,
    tool: str,
    branch: str,
    owner: str,
    step: str = "starting",
    *,
    lock_fd: int | None = None,
) -> dict:
    """Write lock file atomically."""
    now_iso = datetime.now(timezone.utc).isoformat()
    data = {
        "tool": tool,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "branch": branch,
        "step": step,
        "acquired_at": now_iso,
        "last_updated_at": now_iso,
    }
    if owner:
        data["owner"] = owner

    payload = json.dumps(data, indent=2) + "\n"
    if os.name == "nt" and lock_fd is not None:
        encoded = payload.encode()
        os.lseek(lock_fd, 0, os.SEEK_SET)
        os.ftruncate(lock_fd, 0)
        os.write(lock_fd, encoded)
        os.fsync(lock_fd)
    else:
        tmp_path = lock_path.with_suffix(".tmp")
        tmp_path.write_text(payload)
        tmp_path.replace(lock_path)
    return data


def _format_age(iso_string: str) -> str:
    """Render an ISO-8601 timestamp as relative age (`Ns ago` / `Nm ago`)."""
    if not iso_string:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
        return f"{int(elapsed)}s" if elapsed < 60 else f"{int(elapsed / 60)}m"
    except (ValueError, TypeError):
        return "unknown"


def _format_lock_info(data: dict) -> str:
    """Format lock data for display.

    `acquired=` is wall-clock since the lock was first taken; `idle=` is
    wall-clock since the last `update` heartbeat. When both diverge, the lock
    is healthy long-running; when they match and grow, the holder is stuck.
    """
    acquired_age = _format_age(data.get("acquired_at", ""))
    updated_iso = data.get("last_updated_at", "")
    idle_age = _format_age(updated_iso) if updated_iso else None

    owner = str(data.get("owner", "") or "")
    owner_short = f"{owner[:12]}…" if owner else "?"

    parts = [
        f"tool={data.get('tool', '?')}",
        f"owner={owner_short}",
        f"pid={data.get('pid', '?')}",
        f"branch={data.get('branch', '?')}",
        f"step={data.get('step', '?')}",
        f"acquired={acquired_age} ago",
    ]
    if idle_age is not None:
        parts.append(f"idle={idle_age}")
    return " ".join(parts)


def cmd_acquire(args: argparse.Namespace) -> int:
    """Acquire merge lock. Returns 0 on success, 1 on contention."""
    lock_path = _get_lock_path()
    owner = _resolve_owner(args.owner)
    # If no stable owner available, generate a new token
    if not owner or owner.isdigit():
        import uuid
        owner = uuid.uuid4().hex[:16]
    wait_timeout = getattr(args, "wait", 0) or 0
    deadline = time.monotonic() + wait_timeout

    while True:
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            _flock(lock_fd, LOCK_EX | LOCK_NB)
        except OSError:
            os.close(lock_fd)
            if time.monotonic() >= deadline:
                existing = _read_lock(lock_path)
                print(f"LOCKED: {_format_lock_info(existing)}" if existing else "LOCKED: unknown holder")
                return 1
            time.sleep(1)
            continue

        existing = _read_lock(lock_path)
        if existing and not _is_stale(existing):
            existing_owner = str(existing.get("owner", "") or "")
            if existing.get("tool") == args.tool and _owner_matches(existing_owner, owner):
                print(f"REACQUIRED: {_format_lock_info(existing)}")
                _flock(lock_fd, LOCK_UN)
                os.close(lock_fd)
                return 0

            _flock(lock_fd, LOCK_UN)
            os.close(lock_fd)
            if time.monotonic() >= deadline:
                print(f"LOCKED: {_format_lock_info(existing)}")
                return 1
            time.sleep(1)
            continue

        if existing and _is_stale(existing):
            print(f"STALE_CLEARED: {_format_lock_info(existing)}")

        data = _write_lock(lock_path, args.tool, args.branch or "?", owner=owner, lock_fd=lock_fd)
        # Persist owner token so release can find it across ephemeral shell calls
        _owner_token_path().write_text(owner)
        print(f"ACQUIRED: {_format_lock_info(data)}")
        _flock(lock_fd, LOCK_UN)
        os.close(lock_fd)
        return 0


def _resolve_owner(provided: str) -> str:
    """Resolve owner: use provided, fall back to persisted token, then env."""
    owner = (provided or _detect_owner()).strip()
    if not owner or owner.isdigit():
        # Try reading the persisted owner token from the sidecar file
        token_path = _owner_token_path()
        if token_path.exists():
            try:
                owner = token_path.read_text().strip()
            except OSError:
                pass
    return owner


def cmd_release(args: argparse.Namespace) -> int:
    """Release merge lock."""
    lock_path = _get_lock_path()
    owner = _resolve_owner(args.owner)
    existing = _read_lock(lock_path)

    if not existing:
        print("UNLOCKED: no lock held")
        return 0

    if existing.get("tool") != args.tool:
        print(f"DENIED: lock held by {existing.get('tool')}, not {args.tool}")
        return 1

    existing_owner = str(existing.get("owner", "") or "")
    if existing_owner and not _owner_matches(existing_owner, owner):
        print("DENIED: lock owner mismatch (set --owner or DEV_MERGE_OWNER/CODEX_THREAD_ID)")
        return 1

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    # Clean up owner token sidecar
    try:
        _owner_token_path().unlink()
    except FileNotFoundError:
        pass
    print(f"RELEASED: {_format_lock_info(existing)}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Check lock status."""
    lock_path = _get_lock_path()
    existing = _read_lock(lock_path)

    if not existing:
        print("UNLOCKED")
        return 0
    if _is_stale(existing):
        print(f"STALE: {_format_lock_info(existing)}")
        return 2
    print(f"LOCKED: {_format_lock_info(existing)}")
    return 1


def cmd_update(args: argparse.Namespace) -> int:
    """Update lock step for progress visibility."""
    lock_path = _get_lock_path()
    owner = _resolve_owner(args.owner)
    existing = _read_lock(lock_path)

    if not existing:
        print("UNLOCKED: nothing to update")
        return 1
    if existing.get("tool") != args.tool:
        print(f"DENIED: lock held by {existing.get('tool')}, not {args.tool}")
        return 1

    existing_owner = str(existing.get("owner", "") or "")
    if existing_owner and not _owner_matches(existing_owner, owner):
        print("DENIED: lock owner mismatch (set --owner or DEV_MERGE_OWNER/CODEX_THREAD_ID)")
        return 1

    existing["step"] = args.step
    existing["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp_path = lock_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(existing, indent=2) + "\n")
    tmp_path.replace(lock_path)
    print(f"UPDATED: step={args.step}")
    return 0


def cmd_break_lock(_args: argparse.Namespace) -> int:
    """Force-clear stale/stuck lock."""
    lock_path = _get_lock_path()
    existing = _read_lock(lock_path)

    if not existing:
        print("UNLOCKED: nothing to break")
        return 0

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    print(f"BROKEN: {_format_lock_info(existing)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev-merge lock manager")
    sub = parser.add_subparsers(dest="command", required=True)

    acq = sub.add_parser("acquire", help="Acquire merge lock")
    acq.add_argument("--tool", required=True, help="Tool name (claude-code, cursor, codex, etc.)")
    acq.add_argument("--owner", default="", help="Session owner identity (defaults from env)")
    acq.add_argument("--branch", default="?", help="Current branch name")
    acq.add_argument("--wait", type=int, default=0, help="Max seconds to wait for lock")

    rel = sub.add_parser("release", help="Release merge lock")
    rel.add_argument("--tool", required=True, help="Tool name that holds the lock")
    rel.add_argument("--owner", default="", help="Session owner identity (defaults from env)")

    sub.add_parser("status", help="Check lock status")

    upd = sub.add_parser("update", help="Update lock step")
    upd.add_argument("--tool", required=True, help="Tool name that holds the lock")
    upd.add_argument("--owner", default="", help="Session owner identity (defaults from env)")
    upd.add_argument("--step", required=True, help="Current step description")

    sub.add_parser("break-lock", help="Force-clear stale lock")

    args = parser.parse_args()
    handlers = {
        "acquire": cmd_acquire,
        "release": cmd_release,
        "status": cmd_status,
        "update": cmd_update,
        "break-lock": cmd_break_lock,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
