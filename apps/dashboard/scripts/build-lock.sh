#!/usr/bin/env python3
"""Build lock wrapper — ensures only one build/dev process runs at a time.

Uses fcntl.flock() for kernel-managed exclusive locking (works on macOS and Linux).
Lock auto-releases on process death — no stale locks possible.

Usage: ./scripts/build-lock.sh <command> [args...]
Example: ./scripts/build-lock.sh pnpm exec next build
         ./scripts/build-lock.sh pnpm run build
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _same_path(left: Path, right: Path) -> bool:
    left_resolved = str(left.resolve())
    right_resolved = str(right.resolve())
    if os.name == "nt":
        return left_resolved.lower() == right_resolved.lower()
    return left_resolved == right_resolved


def _preferred_project_python(project_root: Path) -> Path | None:
    candidates = []
    explicit = os.environ.get("AUGUR_PYTHON")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            project_root / ".venv" / "bin" / "python3",
            project_root / ".venv" / "bin" / "python",
        ]
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _ensure_project_python(project_root: Path) -> None:
    preferred = _preferred_project_python(project_root)
    if not preferred:
        return
    try:
        current = Path(sys.executable)
        if _same_path(current, preferred):
            return
    except OSError:
        pass
    os.execv(str(preferred), [str(preferred), str(Path(__file__).resolve()), *sys.argv[1:]])


def _worktree_marker_says_worktree(root: Path) -> bool:
    marker = root / ".augur-worktree.yaml"
    if not marker.exists():
        return False
    try:
        for raw_line in marker.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip().lower()
            if line == "worktree: true":
                return True
    except OSError:
        return False
    return False


def _is_clearly_main_checkout(root: Path) -> bool:
    if _worktree_marker_says_worktree(root):
        return False
    dot_git = root / ".git"
    if dot_git.is_dir():
        return True
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = root / common_dir
    return _same_path(common_dir, dot_git)


def _lifecycle_action_for(previous_state) -> str:
    if previous_state and previous_state.get("state") == "healthy":
        return "rebuild"
    return "start"


def _restore_lifecycle_state(
    dashboard_lifecycle,
    previous_state,
    instance_id: str,
    *,
    succeeded: bool,
) -> None:
    dashboard_lifecycle.release_build_lock_state(
        previous_state,
        succeeded=succeeded,
        instance_id=instance_id,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)

    if len(sys.argv) < 2:
        print("Usage: build-lock.sh <command> [args...]", file=sys.stderr)
        return 1

    # Resolve lock directory
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    _ensure_project_python(project_root)
    root_dir = Path(os.environ.get("AUGUR_ROOT", str(project_root)))
    try:
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        from src.config.paths import get_runtime_dir
        from src.lib.dashboard_instance import resolve_dashboard_instance

        runtime_dir = get_runtime_dir()
        instance = resolve_dashboard_instance(root_dir, runtime_dir=runtime_dir)
        lock_dir = instance.build_lock_dir
        instance_id = instance.instance_id
    except Exception as exc:
        if not _is_clearly_main_checkout(root_dir):
            print(f"ERROR: Unable to resolve dashboard instance for build lock: {exc}", file=sys.stderr)
            print("Refusing to use main dashboard build lock fallback outside the main checkout.", file=sys.stderr)
            return 1
        state_dir = (
            os.environ.get("AUGUR_STATE")
            or os.environ.get("AUGUR_RUNTIME")
            or (
                str(Path.home() / "Library" / "Application Support" / "Augur" / "state")
                if sys.platform == "darwin"
                else str(Path.home() / ".local" / "state" / "augur")
            )
        )
        lock_dir = Path(state_dir) / "locks" / "dashboard" / "main"
        instance_id = "main"
    lock_dir.mkdir(parents=True, exist_ok=True)

    lock_file = lock_dir / "dashboard_build.flock"
    meta_file = lock_dir / "dashboard_build.flock.meta"
    timeout = int(os.environ.get("BUILD_LOCK_TIMEOUT", "300"))
    command = sys.argv[1:]
    dashboard_lifecycle_module = None
    previous_lifecycle_state = None

    # Gate check: request permission from dashboard lifecycle before acquiring lock.
    # If the lifecycle module denies the action (e.g., crash-loop protection),
    # exit early so we never acquire flock on a denied build.
    # A healthy dashboard must use "rebuild"; "start" is correctly denied as a
    # duplicate start. The wrapper restores build_lock ownership on exit.
    try:
        sys.path.insert(0, str(project_root / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"))
        import dashboard_lifecycle
        dashboard_lifecycle_module = dashboard_lifecycle
        previous_lifecycle_state = dashboard_lifecycle.get_state(instance_id=instance_id)
        lifecycle_action = _lifecycle_action_for(previous_lifecycle_state)
        gate = dashboard_lifecycle.request_action(
            "build_lock",
            lifecycle_action,
            f"build-lock.sh: {' '.join(sys.argv[1:])}",
            instance_id=instance_id,
        )
        if gate["decision"] == "denied":
            print(f"Lifecycle gate denied: {gate['reason']}", file=sys.stderr)
            return 1
    except ImportError:
        pass  # Lifecycle module not available, proceed without gate

    print(f"Acquiring build lock (timeout: {timeout}s)...")

    # Open the lock file
    fd = os.open(str(lock_file), os.O_WRONLY | os.O_CREAT)

    # Try non-blocking first
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        # Lock is held — wait with timeout via SIGALRM
        print("Lock is held by another process, waiting...")
        if meta_file.exists():
            try:
                info = json.loads(meta_file.read_text())
                print(f"  Lock holder: PID {info.get('pid')}, started {info.get('started')}")
                print(f"  Command: {info.get('command')}")
            except Exception:
                pass

        timed_out = False

        def alarm_handler(signum, frame):
            nonlocal timed_out
            timed_out = True
            raise OSError("Lock timeout")

        old_handler = signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(timeout)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)  # blocking wait
            signal.alarm(0)  # cancel alarm
        except OSError:
            if timed_out:
                print(f"ERROR: Could not acquire build lock after {timeout}s.", file=sys.stderr)
                print("Another build is still running.", file=sys.stderr)
                os.close(fd)
                return 1
            raise
        finally:
            signal.signal(signal.SIGALRM, old_handler)

    print(f"Build lock acquired (PID: {os.getpid()})")

    # Write metadata for observability
    meta_data = {
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(command),
    }
    meta_file.write_text(json.dumps(meta_data))

    # Run the command as a child process (lock stays held by this process)
    exit_code = 1
    try:
        child_env = os.environ.copy()
        child_env["AUGUR_BUILD_LOCK_HELD"] = "1"
        result = subprocess.run(command, env=child_env)  # nosec B603
        exit_code = result.returncode
        return exit_code
    finally:
        if dashboard_lifecycle_module is not None:
            try:
                _restore_lifecycle_state(
                    dashboard_lifecycle_module,
                    previous_lifecycle_state,
                    instance_id,
                    succeeded=exit_code == 0,
                )
            except Exception as exc:
                print(f"WARNING: Unable to restore dashboard lifecycle state: {exc}", file=sys.stderr)
        # Clean up metadata; lock releases when fd closes (process exits)
        meta_file.unlink(missing_ok=True)
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
