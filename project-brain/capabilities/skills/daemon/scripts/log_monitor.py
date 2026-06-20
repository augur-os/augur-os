#!/usr/bin/env python3
"""
Log Monitor Service for Augur.

Watches `llm_logs.jsonl` for errors and emits self-heal events.
Features:
- Persistence: Remembers last read line to avoid reprocessing.
- Deduplication: Generates keys for recurring errors.
- Throttling: Limits max bugs per hour (circuit breaker).
"""

import json
import time
import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    text = sep.join(str(arg) for arg in args) + str(end)
    try:
        file.write(text)
    except UnicodeEncodeError:
        encoding = getattr(file, "encoding", None) or sys.getdefaultencoding() or "utf-8"
        file.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

# Fail-fast imports (ADR-084)
from src.logging.self_heal_event import emit_heal_event as _emit_heal  # noqa: E402

try:
    from src.config.paths import get_logs_dir
except ImportError as e:
    _emit_heal(
        source="log_monitor",
        category="import_failure",
        severity="high",
        message=f"Cannot import path helpers: {e}",
        context={"expected_module": "src.config.paths", "fallback_removed": True},
    )
    raise


# Self-healing is handled by the unified daemon (unified_daemon.py)
# which manages this script as a child subprocess.
# LLM errors are surfaced through the self-heal event pipeline (_emit_heal);
# the previous report_p0_bug path lived in the retired advisor skill.

# Import central log retention config
try:
    from src.config.log_retention import LOG_RETENTION

    MAX_BUGS_PER_HOUR = LOG_RETENTION.max_bugs_per_hour
    SLEEP_INTERVAL = LOG_RETENTION.monitor_check_interval_seconds
except ImportError as e:
    _emit_heal(
        source="log_monitor",
        category="import_failure",
        severity="high",
        message=f"Cannot import LOG_RETENTION config: {e}",
        context={"expected_module": "src.config.log_retention", "fallback_removed": True},
    )
    raise

# Constants
LOGS_DIR = get_logs_dir()
LOG_FILE = LOGS_DIR / "llm_logs.jsonl"
STATE_FILE = LOGS_DIR / "log_monitor_state.json"


def get_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_position": 0, "hourly_bugs": 0, "last_reset": datetime.now().isoformat()}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def generate_dedup_key(entry: dict) -> str:
    """Generate a unique fingerprint for an error."""
    parts = [entry.get("provider", "unknown"), entry.get("model", "unknown"), entry.get("error", "unknown_error")]
    # Simple hash of the components
    key_string = "|".join(str(p) for p in parts)
    return hashlib.sha256(key_string.encode()).hexdigest()


def monitor_logs():
    _out(f"👀 Log Monitor started. Watching: {LOG_FILE}")

    while True:
        state = get_state()
        last_pos = state.get("last_position", 0)

        # Reset hourly counter if needed
        last_reset = datetime.fromisoformat(state.get("last_reset", datetime.now().isoformat()))
        if datetime.now() - last_reset > timedelta(hours=1):
            state["hourly_bugs"] = 0
            state["last_reset"] = datetime.now().isoformat()
            save_state(state)
            _out("🔄 Hourly circuit breaker reset.")

        if not LOG_FILE.exists():
            _out(f"⚠️  Log file not found: {LOG_FILE}. Waiting...")
            time.sleep(SLEEP_INTERVAL)
            continue

        try:
            with open(LOG_FILE, "r") as f:
                # Seek to last known position
                f.seek(last_pos)

                # Check if file was truncated (rotated)
                if f.tell() != last_pos:
                    _out("🔄 File rotated or truncated. Resetting position.")
                    f.seek(0)

                new_lines = f.readlines()
                current_pos = f.tell()

                if not new_lines:
                    time.sleep(SLEEP_INTERVAL)
                    continue

                _out(f"📝 Processing {len(new_lines)} new log lines...")

                for line in new_lines:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 🚨 CHECK FOR ERRORS
                    if not entry.get("success", True):
                        if state["hourly_bugs"] >= MAX_BUGS_PER_HOUR:
                            _out("🛑 Circuit breaker active. Skipping bug report.")
                            continue

                        error_msg = entry.get("error", "Unknown error")
                        provider = entry.get("provider", "unknown")
                        model = entry.get("model", "unknown")
                        dedup_key = generate_dedup_key(entry)

                        _out(f"❌ Found error: {error_msg}")

                        _emit_heal(
                            source="log_monitor",
                            category="llm_error",
                            severity="medium",
                            message=f"LLM Error: {provider}/{model} - {error_msg[:200]}",
                            context={
                                "provider": provider,
                                "model": model,
                                "dedup_key": dedup_key,
                                "log_entry": entry,
                            },
                        )

                        state["hourly_bugs"] += 1

                # Update state
                state["last_position"] = current_pos
                save_state(state)

        except Exception as e:
            _out(f"❌ Monitor loop error: {e}")
            time.sleep(SLEEP_INTERVAL)


if __name__ == "__main__":
    monitor_logs()
