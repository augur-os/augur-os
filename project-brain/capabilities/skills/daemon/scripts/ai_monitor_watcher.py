"""AI Monitor Watcher — watches daemon stderr logs for actionable errors.

CLI tool called by AI clients via Bash. Uses watchdog (with polling fallback)
to observe daemon stderr logs and self-heal events. Applies filtering via
self_heal.patterns and blocks until an actionable error is detected, then
outputs a compact JSON event and exits.

Usage:
    python ai_monitor_watcher.py --wait-for-event [--timeout SECONDS] [--debounce SECONDS]
"""
# TODO_CLEANUP: This file is 830 lines — consider splitting into smaller modules

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).resolve().parent

# Allow importing self_heal.patterns
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)


# ── Lazy imports ──────────────────────────────────────────────────────────────


def _get_patterns():
    """Lazy import of PATTERNS to avoid import errors in test isolation."""
    from self_heal.patterns import PATTERNS
    return PATTERNS


def _get_default_paths():
    """Lazy import of path helpers — only needed for CLI main()."""
    from src.config.paths import get_logs_dir, get_runtime_dir, get_vault_dir
    return get_logs_dir, get_runtime_dir, get_vault_dir


# ── Feedback loop prevention ─────────────────────────────────────────────────

_SELF_LOG_NAME = "ai_monitor.stderr.log"

# Generic error indicators used when no pattern matches
_GENERIC_ERROR_RE = re.compile(
    r"\bERROR\b|\bCRITICAL\b|Traceback \(most recent call last\)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# WATERMARKS
# ═══════════════════════════════════════════════════════════════════════════════

_WATERMARK_FILENAME = "ai_monitor_watermarks.json"


def _load_watermarks(state_dir: Path) -> dict[str, int]:
    """Read byte-offset watermarks from state_dir."""
    wm_file = state_dir / _WATERMARK_FILENAME
    if wm_file.exists():
        try:
            return json.loads(wm_file.read_text())
        except Exception:
            return {}
    return {}


def _save_watermarks(state_dir: Path, wm: dict[str, int]) -> None:
    """Atomic write of watermarks via temp file + rename."""
    state_dir.mkdir(parents=True, exist_ok=True)
    wm_file = state_dir / _WATERMARK_FILENAME
    fd, tmp_path = tempfile.mkstemp(
        dir=str(state_dir), suffix=".tmp", prefix="wm_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(wm, f, indent=2)
        os.rename(tmp_path, str(wm_file))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# READ NEW LINES
# ═══════════════════════════════════════════════════════════════════════════════


def _read_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    """Seek to byte offset, read to end, return (lines, new_offset).

    Handles file truncation: if offset > file size, resets to 0.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return [], 0

    # File truncated or rotated — reset
    if offset > size:
        offset = 0

    # No new data
    if size == offset:
        return [], size

    try:
        with open(path, "r", errors="replace") as f:
            f.seek(offset)
            new_content = f.read()
        lines = [ln for ln in new_content.splitlines() if ln.strip()]
        return lines, size
    except Exception:
        return [], offset


# ═══════════════════════════════════════════════════════════════════════════════
# DEDUP KEY
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_dedup_key(message: str, source: str) -> str:
    """Hash-based dedup key from normalized message + source.

    Uses the same normalization as scanner.py's _generate_dedup_key so both
    components produce matching keys for the same error in the shared registry.
    """
    # Normalize volatile tokens (matches scanner.py:_normalize_message_for_dedup)
    normalized_msg = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", message)
    normalized_msg = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "UUID", normalized_msg,
    )
    normalized_msg = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "DATE", normalized_msg)
    normalized_msg = re.sub(r"\d+", "N", normalized_msg)
    normalized_msg = re.sub(r"/[^\s]+", "/PATH", normalized_msg)
    normalized_msg = re.sub(r"\s+", " ", normalized_msg).strip()
    key_input = f"{source}|{normalized_msg[:220]}"
    return hashlib.sha256(key_input.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════════
# FILTER LINES
# ═══════════════════════════════════════════════════════════════════════════════


def _filter_lines(lines: list[str], source: str) -> list[dict]:
    """Check each line against self_heal.patterns.

    A line is actionable if:
    - It matches an actionable-tier pattern, OR
    - It contains ERROR/CRITICAL/Traceback AND doesn't match any
      dismiss/transient pattern.

    Returns list of dicts: {message, source, severity, dedup_key}
    """
    try:
        patterns = _get_patterns()
    except ImportError:
        patterns = []

    results: list[dict] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched_tier = None
        matched_severity = "medium"

        # Check patterns in tier priority order: dismiss -> transient -> actionable
        for pattern in patterns:
            if pattern.regex.search(stripped):
                if pattern.tier == "dismiss":
                    matched_tier = "dismiss"
                    break
                elif pattern.tier == "transient":
                    matched_tier = "transient"
                    break
                elif pattern.tier == "actionable":
                    matched_tier = "actionable"
                    matched_severity = pattern.severity
                    break

        if matched_tier == "dismiss":
            continue
        if matched_tier == "transient":
            continue

        if matched_tier == "actionable":
            dedup_key = _generate_dedup_key(stripped, source)
            results.append({
                "message": stripped[:300],
                "source": source,
                "severity": matched_severity,
                "dedup_key": dedup_key,
            })
            continue

        # No pattern matched — check for generic error indicators
        if _GENERIC_ERROR_RE.search(stripped):
            dedup_key = _generate_dedup_key(stripped, source)
            results.append({
                "message": stripped[:300],
                "source": source,
                "severity": "medium",
                "dedup_key": dedup_key,
            })

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT EVENT
# ═══════════════════════════════════════════════════════════════════════════════


def _format_event(
    source: str,
    event_type: str,
    message: str,
    file: str,
    severity: str,
    dedup_key: str,
    **kw,
) -> str:
    """Return compact JSON string for an actionable event."""
    event = {
        "source": source,
        "type": event_type,
        "message": message,
        "file": file,
        "severity": severity,
        "dedup_key": dedup_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event.update(kw)
    return json.dumps(event, separators=(",", ":"))


# ═══════════════════════════════════════════════════════════════════════════════
# WATCHDOG HANDLER
# ═══════════════════════════════════════════════════════════════════════════════


def _is_watchable_file(path: str) -> bool:
    """Only process *.stderr.log and *.jsonl files, excluding our own log."""
    name = os.path.basename(path)
    if name == _SELF_LOG_NAME:
        return False
    return name.endswith(".stderr.log") or name.endswith(".jsonl")


def _create_handler_class():
    """Create the watchdog handler class, importing watchdog lazily."""
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    class StderrLogHandler(FileSystemEventHandler):
        """Watches stderr log files for changes, signals main thread."""

        def __init__(self, signal_event: threading.Event, debounce: float):
            super().__init__()
            self.signal_event = signal_event
            self.debounce = debounce
            self.debounce_map: dict[str, float] = {}
            self.changed_files: list[str] = []
            self.lock = threading.Lock()

        def _handle_event(self, path: str) -> None:
            if not _is_watchable_file(path):
                return
            now = time.time()
            with self.lock:
                last = self.debounce_map.get(path, 0)
                if now - last < self.debounce:
                    return
                self.debounce_map[path] = now
                self.changed_files.append(path)
            self.signal_event.set()

        def on_modified(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._handle_event(event.src_path)

        def on_created(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._handle_event(event.src_path)

        def get_changed_files(self) -> list[str]:
            """Drain the changed files list (deduplicated)."""
            with self.lock:
                files = list(dict.fromkeys(self.changed_files))
                self.changed_files.clear()
                return files

    return StderrLogHandler


# ═══════════════════════════════════════════════════════════════════════════════
# WAIT FOR EVENT (core blocking function)
# ═══════════════════════════════════════════════════════════════════════════════


def _wait_for_event_with_timeout(
    stderr_dir: Path,
    state_dir: Path,
    vault_dir: Path | None,
    timeout: float,
    debounce: float,
    registry: dict,
) -> str:
    """Block until an actionable error is detected or timeout expires.

    Sets up watchdog Observer on stderr_dir (if it exists and watchdog is
    available), falls back to polling. On file change: read new lines, filter,
    if actionable -> return formatted JSON event. If timeout -> return
    {"type": "timeout"}.

    Args:
        stderr_dir: Directory containing daemon stderr log files.
        state_dir: Directory for watermark state persistence.
        vault_dir: Vault directory (unused for now, reserved for future).
        timeout: Max seconds to wait before returning timeout event.
        debounce: Debounce interval in seconds for file change events.
        registry: Dedup registry — skip events whose dedup_key has status "fixed".

    Returns:
        Compact JSON string — either an actionable event or a timeout event.
    """
    watermarks = _load_watermarks(state_dir)
    signal_event = threading.Event()
    observer = None
    handler = None
    use_watchdog = False

    # Try to set up watchdog observer
    if stderr_dir.is_dir():
        try:
            HandlerClass = _create_handler_class()
            from watchdog.observers import Observer

            handler = HandlerClass(signal_event, debounce)
            observer = Observer()
            observer.schedule(handler, str(stderr_dir), recursive=True)
            observer.start()
            use_watchdog = True
        except ImportError:
            # Watchdog not available — fall back to polling
            pass
        except Exception:
            # Observer setup failed — fall back to polling
            pass

    deadline = time.monotonic() + timeout

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            if use_watchdog and handler is not None:
                # Wait for watchdog signal or timeout
                signal_event.wait(timeout=min(remaining, debounce * 2))
                signal_event.clear()

                changed = handler.get_changed_files()
            else:
                # Polling fallback
                time.sleep(min(remaining, debounce * 2))
                changed = []
                if stderr_dir.is_dir():
                    for entry in stderr_dir.iterdir():
                        if _is_watchable_file(str(entry)):
                            try:
                                size = entry.stat().st_size
                                prev = watermarks.get(str(entry), 0)
                                if size > prev:
                                    changed.append(str(entry))
                            except OSError:
                                pass

            # Process changed files
            for fpath_str in changed:
                fpath = Path(fpath_str)
                prev_offset = watermarks.get(fpath_str, 0)
                lines, new_offset = _read_new_lines(fpath, prev_offset)
                watermarks[fpath_str] = new_offset

                if not lines:
                    continue

                source = fpath.stem
                actionable = _filter_lines(lines, source)

                for item in actionable:
                    # Skip events already fixed in registry
                    dk = item["dedup_key"]
                    if dk in registry:
                        reg_entry = registry[dk]
                        if isinstance(reg_entry, dict) and reg_entry.get("status") == "fixed":
                            continue

                    # Save watermarks before returning
                    _save_watermarks(state_dir, watermarks)

                    return _format_event(
                        source=item["source"],
                        event_type="daemon_stderr",
                        message=item["message"],
                        file=fpath_str,
                        severity=item["severity"],
                        dedup_key=dk,
                    )

    finally:
        # Always clean up the observer
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)

    # Save watermarks on timeout too
    try:
        _save_watermarks(state_dir, watermarks)
    except Exception:
        pass

    return json.dumps({
        "type": "timeout",
        "message": f"No actionable errors detected within {timeout}s",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, separators=(",", ":"))


# ═══════════════════════════════════════════════════════════════════════════════
# LOCK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


_LOCK_WORKER_CODE = r"""
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

issue_key = sys.argv[1]
lock_file = Path(sys.argv[2])
child_pid = os.getpid()
lock_data = {
    "issue_key": issue_key,
    "pid": child_pid,
    "started": datetime.now(timezone.utc).isoformat(),
}
lock_file.parent.mkdir(parents=True, exist_ok=True)
lock_file.write_text(json.dumps(lock_data))

while True:
    try:
        signal.pause()
    except AttributeError:
        time.sleep(60)
    except Exception:
        time.sleep(60)
"""


def _acquire_lock(key: str, lock_file: Path) -> int:
    """Spawn a child process that holds the lock file open.

    The child writes {issue_key, pid, started} to lock_file and stays alive
    until killed. Returns the child PID.
    """
    python = sys.executable or "python3"
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(  # nosec B603
        [python, "-c", _LOCK_WORKER_CODE, key, str(lock_file)],
        **popen_kwargs,
    )

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Lock worker exited early for key={key}")
        try:
            data = json.loads(lock_file.read_text())
            if data.get("issue_key") == key:
                # On Windows with venv, the Popen PID might be a shim PID,
                # while the lock file contains the real python.exe PID.
                # Returning the real PID allows killing the actual worker.
                return data.get("pid")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        time.sleep(0.05)

    proc.terminate()
    raise RuntimeError(f"Lock worker failed to start within 5s for key={key}")


def _release_lock(lock_file: Path) -> None:
    """Kill the lock holder and remove the lock file."""
    if not lock_file.exists():
        return

    try:
        lock_data = json.loads(lock_file.read_text())
        pid = lock_data.get("pid")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                # Brief wait for process to exit
                for _ in range(20):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.05)
                    except (OSError, ProcessLookupError):
                        break
            except (OSError, ProcessLookupError):
                pass
    except Exception:
        pass

    try:
        lock_file.unlink(missing_ok=True)
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# RECORD FIX
# ═══════════════════════════════════════════════════════════════════════════════


def _record_fix(
    registry_path: Path,
    key: str,
    status: str,
    commit_hash: str,
) -> None:
    """Update a registry entry with the fix result (atomic write)."""
    registry: dict = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except Exception:
            pass

    entry = registry.get(key, {})
    entry["status"] = status
    entry["fix_commit"] = commit_hash
    entry["fixed_at"] = datetime.now(timezone.utc).isoformat()
    registry[key] = entry

    # Atomic write
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(registry_path.parent), suffix=".tmp", prefix="reg_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(registry, f, indent=2)
        os.replace(tmp_path, str(registry_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# VAULT CHECK
# ═══════════════════════════════════════════════════════════════════════════════

_CONFLICT_MARKER_RE = re.compile(r"^<{7} ")
_SCAN_SUBDIRS = ("data", "memory")


def _vault_check(vault_dir: Path) -> list[dict]:
    """Scan vault for git conflict markers in .md files.

    Only scans top-level data/ and memory/ subdirectories to avoid full vault
    recursion.  Returns list of issue dicts: {type, file, message}.
    """
    issues: list[dict] = []

    for subdir_name in _SCAN_SUBDIRS:
        subdir = vault_dir / subdir_name
        if not subdir.is_dir():
            continue
        for md_file in subdir.rglob("*.md"):
            try:
                text = md_file.read_text(errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _CONFLICT_MARKER_RE.match(line):
                    issues.append({
                        "type": "conflict_marker",
                        "file": str(md_file),
                        "message": f"Git conflict marker at line {lineno}",
                    })
                    break  # One report per file

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_status(state_dir: Path, runtime_dir: Path | None = None) -> str:
    """Return JSON summary of daemon and self-heal registry state.

    Args:
        state_dir: AI monitor state directory (RUNTIME_DIR / "ai_monitor").
        runtime_dir: Top-level runtime dir for canonical paths. Falls back to
                     state_dir.parent if not provided.
    """
    if runtime_dir is None:
        runtime_dir = state_dir.parent

    # Read daemon status (lives under RUNTIME_DIR/stats/)
    daemon_info: dict = {}
    daemon_status_path = runtime_dir / "stats" / "daemon_status.json"
    if daemon_status_path.exists():
        try:
            daemon_info = json.loads(daemon_status_path.read_text())
        except Exception:
            pass

    # Read self-heal registry (lives directly under RUNTIME_DIR)
    registry: dict = {}
    registry_path = runtime_dir / "self_heal_registry.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except Exception:
            pass

    counts: dict[str, int] = {}
    for entry in registry.values():
        if isinstance(entry, dict):
            s = entry.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1

    pending = counts.get("detected", 0)
    fixed = counts.get("fixed", 0)
    failed = counts.get("failed", 0)

    result = {
        "daemon": daemon_info,
        "pending_issues": pending,
        "fixed_issues": fixed,
        "failed_issues": failed,
        "registry_total": len(registry),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(result, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# BYTES COUNTER
# ═══════════════════════════════════════════════════════════════════════════════

_BYTES_COUNTER_FILENAME = "ai_monitor_bytes.json"


def _update_bytes_counter(state_dir: Path, bytes_added: int) -> None:
    """Atomically increment the bytes_outputted counter."""
    counter_file = state_dir / _BYTES_COUNTER_FILENAME
    data: dict = {}
    if counter_file.exists():
        try:
            data = json.loads(counter_file.read_text())
        except Exception:
            pass

    data["bytes_outputted"] = data.get("bytes_outputted", 0) + bytes_added
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    state_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(state_dir), suffix=".tmp", prefix="bytes_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, str(counter_file))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """CLI entry point for ai_monitor_watcher."""
    parser = argparse.ArgumentParser(
        description="Watch daemon stderr logs for actionable errors.",
    )
    parser.add_argument(
        "--wait-for-event",
        action="store_true",
        help="Block until an actionable error is detected, then output JSON and exit.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Max seconds to wait (default: 300).",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=1.0,
        help="Debounce interval in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--acquire-lock",
        action="store_true",
        help="Acquire the self-heal fix lock for the given --key.",
    )
    parser.add_argument(
        "--release-lock",
        action="store_true",
        help="Release the self-heal fix lock.",
    )
    parser.add_argument(
        "--record-fix",
        action="store_true",
        help="Record a fix result in the self-heal registry.",
    )
    parser.add_argument(
        "--vault-check",
        action="store_true",
        help="Scan vault for conflict markers and YAML issues.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Output JSON summary of daemon and self-heal registry state.",
    )
    parser.add_argument("--key", type=str, help="Issue dedup key (for --acquire-lock / --record-fix).")
    parser.add_argument("--commit", type=str, help="Commit hash (for --record-fix).")
    parser.add_argument("--fix-status", type=str, default="fixed", help="Fix status string (for --record-fix).")

    args = parser.parse_args()

    # Resolve paths
    get_logs_dir, get_runtime_dir, get_vault_dir = _get_default_paths()
    state_dir = get_runtime_dir() / "ai_monitor"
    lock_file = get_runtime_dir() / "locks" / "self_heal_fix.lock"
    registry_path = get_runtime_dir() / "self_heal_registry.json"

    if args.acquire_lock:
        if not args.key:
            parser.error("--acquire-lock requires --key")
        pid = _acquire_lock(args.key, lock_file)
        print(json.dumps({"pid": pid, "lock_file": str(lock_file)}))
        return

    if args.release_lock:
        _release_lock(lock_file)
        print(json.dumps({"released": True, "lock_file": str(lock_file)}))
        return

    if args.record_fix:
        if not args.key:
            parser.error("--record-fix requires --key")
        commit = args.commit or ""
        _record_fix(registry_path, args.key, args.fix_status, commit)
        print(json.dumps({"recorded": True, "key": args.key, "status": args.fix_status}))
        return

    if args.vault_check:
        vault_dir = get_vault_dir()
        issues = _vault_check(vault_dir)
        print(json.dumps({"issues": issues, "count": len(issues)}, indent=2))
        return

    if args.status:
        print(_get_status(state_dir, runtime_dir=get_runtime_dir()))
        return

    if not args.wait_for_event:
        parser.error("One of --wait-for-event, --acquire-lock, --release-lock, --record-fix, --vault-check, --status is required")

    stderr_dir = get_logs_dir() / "daemon" / "stderr"
    vault_dir = get_vault_dir()

    # Load existing registry for dedup
    registry: dict = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except Exception:
            pass

    result = _wait_for_event_with_timeout(
        stderr_dir=stderr_dir,
        state_dir=state_dir,
        vault_dir=vault_dir,
        timeout=args.timeout,
        debounce=args.debounce,
        registry=registry,
    )
    print(result)
    # Track bytes outputted for context pressure management
    _update_bytes_counter(state_dir, len(result))


if __name__ == "__main__":
    main()
