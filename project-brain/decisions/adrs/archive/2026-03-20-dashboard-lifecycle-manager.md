# Dashboard Lifecycle Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a coordination layer that prevents concurrent actors from fighting over the dashboard, detects crash loops, and logs every lifecycle event.

**Architecture:** New `dashboard_lifecycle.py` module owns state, event log, and gate logic. `dashboard_monitor.py` delegates state tracking to it. `cleanup_processes.py` and `build-lock.sh` call the gate before acting. CLI entry point for shell scripts.

**Tech Stack:** Python 3.11+, fcntl, JSON, JSONL

**Spec:** `docs/superpowers/specs/2026-03-20-dashboard-lifecycle-manager-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `.claude/skills/daemon/scripts/dashboard_lifecycle.py` | **CREATE** | State machine, gate, event log, stability tracker, crash-loop detector, CLI |
| `.claude/skills/daemon/scripts/dashboard_monitor.py` | MODIFY | Delegate state to lifecycle module, remove in-memory globals |
| `.claude/skills/daemon/scripts/cleanup_processes.py` | MODIFY | Gate call before port kill, remove reload lock |
| `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py` | **CREATE** | Unit tests for lifecycle module |
| `.claude/skills/daemon/augur/tests/test_dashboard_monitor.py` | MODIFY | Update existing tests for lifecycle integration |
| `apps/dashboard/scripts/build-lock.sh` | MODIFY | Gate call before flock acquire |
| `apps/dashboard/scripts/start-dev.sh` | MODIFY | Log-event call on startup |
| `CLAUDE.md` | MODIFY | Add Critical Rule #18 |

---

### Task 1: Core State Machine & Event Log

**Files:**
- Create: `.claude/skills/daemon/scripts/dashboard_lifecycle.py`
- Test: `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py`

- [ ] **Step 1: Write failing tests for state machine basics**

```python
# .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py
"""Tests for dashboard lifecycle manager."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def lifecycle_env(tmp_path, monkeypatch):
    """Set up isolated lifecycle environment."""
    state_dir = tmp_path / "daemon"
    state_dir.mkdir()
    log_file = tmp_path / "dashboard_lifecycle.jsonl"

    monkeypatch.setattr(
        "dashboard_lifecycle.get_runtime_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dashboard_lifecycle.LOG_FILE",
        log_file,
    )

    import dashboard_lifecycle
    dashboard_lifecycle._init_state_if_missing()
    return {"state_dir": state_dir, "log_file": log_file, "module": dashboard_lifecycle}


def test_initial_state_is_unknown(lifecycle_env):
    mod = lifecycle_env["module"]
    state = mod.get_state()
    assert state["state"] in ("unknown", "stopped", "crashed", "healthy")


def test_log_event_appends_jsonl(lifecycle_env):
    mod = lifecycle_env["module"]
    mod.log_event("test_actor", "start", "unit test")
    mod.log_event("test_actor", "stop", "unit test 2")

    lines = lifecycle_env["log_file"].read_text().strip().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["actor"] == "test_actor"
    assert entry["action"] == "start"
    assert "ts" in entry


def test_get_state_returns_persisted_state(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        "state": "healthy",
        "owner": None,
        "owner_reason": None,
        "owner_since": None,
        "healthy_since": "2026-03-20T12:00:00",
        "last_crash_at": None,
        "recent_crashes": [],
        "recovery_backoff_seconds": 0,
        "consecutive_healthy_polls": 2,
    }))
    state = mod.get_state()
    assert state["state"] == "healthy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_lifecycle'`

- [ ] **Step 3: Implement core module — constants, state I/O, event log**

Create `.claude/skills/daemon/scripts/dashboard_lifecycle.py` with:

```python
#!/usr/bin/env python3
"""Dashboard Lifecycle Manager.

Single coordination point for all dashboard state changes.
Owns: state machine, lifecycle gate, event log, stability tracking, crash-loop detection.

Public API:
    request_action(actor, action, reason, force=False) -> dict
    log_event(actor, action, reason, **extra) -> None
    get_state() -> dict

CLI:
    python3 dashboard_lifecycle.py request-action --actor X --action Y --reason Z
    python3 dashboard_lifecycle.py log-event --actor X --action Y --reason Z
    python3 dashboard_lifecycle.py state
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Setup project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_runtime_dir

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging as _logging

    def get_entity_logger(name: str):
        logger = _logging.getLogger(name)
        if not logger.handlers:
            handler = _logging.StreamHandler()
            handler.setFormatter(_logging.Formatter("%(levelname)s - %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(_logging.INFO)
        return logger


logger = get_entity_logger("dashboard_lifecycle")

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

STATES = ("stopped", "starting", "compiling", "stabilizing", "healthy", "stopping", "crashed", "unknown")
ACTORS = ("dashboard_monitor", "cleanup_processes", "build_lock", "launchd", "dev_build", "unknown")
ACTIONS = (
    "stop", "start", "restart", "rebuild", "health_check", "crash_detected",
    "recovery_attempt", "recovery_success", "recovery_failed", "crash_loop",
    "gate_denied", "gate_bypassed", "stabilized",
)

OWNERSHIP_TTL_SECONDS = 300  # 5 minutes
STABILIZATION_POLLS = 2  # consecutive healthy polls before "healthy"
CRASH_LOOP_THRESHOLD = 3  # crashes in window = crash loop
CRASH_LOOP_WINDOW_SECONDS = 600  # 10 minutes
BACKOFF_BASE_SECONDS = 30
BACKOFF_MULTIPLIER = 3
HEALTHY_RESET_SECONDS = 300  # 5 min healthy resets backoff

LOG_FILE = Path.home() / "Library" / "Logs" / "Augur" / "dashboard_lifecycle.jsonl"

DEFAULT_STATE = {
    "state": "unknown",
    "owner": None,
    "owner_reason": None,
    "owner_since": None,
    "healthy_since": None,
    "last_crash_at": None,
    "recent_crashes": [],
    "recovery_backoff_seconds": 0,
    "consecutive_healthy_polls": 0,
}


# ═══════════════════════════════════════════════════════════════════════════════
# STATE I/O
# ═══════════════════════════════════════════════════════════════════════════════


def _state_file() -> Path:
    d = get_runtime_dir() / "daemon"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dashboard_state.json"


def _gate_lock_file() -> Path:
    d = get_runtime_dir() / "daemon"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dashboard_gate.lock"


def _read_state() -> dict:
    sf = _state_file()
    if sf.exists():
        try:
            return json.loads(sf.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt state file, reinitializing")
    return dict(DEFAULT_STATE)


def _write_state(state: dict) -> None:
    sf = _state_file()
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.rename(str(tmp), str(sf))


def _init_state_if_missing() -> None:
    sf = _state_file()
    if not sf.exists():
        _write_state(dict(DEFAULT_STATE))


def get_state() -> dict:
    """Read current lifecycle state."""
    return _read_state()


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT LOG
# ═══════════════════════════════════════════════════════════════════════════════


def _log_lock_file() -> Path:
    return LOG_FILE.with_suffix(".lock")


def log_event(actor: str, action: str, reason: str, **extra: Any) -> None:
    """Append a lifecycle event to the JSONL log."""
    state = _read_state()
    entry = {
        "ts": datetime.now().isoformat(),
        "actor": actor,
        "action": action,
        "reason": reason,
        "prev_state": state.get("state", "unknown"),
        "new_state": state.get("state", "unknown"),
        **extra,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _log_lock_file()
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v 2>&1 | tail -20`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/scripts/dashboard_lifecycle.py .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py
git commit -m "feat(lifecycle): add core state machine, event log, and state I/O"
```

---

### Task 2: Lifecycle Gate (request_action)

**Files:**
- Modify: `.claude/skills/daemon/scripts/dashboard_lifecycle.py`
- Test: `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py`

- [ ] **Step 1: Write failing tests for gate logic**

Append to test file:

```python
def test_gate_grants_stop_when_healthy(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-03-20T11:00:00",
        "consecutive_healthy_polls": 5,
    }))

    result = mod.request_action("dev_build", "stop", "test rebuild")
    assert result["decision"] == "granted"

    # State should now be "stopping" with owner
    new_state = mod.get_state()
    assert new_state["state"] == "stopping"
    assert new_state["owner"] == "dev_build"


def test_gate_denies_stop_when_compiling(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "agent:abc",
    }))

    result = mod.request_action("dev_build", "stop", "want rebuild")
    assert result["decision"] == "denied"
    assert "compiling" in result["reason"]


def test_gate_denies_concurrent_restart(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "owner": "dashboard_monitor",
    }))

    result = mod.request_action("agent:xyz", "restart", "I want to fix it")
    assert result["decision"] == "denied"
    assert "dashboard_monitor" in result["reason"]


def test_gate_grants_restart_when_crashed_no_owner(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "owner": None,
    }))

    result = mod.request_action("dashboard_monitor", "restart", "auto-recovery")
    assert result["decision"] == "granted"


def test_gate_force_bypass(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "agent:abc",
    }))

    result = mod.request_action("cleanup_processes", "stop", "force kill", force=True)
    assert result["decision"] == "granted"

    # Check gate_bypassed was logged
    lines = lifecycle_env["log_file"].read_text().strip().splitlines()
    assert any("gate_bypassed" in line for line in lines)


def test_ownership_ttl_expires(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    expired_time = (datetime.now() - timedelta(seconds=400)).isoformat()
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "dead_agent",
        "owner_since": expired_time,
    }))

    result = mod.request_action("dashboard_monitor", "restart", "TTL expired")
    assert result["decision"] == "granted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v -k "gate" 2>&1 | tail -20`
Expected: FAIL — `AttributeError: module 'dashboard_lifecycle' has no attribute 'request_action'`

- [ ] **Step 3: Implement `request_action()` in dashboard_lifecycle.py**

Add after the event log section:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# LIFECYCLE GATE
# ═══════════════════════════════════════════════════════════════════════════════


def _check_ownership_ttl(state: dict) -> dict:
    """Expire stale ownership. Returns updated state."""
    owner_since = state.get("owner_since")
    if owner_since and state.get("owner"):
        try:
            since = datetime.fromisoformat(owner_since)
            if (datetime.now() - since).total_seconds() > OWNERSHIP_TTL_SECONDS:
                logger.warning(f"Ownership expired for {state['owner']} (TTL {OWNERSHIP_TTL_SECONDS}s)")
                log_event(state["owner"], "gate_denied", f"ownership TTL expired after {OWNERSHIP_TTL_SECONDS}s")
                state["state"] = "crashed"
                state["owner"] = None
                state["owner_since"] = None
        except (ValueError, TypeError):
            pass
    return state


def request_action(actor: str, action: str, reason: str, force: bool = False) -> dict:
    """Gate: request permission to change dashboard state.

    Acquires exclusive flock for the entire read-check-decide-write cycle.
    Returns {"decision": "granted"|"denied", "reason": str}
    """
    lock_path = _gate_lock_file()
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _request_action_locked(actor, action, reason, force)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _request_action_locked(actor: str, action: str, reason: str, force: bool) -> dict:
    """Gate logic under exclusive lock."""
    state = _read_state()
    state = _check_ownership_ttl(state)
    current = state.get("state", "unknown")

    # Force bypass
    if force:
        prev = current
        state["state"] = "stopping" if action == "stop" else current
        state["owner"] = actor
        state["owner_reason"] = reason
        state["owner_since"] = datetime.now().isoformat()
        _write_state(state)
        log_event(actor, "gate_bypassed", reason, prev_state=prev, new_state=state["state"])
        return {"decision": "granted", "reason": f"force bypass by {actor}"}

    # Gate rules by current state
    if current == "healthy":
        if action in ("stop", "rebuild"):
            prev = current
            state["state"] = "stopping" if action == "stop" else "stopping"
            state["owner"] = actor
            state["owner_reason"] = reason
            state["owner_since"] = datetime.now().isoformat()
            state["consecutive_healthy_polls"] = 0
            _write_state(state)
            log_event(actor, action, reason, prev_state=prev, new_state=state["state"])
            return {"decision": "granted", "reason": f"{action} granted to {actor}"}

    if current == "stabilizing":
        if action in ("stop", "rebuild"):
            msg = f"dashboard is stabilizing, deny {action} from {actor}"
            log_event(actor, "gate_denied", msg)
            return {"decision": "denied", "reason": msg}

    if current in ("starting", "compiling"):
        if action in ("stop", "rebuild"):
            owner = state.get("owner", "unknown")
            msg = f"dashboard is {current}, owned by {owner}"
            log_event(actor, "gate_denied", msg)
            return {"decision": "denied", "reason": msg}

    if current == "stopping":
        owner = state.get("owner", "unknown")
        msg = f"shutdown in progress by {owner}"
        log_event(actor, "gate_denied", msg)
        return {"decision": "denied", "reason": msg}

    if current in ("crashed", "unknown", "stopped"):
        if action == "restart":
            owner = state.get("owner")
            if owner and owner != actor:
                msg = f"recovery already owned by {owner}"
                log_event(actor, "gate_denied", msg)
                return {"decision": "denied", "reason": msg}
            state["state"] = "starting"
            state["owner"] = actor
            state["owner_reason"] = reason
            state["owner_since"] = datetime.now().isoformat()
            _write_state(state)
            log_event(actor, action, reason, prev_state=current, new_state="starting")
            return {"decision": "granted", "reason": f"restart granted to {actor}"}

    # Default: grant (unknown state or unmatched action)
    log_event(actor, action, reason)
    return {"decision": "granted", "reason": f"default grant for {action} in state {current}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/scripts/dashboard_lifecycle.py .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py
git commit -m "feat(lifecycle): implement lifecycle gate with concurrency safety and ownership TTL"
```

---

### Task 3: Stability Tracking & Crash-Loop Detection

**Files:**
- Modify: `.claude/skills/daemon/scripts/dashboard_lifecycle.py`
- Test: `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py`

- [ ] **Step 1: Write failing tests for crash-loop and stability**

Append to test file:

```python
def test_record_crash_adds_to_recent_crashes(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({**mod.DEFAULT_STATE, "state": "healthy"}))

    mod.record_crash("dashboard_monitor", "process gone")
    state = mod.get_state()
    assert state["state"] == "crashed"
    assert len(state["recent_crashes"]) == 1


def test_crash_loop_detected_after_3_crashes(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    now = datetime.now()
    recent = [(now - timedelta(seconds=s)).isoformat() for s in [120, 60, 0]]
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "recent_crashes": recent,
    }))

    assert mod.is_crash_loop() is True


def test_no_crash_loop_with_old_crashes(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    now = datetime.now()
    old = [(now - timedelta(seconds=s)).isoformat() for s in [900, 800, 700]]
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "recent_crashes": old,
    }))

    assert mod.is_crash_loop() is False


def test_record_healthy_poll_increments_counter(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "stabilizing",
        "consecutive_healthy_polls": 0,
    }))

    result = mod.record_healthy_poll()
    assert result == "stabilizing"  # still stabilizing after 1 poll

    result = mod.record_healthy_poll()
    assert result == "healthy"  # promoted after 2 polls
    state = mod.get_state()
    assert state["state"] == "healthy"
    assert state["healthy_since"] is not None


def test_get_recovery_backoff(lifecycle_env):
    mod = lifecycle_env["module"]
    assert mod.get_recovery_backoff(0) == 0  # first attempt, no wait
    assert mod.get_recovery_backoff(1) == 30
    assert mod.get_recovery_backoff(2) == 90
    assert mod.get_recovery_backoff(3) == 270
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v -k "crash or healthy_poll or backoff" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: Implement stability and crash-loop functions**

Add to `dashboard_lifecycle.py`:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# STABILITY & CRASH-LOOP TRACKING
# ═══════════════════════════════════════════════════════════════════════════════


def record_crash(actor: str, reason: str) -> dict:
    """Record a dashboard crash. Updates state + recent_crashes."""
    lock_path = _gate_lock_file()
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _read_state()
        prev = state["state"]
        now = datetime.now()

        state["state"] = "crashed"
        state["last_crash_at"] = now.isoformat()
        state["consecutive_healthy_polls"] = 0

        # Add to rolling window
        crashes = state.get("recent_crashes", [])
        crashes.append(now.isoformat())
        # Trim to window
        cutoff = (now - timedelta(seconds=CRASH_LOOP_WINDOW_SECONDS)).isoformat()
        state["recent_crashes"] = [c for c in crashes if c > cutoff]

        # Calculate uptime if was healthy/stabilizing
        uptime = None
        hs = state.get("healthy_since")
        if hs and prev in ("healthy", "stabilizing"):
            try:
                uptime = (now - datetime.fromisoformat(hs)).total_seconds()
            except (ValueError, TypeError):
                pass

        state["healthy_since"] = None
        state["owner"] = None
        state["owner_since"] = None
        _write_state(state)

        log_event(actor, "crash_detected", reason,
                  prev_state=prev, new_state="crashed",
                  uptime_seconds=uptime)
        return state
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def is_crash_loop() -> bool:
    """Check if dashboard is in a crash loop (3+ crashes in 10 min)."""
    state = _read_state()
    crashes = state.get("recent_crashes", [])
    if len(crashes) < CRASH_LOOP_THRESHOLD:
        return False
    cutoff = (datetime.now() - timedelta(seconds=CRASH_LOOP_WINDOW_SECONDS)).isoformat()
    recent = [c for c in crashes if c > cutoff]
    return len(recent) >= CRASH_LOOP_THRESHOLD


def record_healthy_poll() -> str:
    """Record a successful health check. Returns new state name."""
    lock_path = _gate_lock_file()
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _read_state()
        current = state.get("state", "unknown")
        polls = state.get("consecutive_healthy_polls", 0) + 1
        state["consecutive_healthy_polls"] = polls

        if current in ("starting", "compiling", "stabilizing", "unknown"):
            if polls >= STABILIZATION_POLLS:
                state["state"] = "healthy"
                state["healthy_since"] = datetime.now().isoformat()
                state["owner"] = None
                state["owner_since"] = None
                state["recovery_backoff_seconds"] = 0
                _write_state(state)
                log_event("dashboard_monitor", "stabilized", f"stable after {polls} polls",
                          prev_state=current, new_state="healthy")
                return "healthy"
            else:
                state["state"] = "stabilizing"
                if not state.get("healthy_since"):
                    state["healthy_since"] = datetime.now().isoformat()
                _write_state(state)
                return "stabilizing"

        if current == "healthy":
            # Already healthy, just update polls
            _write_state(state)

        return state.get("state", current)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def get_recovery_backoff(attempt: int) -> int:
    """Calculate backoff seconds for recovery attempt N.

    Sequence: 0 (first), 30, 90, 270, ...
    Formula: 0 for n=0, else 30 * 3^(n-1)
    """
    if attempt <= 0:
        return 0
    return BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/scripts/dashboard_lifecycle.py .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py
git commit -m "feat(lifecycle): add stability tracking, crash-loop detection, and recovery backoff"
```

---

### Task 4: CLI Entry Point

**Files:**
- Modify: `.claude/skills/daemon/scripts/dashboard_lifecycle.py`

- [ ] **Step 1: Add CLI `if __name__` block to dashboard_lifecycle.py**

Append at end of file:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard Lifecycle Manager")
    sub = parser.add_subparsers(dest="command")

    # request-action
    ra = sub.add_parser("request-action", help="Request permission for a dashboard action")
    ra.add_argument("--actor", required=True)
    ra.add_argument("--action", required=True)
    ra.add_argument("--reason", required=True)
    ra.add_argument("--force", action="store_true")

    # log-event
    le = sub.add_parser("log-event", help="Log a lifecycle event (passive)")
    le.add_argument("--actor", required=True)
    le.add_argument("--action", required=True)
    le.add_argument("--reason", required=True)

    # state
    sub.add_parser("state", help="Print current state as JSON")

    args = parser.parse_args()

    if args.command == "request-action":
        result = request_action(args.actor, args.action, args.reason, force=args.force)
        print(json.dumps(result))
        return 0 if result["decision"] == "granted" else 1

    elif args.command == "log-event":
        log_event(args.actor, args.action, args.reason)
        return 0

    elif args.command == "state":
        print(json.dumps(get_state(), indent=2))
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test CLI manually**

Run: `cd ~/Projects/Augur && python3 .claude/skills/daemon/scripts/dashboard_lifecycle.py state`
Expected: JSON output with current state

Run: `cd ~/Projects/Augur && python3 .claude/skills/daemon/scripts/dashboard_lifecycle.py log-event --actor test --action start --reason "CLI test"`
Expected: exit 0, event appended to JSONL

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/daemon/scripts/dashboard_lifecycle.py
git commit -m "feat(lifecycle): add CLI entry point for shell script integration"
```

---

### Task 5: Wire dashboard_monitor.py to Lifecycle Module

**Files:**
- Modify: `.claude/skills/daemon/scripts/dashboard_monitor.py` (lines 132-146, 825-996)
- Test: `.claude/skills/daemon/augur/tests/test_dashboard_monitor.py`

This is the largest change. The monitor's `check_and_recover()` delegates state tracking to the lifecycle module.

- [ ] **Step 1: Add lifecycle import to dashboard_monitor.py**

After line 125 (existing `logger = get_entity_logger(...)`) add:

```python
try:
    import dashboard_lifecycle
except ImportError:
    dashboard_lifecycle = None  # Fallback: operate without lifecycle gate
```

- [ ] **Step 2: Modify check_and_recover() — healthy path**

In `check_and_recover()`, replace the block at lines ~837-844 where `_first_down_at = None` is set on healthy:

```python
    if status["running"]:
        if status.get("healthy"):
            _first_down_at = None
            _consecutive_http_failures = 0
            _last_fatal_notify_at = None

            # Delegate stability tracking to lifecycle
            if dashboard_lifecycle:
                new_state = dashboard_lifecycle.record_healthy_poll()
                if new_state == "healthy" and _was_stabilizing:
                    _was_stabilizing = False
                    notify("Dashboard recovered and stable", channel="system")
                elif new_state == "stabilizing":
                    _was_stabilizing = True

            write_status(status)
            return status
```

Add new global: `_was_stabilizing: bool = False`

- [ ] **Step 3: Modify check_and_recover() — crash detection path**

In the "Dashboard is down" section (~line 869), replace the `_first_down_at` tracking with lifecycle calls:

```python
    # Dashboard is down — record via lifecycle
    _consecutive_http_failures = 0
    now = datetime.now()
    if _first_down_at is None:
        _first_down_at = now
        # Record crash in lifecycle if it was previously healthy/stabilizing
        if dashboard_lifecycle:
            dashboard_lifecycle.record_crash("dashboard_monitor", "process gone")
    down_seconds = (now - _first_down_at).total_seconds()
```

- [ ] **Step 4: Modify recovery path — use gate + crash-loop check**

Before calling `run_recovery()`, add gate check and crash-loop detection:

```python
    if is_production_mode():
        # Check crash loop before recovery
        if dashboard_lifecycle and dashboard_lifecycle.is_crash_loop():
            status["action"] = "crash_loop"
            logger.error("Dashboard in crash loop — recovery suspended")
            dashboard_lifecycle.log_event(
                "dashboard_monitor", "crash_loop",
                f"3+ crashes in 10min, suspending recovery"
            )
            now_ts = datetime.now()
            should_notify = (
                _last_fatal_notify_at is None
                or (now_ts - _last_fatal_notify_at).total_seconds() > FATAL_NOTIFY_COOLDOWN_SECONDS
            )
            if should_notify:
                _last_fatal_notify_at = now_ts
                notify(
                    "CRASH LOOP: Dashboard failed 3x in 10min. Recovery suspended. Manual fix needed.",
                    channel="system",
                )
            write_status(status)
            return status

        # Request permission from lifecycle gate
        if dashboard_lifecycle:
            gate = dashboard_lifecycle.request_action("dashboard_monitor", "restart", "auto-recovery")
            if gate["decision"] == "denied":
                logger.info(f"Gate denied recovery: {gate['reason']}")
                status["action"] = "gate_denied"
                write_status(status)
                return status

        logger.info("Production mode: Attempting recovery...")
        success, stage, duration = run_recovery()
```

- [ ] **Step 5: Run existing tests + manual check**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_monitor.py -v 2>&1 | tail -20`
Expected: Existing tests still pass

Run: `python3 -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'.claude/skills/daemon/scripts'); import dashboard_monitor; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/daemon/scripts/dashboard_monitor.py
git commit -m "feat(lifecycle): wire dashboard_monitor to lifecycle gate and crash-loop detection"
```

---

### Task 6: Wire cleanup_processes.py

**Files:**
- Modify: `.claude/skills/daemon/scripts/cleanup_processes.py` (lines 463-487, 522-612)

- [ ] **Step 1: Add lifecycle import**

After imports section (~line 88):

```python
try:
    import dashboard_lifecycle
except ImportError:
    dashboard_lifecycle = None
```

- [ ] **Step 2: Add gate call before port cleanup**

In `cleanup_port()` function (~line 522), before the actual kill logic, add:

```python
    # Request permission from lifecycle gate
    if dashboard_lifecycle and not force:
        gate = dashboard_lifecycle.request_action(
            "cleanup_processes", "stop",
            f"cleanup_port(port={port}, force={force})"
        )
        if gate["decision"] == "denied":
            logger.warning(f"Lifecycle gate denied cleanup: {gate['reason']}")
            return 0  # No processes cleaned
    elif dashboard_lifecycle and force:
        dashboard_lifecycle.request_action(
            "cleanup_processes", "stop",
            f"cleanup_port(port={port}, force=True)",
            force=True,
        )
```

- [ ] **Step 3: Remove `_create_reload_lock` / `_remove_reload_lock`**

Delete functions at lines 463-487. Replace calls to `_create_reload_lock()` with `dashboard_lifecycle.log_event(...)` calls where needed. Replace `_remove_reload_lock()` with nothing (lifecycle gate handles coordination).

Search for all call sites of these functions and update them.

- [ ] **Step 4: Verify script loads**

Run: `python3 -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'.claude/skills/daemon/scripts'); import cleanup_processes; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/daemon/scripts/cleanup_processes.py
git commit -m "feat(lifecycle): wire cleanup_processes to lifecycle gate, remove reload locks"
```

---

### Task 7: Wire build-lock.sh and start-dev.sh

**Files:**
- Modify: `apps/dashboard/scripts/build-lock.sh`
- Modify: `apps/dashboard/scripts/start-dev.sh`

- [ ] **Step 1: Add gate call to build-lock.sh**

This file is Python. Before the flock acquire, add:

```python
# Request lifecycle gate permission before acquiring build lock
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / ".claude" / "skills" / "daemon" / "scripts"))
    from dashboard_lifecycle import request_action
    gate = request_action("build_lock", "rebuild", f"build-lock.sh: {' '.join(sys.argv[1:])}")
    if gate["decision"] == "denied":
        print(f"Lifecycle gate denied: {gate['reason']}", file=sys.stderr)
        sys.exit(1)
except ImportError:
    pass  # Lifecycle module not available, proceed without gate
```

- [ ] **Step 2: Add log-event to start-dev.sh**

Near the top of `start-dev.sh`, after environment setup (~line 25), add:

```bash
# Log dashboard start event
python3 "${AUGUR_ROOT}/.claude/skills/daemon/scripts/dashboard_lifecycle.py" \
    log-event --actor build_lock --action start --reason "start-dev.sh" 2>/dev/null || true
```

- [ ] **Step 3: Test build-lock.sh still works**

Run: `cd ~/Projects/Augur/apps/dashboard && python3 scripts/build-lock.sh echo "test"`
Expected: prints "test" (flock acquired, command runs, flock released)

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/scripts/build-lock.sh apps/dashboard/scripts/start-dev.sh
git commit -m "feat(lifecycle): wire build scripts to lifecycle gate and event log"
```

---

### Task 8: CLAUDE.md Rule & Skill Doc Updates

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.claude/skills/dev-build/SKILL.md`

- [ ] **Step 1: Add Critical Rule #18 to CLAUDE.md**

After rule 17 (Wiring audit on broken/empty pages), add:

```markdown
18. **Dashboard lifecycle gate** — Never run `npm run dev`, `npm run build`, `cleanup_processes.py --port 3000`, or kill dashboard processes directly. All dashboard state changes go through `dashboard_lifecycle.request_action()` (Python) or `dashboard_lifecycle.py request-action` (CLI) or via `/dev-build` which calls the gate internally. Direct manipulation bypasses crash-loop protection and breaks coordination between concurrent agents.
```

- [ ] **Step 2: Update dev-build SKILL.md**

In `.claude/skills/dev-build/SKILL.md`, update Step 1 (Cleanup Processes) to note that cleanup_processes now calls the lifecycle gate automatically. No manual gate call needed when using `/dev-build`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .claude/skills/dev-build/SKILL.md
git commit -m "docs: add dashboard lifecycle gate rule #18, update dev-build skill"
```

---

### Task 9: Integration Test — Full Lifecycle Flow

**Files:**
- Modify: `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py`

- [ ] **Step 1: Write end-to-end lifecycle test**

```python
def test_full_lifecycle_flow(lifecycle_env):
    """Simulate: healthy → stop → start → compile → stabilize → healthy."""
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({**mod.DEFAULT_STATE, "state": "healthy", "healthy_since": "2026-03-20T11:00:00", "consecutive_healthy_polls": 5}))

    # Agent requests stop
    result = mod.request_action("dev_build", "stop", "rebuild requested")
    assert result["decision"] == "granted"
    assert mod.get_state()["state"] == "stopping"

    # Another agent tries to stop — denied
    result = mod.request_action("agent:xyz", "stop", "me too")
    assert result["decision"] == "denied"

    # Simulate: dashboard stops, then crashes detected
    mod.record_crash("dashboard_monitor", "process gone after stop")
    assert mod.get_state()["state"] == "crashed"

    # Monitor requests restart
    result = mod.request_action("dashboard_monitor", "restart", "auto-recovery")
    assert result["decision"] == "granted"
    assert mod.get_state()["state"] == "starting"

    # Health polls: stabilizing → healthy
    assert mod.record_healthy_poll() == "stabilizing"
    assert mod.record_healthy_poll() == "healthy"
    assert mod.get_state()["state"] == "healthy"

    # Verify event log has full trace
    log_lines = lifecycle_env["log_file"].read_text().strip().splitlines()
    actions = [json.loads(l)["action"] for l in log_lines]
    assert "stop" in actions
    assert "gate_denied" in actions
    assert "crash_detected" in actions
    assert "restart" in actions
    assert "stabilized" in actions


def test_crash_loop_blocks_recovery(lifecycle_env):
    """Simulate 3 rapid crashes — recovery should be blocked."""
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({**mod.DEFAULT_STATE, "state": "healthy", "healthy_since": "2026-03-20T11:00:00"}))

    for i in range(3):
        mod.record_crash("dashboard_monitor", f"crash #{i+1}")
        # Simulate quick recovery between crashes
        if i < 2:
            state = mod.get_state()
            state["state"] = "healthy"
            state["healthy_since"] = datetime.now().isoformat()
            state_file.write_text(json.dumps(state))

    assert mod.is_crash_loop() is True
```

- [ ] **Step 2: Run full test suite**

Run: `cd ~/Projects/Augur && PYTHONPATH=.claude/skills/daemon/scripts:. python3 -m pytest .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py -v 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py
git commit -m "test(lifecycle): add integration tests for full lifecycle flow and crash-loop blocking"
```

---

### Task 10: Restart Daemon & Verify

- [ ] **Step 1: Restart daemon to load new code**

```bash
launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist 2>/dev/null
sleep 1
launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist
```

- [ ] **Step 2: Verify all 11 services running**

```bash
sleep 5
python3 .claude/skills/daemon/scripts/unified_daemon.py status
```

Expected: 11/11 RUNNING

- [ ] **Step 3: Verify lifecycle state is tracking**

```bash
python3 .claude/skills/daemon/scripts/dashboard_lifecycle.py state
```

Expected: JSON with current dashboard state

- [ ] **Step 4: Verify event log is being written**

```bash
sleep 35  # Wait for one monitor cycle
cat ~/Library/Logs/Augur/dashboard_lifecycle.jsonl | tail -3
```

Expected: At least one `health_check` event logged

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(lifecycle): dashboard lifecycle manager — coordination gate, event log, crash-loop detection"
```
