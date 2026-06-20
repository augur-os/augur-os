"""
Self-Heal Event Emitter (ADR-084).

Zero-dependency structured event emitter for the fail-fast self-heal pattern.
Writes JSONL events to the persistent state directory for the daemon to pick up.

This function MUST NEVER raise. It is called from error paths.
Path resolution should still follow src.config.paths.
"""

import json
import os
import sys
import socket
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_state_dir

# Valid categories and severities
VALID_CATEGORIES = frozenset(
    {
        "import_failure",
        "path_missing",
        "config_missing",
        "mcp_failure",
        "service_fallback",
    }
)

VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low"})

# Retention: only keep events from the last 30 minutes
RETENTION_SECONDS = 1800
# Rotate at most once per 5 minutes to avoid I/O churn
_last_rotation_check: float = 0.0


def _get_event_file() -> Path | None:
    """Get the path to self_heal_events.jsonl, creating dirs if needed."""
    try:
        event_file = get_state_dir() / "self_heal_events.jsonl"
        event_file.parent.mkdir(parents=True, exist_ok=True)
        return event_file
    except Exception:
        return None


def rotate_events(event_file: Path | None = None) -> None:
    """Remove events older than RETENTION_SECONDS (30 min).

    Called automatically by emit_heal_event at most once per 5 minutes.
    Can also be called directly for manual cleanup.
    """
    global _last_rotation_check
    try:
        if event_file is None:
            event_file = _get_event_file()
        if event_file is None or not event_file.exists():
            return

        import time

        now = time.time()
        # Throttle: skip if checked recently
        if now - _last_rotation_check < 300:
            return
        _last_rotation_check = now

        cutoff = datetime.now(timezone.utc).timestamp() - RETENTION_SECONDS
        kept: list[str] = []
        with open(event_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    ts_str = ev.get("timestamp", "")
                    # Parse ISO timestamp
                    if ts_str.endswith("Z"):
                        ts_str = ts_str[:-1] + "+00:00"
                    ev_time = datetime.fromisoformat(ts_str).timestamp()
                    if ev_time >= cutoff:
                        kept.append(line)
                except (json.JSONDecodeError, ValueError, TypeError):
                    # Keep unparseable lines to avoid data loss
                    kept.append(line)

        # Atomic rewrite — os.replace, not os.rename: on Windows os.rename
        # raises FileExistsError when dst exists (silently swallowed by the
        # surrounding except, so rotation never actually happened here).
        tmp = event_file.with_suffix(".rotation_tmp")
        tmp.write_text("\n".join(kept) + "\n" if kept else "")
        os.replace(str(tmp), str(event_file))
    except Exception:
        pass  # rotation must never raise


def emit_heal_event(
    source: str,
    category: str,
    severity: str,
    message: str,
    context: dict | None = None,
) -> None:
    """Write a structured event to the self-heal event log.

    The daemon picks this up within its scan interval (default: 5 min).
    This function MUST NOT raise — it's called from error paths.
    Events older than 30 minutes are automatically rotated out.

    Args:
        source: Script/module name (e.g. "mcp_server").
        category: One of: import_failure, path_missing, config_missing,
                  mcp_failure, service_fallback.
        severity: One of: critical, high, medium, low.
        message: Human-readable description of the failure.
        context: Optional structured metadata dict.
    """
    try:
        event = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "source": str(source),
            "category": str(category),
            "severity": str(severity),
            "message": str(message),
            "context": context if context is not None else {},
            "host": socket.gethostname(),
            "pid": os.getpid(),
        }

        event_file = _get_event_file()
        if event_file is None:
            # Cannot resolve project root — fall back to stderr
            print(f"[self-heal] {json.dumps(event)}", file=sys.stderr, flush=True)
            return

        # Rotate old events before writing new one
        rotate_events(event_file)

        # Atomic append: write to temp file in same directory, then append
        # This avoids partial writes if the process is killed mid-write
        event_line = json.dumps(event, separators=(",", ":")) + "\n"

        fd, tmp_path = tempfile.mkstemp(dir=event_file.parent, prefix=".heal_", suffix=".tmp")
        try:
            os.write(fd, event_line.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            fd = -1  # mark as closed

            # Append temp file content to the event log
            with open(event_file, "a", encoding="utf-8") as dest:
                dest.write(event_line)
        finally:
            if fd >= 0:
                os.close(fd)
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as exc:
        # Absolute last resort — write to stderr so we never raise
        try:
            print(
                f"[self-heal] emit failed: {exc} | source={source} "
                f"category={category} severity={severity} message={message}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:
            pass  # truly nothing we can do
