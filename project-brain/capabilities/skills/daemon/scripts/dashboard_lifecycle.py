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
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Setup project root for imports
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from src.config.paths import get_runtime_dir
from src.lib.dashboard_instance import AugurDashboardInstance, resolve_dashboard_instance

if os.name == "nt":
    import msvcrt

    class _FcntlCompat:
        LOCK_EX = 1
        LOCK_UN = 8

        @staticmethod
        def flock(lock_fd: int, operation: int) -> None:
            os.lseek(lock_fd, 0, os.SEEK_END)
            if os.lseek(lock_fd, 0, os.SEEK_CUR) == 0:
                os.write(lock_fd, b"0")
            os.lseek(lock_fd, 0, os.SEEK_SET)
            mode = msvcrt.LK_UNLCK if operation & _FcntlCompat.LOCK_UN else msvcrt.LK_LOCK
            msvcrt.locking(lock_fd, mode, 1)

    fcntl = _FcntlCompat()
else:
    import fcntl

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

STATES = ("stopped", "starting", "compiling", "stabilizing", "healthy", "stopping", "crashed", "degraded", "unknown")
ACTORS = ("dashboard_monitor", "cleanup_processes", "build_lock", "launchd", "dev_build", "unknown")
ACTIONS = (
    "stop", "start", "restart", "rebuild", "health_check", "crash_detected",
    "recovery_attempt", "recovery_success", "recovery_failed", "crash_loop",
    "recovery_abandoned", "gate_denied", "gate_bypassed", "stabilized",
)

OWNERSHIP_TTL_SECONDS = 300  # default: 5 minutes
# Per-state TTL overrides — transient states (mid-start, mid-stop) fail
# fast so a crashed/SIGKILLed actor doesn't leave the gate stuck for the
# full 5 minutes. A healthy dashboard starts in <20s; 60s is generous
# enough that real builds aren't false-expired.
# Root cause documented in project_dashboard_monitor_stuck_gate_fix memory.
TRANSIENT_STATE_TTL_SECONDS = 60
_TRANSIENT_STATES = {"starting", "compiling", "stopping"}
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
    "stopped_at": None,
    "recent_crashes": [],
    "recovery_backoff_seconds": 0,
    "consecutive_healthy_polls": 0,
}


def _normalize_state(state: dict, now: datetime | None = None) -> dict:
    """Keep persisted state internally coherent after older buggy writes."""
    normalized = {**DEFAULT_STATE, **state}
    if not normalized.get("owner"):
        normalized["owner"] = None
        normalized["owner_reason"] = None
        normalized["owner_since"] = None
    normalized = _prune_crash_history(normalized, now=now)
    return normalized


def _prune_crash_history(state: dict, now: datetime | None = None) -> dict:
    """Trim stale crash-loop history and clear it after sustained health."""
    now = now or datetime.now()
    normalized = dict(state)
    crashes = normalized.get("recent_crashes", []) or []
    cutoff = (now - timedelta(seconds=CRASH_LOOP_WINDOW_SECONDS)).isoformat()
    normalized["recent_crashes"] = [c for c in crashes if isinstance(c, str) and c > cutoff]

    healthy_since = normalized.get("healthy_since")
    if normalized.get("state") == "healthy" and healthy_since:
        try:
            healthy_for = (now - datetime.fromisoformat(healthy_since)).total_seconds()
        except (ValueError, TypeError):
            healthy_for = None
        if healthy_for is not None and healthy_for >= HEALTHY_RESET_SECONDS:
            normalized["recent_crashes"] = []
            normalized["recovery_backoff_seconds"] = 0

    return normalized


# ═══════════════════════════════════════════════════════════════════════════════
# STATE I/O
# ═══════════════════════════════════════════════════════════════════════════════


def _resolve_instance(
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> AugurDashboardInstance:
    if instance is not None:
        return instance
    root = _checkout_root_for_default((project_root or Path.cwd()).expanduser().resolve())
    resolved = resolve_dashboard_instance(
        root,
        runtime_dir=get_runtime_dir(),
        explicit_instance=instance_id,
    )
    if resolved.kind == "isolated" and instance_id is None:
        raise RuntimeError(f"could not resolve dashboard instance for {root}")
    if resolved.kind == "main" and instance_id is None and not _looks_like_augur_checkout(root):
        raise RuntimeError(f"could not resolve dashboard instance for {root}")
    return resolved


def _checkout_root_for_default(root: Path) -> Path:
    for candidate in (root, *root.parents):
        if _looks_like_augur_checkout(candidate):
            return candidate
    return root


def _looks_like_augur_checkout(root: Path) -> bool:
    return (
        (root / "project.yaml").exists()
        or (root / ".augur-worktree.yaml").exists()
        or (root / "docs" / "agent-topics").is_dir()
    )


def _state_file(instance: AugurDashboardInstance | None = None) -> Path:
    target = instance or _resolve_instance()
    target.lifecycle_dir.mkdir(parents=True, exist_ok=True)
    return target.lifecycle_dir / "state.json"


def _legacy_state_file() -> Path:
    return get_runtime_dir() / "daemon" / "dashboard_state.json"


def _state_file_for_read(instance: AugurDashboardInstance | None = None) -> Path:
    target = instance or _resolve_instance()
    scoped = _state_file(target)
    legacy = _legacy_state_file()
    if target.kind != "main":
        return scoped
    if not scoped.exists() and legacy.exists():
        return legacy
    if scoped.exists() and legacy.exists():
        try:
            if legacy.stat().st_mtime >= scoped.stat().st_mtime:
                return legacy
        except OSError:
            return scoped
    return scoped


def _gate_lock_file(instance: AugurDashboardInstance | None = None) -> Path:
    target = instance or _resolve_instance()
    target.lifecycle_dir.mkdir(parents=True, exist_ok=True)
    return target.lifecycle_dir / "gate.lock"


def _read_state(instance: AugurDashboardInstance | None = None) -> dict:
    target = instance or _resolve_instance()
    sf = _state_file_for_read(target)
    if sf.exists():
        try:
            raw_state = json.loads(sf.read_text())
            normalized = _normalize_state(raw_state)
            if sf == _legacy_state_file() and target.kind == "main":
                _write_state(normalized, target)
                try:
                    sf.unlink()
                except OSError:
                    pass
            elif normalized != raw_state:
                _write_state(normalized, target)
            return normalized
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt state file, reinitializing")
    return dict(DEFAULT_STATE)


def _write_state(state: dict, instance: AugurDashboardInstance | None = None) -> None:
    target = instance or _resolve_instance()
    sf = _state_file(target)
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(_normalize_state(state), indent=2))
    os.replace(str(tmp), str(sf))


def _init_state_if_missing(
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> None:
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    sf = _state_file(target)
    if not sf.exists():
        _write_state(dict(DEFAULT_STATE), target)


def get_state(
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> dict:
    """Read current lifecycle state."""
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    return _read_state(target)


BUILD_LOCK_RESTORE_KEYS = (
    "state",
    "owner",
    "owner_reason",
    "owner_since",
    "healthy_since",
    "last_crash_at",
    "recent_crashes",
    "recovery_backoff_seconds",
    "consecutive_healthy_polls",
)


def restore_build_lock_state(
    previous_state: dict | None,
    current_state: dict,
    *,
    succeeded: bool,
    now: datetime | None = None,
) -> dict | None:
    """Return the lifecycle state to write when build_lock releases ownership.

    Successful build-lock commands must not republish stale crashed/degraded
    states. The dashboard monitor can still record a fresh crash if the process
    is actually unhealthy after release.
    """
    if not previous_state or current_state.get("owner") != "build_lock":
        return None

    now = now or datetime.now()
    if succeeded:
        prior_polls = previous_state.get("consecutive_healthy_polls", 0)
        if not isinstance(prior_polls, int):
            prior_polls = 0
        restored = {
            **current_state,
            "state": "healthy",
            "owner": None,
            "owner_reason": None,
            "owner_since": None,
            "healthy_since": now.isoformat(),
            "last_crash_at": previous_state.get("last_crash_at"),
            "recent_crashes": [],
            "recovery_backoff_seconds": 0,
            "consecutive_healthy_polls": max(prior_polls, STABILIZATION_POLLS),
        }
        return _normalize_state(restored, now=now)

    restored = dict(current_state)
    for key in BUILD_LOCK_RESTORE_KEYS:
        restored[key] = previous_state.get(key)
    if previous_state.get("state") == "healthy":
        restored["state"] = "crashed"
        restored["healthy_since"] = None
        restored["consecutive_healthy_polls"] = 0
    return _normalize_state(restored, now=now)


def release_build_lock_state(
    previous_state: dict | None,
    *,
    succeeded: bool,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> dict | None:
    """Persist and log the build_lock release transition."""
    if not previous_state:
        return None

    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    lock_path = _gate_lock_file(target)
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        current = _read_state(target)
        restored = restore_build_lock_state(previous_state, current, succeeded=succeeded)
        if restored is None:
            return None
        previous_name = current.get("state", "unknown")
        _write_state(restored, target)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    reason = (
        "build-lock release marked successful command healthy"
        if succeeded
        else "build-lock release restored previous lifecycle state"
    )
    log_event(
        "build_lock",
        "gate_bypassed",
        reason,
        instance=target,
        prev_state=previous_name,
        new_state=restored.get("state", "unknown"),
        build_succeeded=succeeded,
    )
    return restored


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT LOG
# ═══════════════════════════════════════════════════════════════════════════════


LOG_RETENTION_SECONDS = 1800  # 30 minutes
_last_log_rotation: float = 0.0


def _log_lock_file() -> Path:
    return LOG_FILE.with_suffix(".lock")


def _rotate_log() -> None:
    """Remove lifecycle log entries older than 30 minutes. At most once per 5 min."""
    global _last_log_rotation
    now = time.time()
    if now - _last_log_rotation < 300:
        return
    _last_log_rotation = now
    if not LOG_FILE.exists():
        return
    try:
        cutoff = (datetime.now() - timedelta(seconds=LOG_RETENTION_SECONDS)).isoformat()
        kept: list[str] = []
        with open(LOG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("ts", "") >= cutoff:
                        kept.append(line)
                except (json.JSONDecodeError, ValueError):
                    kept.append(line)
        tmp = LOG_FILE.with_suffix(".rotation_tmp")
        tmp.write_text("\n".join(kept) + "\n" if kept else "")
        os.replace(str(tmp), str(LOG_FILE))
    except Exception:
        pass  # rotation must never break logging


def _infer_new_state(action: str, current_state: str) -> str:
    """Infer new_state from action when caller doesn't pass it explicitly."""
    inference = {
        "recovery_failed": "crashed",
        "restart": "starting",
        "crash_loop": "degraded",
        "recovery_abandoned": "degraded",
        "started": "healthy",
        "healthy": "healthy",
        "stabilized": "healthy",
        "recovery_success": "healthy",
        "crash_detected": "crashed",
    }
    return inference.get(action, current_state)


def log_event(
    actor: str,
    action: str,
    reason: str,
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
    **extra: Any,
) -> None:
    """Append a lifecycle event to the JSONL log. Rotates old entries.

    When prev_state/new_state are not passed, prev_state defaults to the
    current persisted state and new_state is inferred from the action.
    If the inferred new_state differs from the persisted state, the state
    file is updated to match.
    """
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    state = _read_state(target)
    current = state.get("state", "unknown")
    prev_state = extra.pop("prev_state", current)
    new_state = extra.pop("new_state", _infer_new_state(action, current))

    # Persist the state transition when it differs from current
    if new_state != current:
        state["state"] = new_state
        if new_state == "healthy":
            state["healthy_since"] = datetime.now().isoformat()
            state["owner"] = None
            state["owner_reason"] = None
            state["owner_since"] = None
            state["recovery_backoff_seconds"] = 0
        elif new_state in ("crashed", "degraded", "stopped"):
            state["healthy_since"] = None
            state["owner"] = None
            state["owner_reason"] = None
            state["owner_since"] = None
        _write_state(state, target)

    entry = {
        "ts": datetime.now().isoformat(),
        "instance_id": target.instance_id,
        "actor": actor,
        "action": action,
        "reason": reason,
        "prev_state": prev_state,
        "new_state": new_state,
        **extra,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _log_lock_file()
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _rotate_log()
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ═══════════════════════════════════════════════════════════════════════════════
# LIFECYCLE GATE
# ═══════════════════════════════════════════════════════════════════════════════


def _check_ownership_ttl(state: dict, instance: AugurDashboardInstance) -> dict:
    """Expire stale ownership. Returns updated state.

    Uses TRANSIENT_STATE_TTL_SECONDS (60s) for starting/compiling/stopping
    and OWNERSHIP_TTL_SECONDS (300s) for everything else. Fast-fail on
    transient states unstuck the gate when a daemon dies mid-start.
    """
    owner_since = state.get("owner_since")
    if owner_since and state.get("owner"):
        current_state = state.get("state", "")
        ttl = (
            TRANSIENT_STATE_TTL_SECONDS
            if current_state in _TRANSIENT_STATES
            else OWNERSHIP_TTL_SECONDS
        )
        try:
            since = datetime.fromisoformat(owner_since)
            if (datetime.now() - since).total_seconds() > ttl:
                expired_owner = state["owner"]
                logger.warning(
                    f"Ownership expired for {expired_owner} in state={current_state} "
                    f"(TTL {ttl}s)"
                )
                state["state"] = "crashed"
                state["owner"] = None
                state["owner_reason"] = None
                state["owner_since"] = None
                _write_state(state, instance)
                log_event(
                    expired_owner, "gate_denied",
                    f"ownership TTL expired after {ttl}s in state={current_state}",
                    instance=instance, prev_state=current_state, new_state="crashed",
                )
        except (ValueError, TypeError):
            pass
    return state


def request_action(
    actor: str,
    action: str,
    reason: str,
    force: bool = False,
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> dict:
    """Gate: request permission to change dashboard state.

    Acquires exclusive flock for the entire read-check-decide-write cycle.
    Returns {"decision": "granted"|"denied", "reason": str}
    """
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    lock_path = _gate_lock_file(target)
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _request_action_locked(actor, action, reason, force, target)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _request_action_locked(actor: str, action: str, reason: str, force: bool, instance: AugurDashboardInstance) -> dict:
    """Gate logic under exclusive lock."""
    state = _read_state(instance)
    state = _check_ownership_ttl(state, instance)
    current = state.get("state", "unknown")

    if action == "start":
        if current in ("healthy", "stabilizing", "starting", "compiling", "stopping"):
            owner = state.get("owner") or "unknown"
            if current == "healthy":
                msg = f"dashboard already healthy, deny start from {actor}"
            elif current == "stopping":
                msg = f"shutdown in progress by {owner}"
            else:
                msg = f"dashboard is {current}, owned by {owner}"
            log_event(actor, "gate_denied", msg, instance=instance)
            return {"decision": "denied", "reason": msg}

        if current in ("crashed", "degraded", "unknown", "stopped"):
            state["state"] = "compiling"
            state["owner"] = actor
            state["owner_reason"] = reason
            state["owner_since"] = datetime.now().isoformat()
            state["consecutive_healthy_polls"] = 0
            _write_state(state, instance)
            log_event(actor, action, reason, instance=instance, prev_state=current, new_state="compiling")
            return {"decision": "granted", "reason": f"start granted to {actor}"}

    # Force bypass
    if force:
        prev = current
        state["state"] = "stopping" if action == "stop" else current
        state["owner"] = actor
        state["owner_reason"] = reason
        state["owner_since"] = datetime.now().isoformat()
        _write_state(state, instance)
        log_event(actor, "gate_bypassed", reason, instance=instance, prev_state=prev, new_state=state["state"])
        return {"decision": "granted", "reason": f"force bypass by {actor}"}

    # Gate rules by current state
    if current == "healthy":
        if action in ("stop", "rebuild"):
            prev = current
            state["state"] = "compiling" if action == "rebuild" else "stopping"
            state["owner"] = actor
            state["owner_reason"] = reason
            state["owner_since"] = datetime.now().isoformat()
            state["healthy_since"] = None
            state["consecutive_healthy_polls"] = 0
            _write_state(state, instance)
            log_event(actor, action, reason, instance=instance, prev_state=prev, new_state=state["state"])
            return {"decision": "granted", "reason": f"{action} granted to {actor}"}

    if current == "stabilizing":
        if action in ("stop", "rebuild"):
            msg = f"dashboard is stabilizing, deny {action} from {actor}"
            log_event(actor, "gate_denied", msg, instance=instance)
            return {"decision": "denied", "reason": msg}

    if current in ("starting", "compiling"):
        if action in ("stop", "rebuild", "restart"):
            owner = state.get("owner") or "unknown"
            msg = f"dashboard is {current}, owned by {owner}"
            log_event(actor, "gate_denied", msg, instance=instance)
            return {"decision": "denied", "reason": msg}

    if current == "stopping":
        owner = state.get("owner") or "unknown"
        msg = f"shutdown in progress by {owner}"
        log_event(actor, "gate_denied", msg, instance=instance)
        return {"decision": "denied", "reason": msg}

    if current in ("crashed", "degraded", "unknown", "stopped"):
        if action == "restart":
            owner = state.get("owner")
            if owner and owner != actor:
                msg = f"recovery already owned by {owner}"
                log_event(actor, "gate_denied", msg, instance=instance)
                return {"decision": "denied", "reason": msg}
            state["state"] = "starting"
            state["owner"] = actor
            state["owner_reason"] = reason
            state["owner_since"] = datetime.now().isoformat()
            _write_state(state, instance)
            log_event(actor, action, reason, instance=instance, prev_state=current, new_state="starting")
            return {"decision": "granted", "reason": f"restart granted to {actor}"}

    # Default: grant (unknown state or unmatched action)
    log_event(actor, action, reason, instance=instance)
    return {"decision": "granted", "reason": f"default grant for {action} in state {current}"}


def mark_stopped(
    actor: str,
    reason: str,
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> dict:
    """Mark the dashboard cleanly stopped: state='stopped', ownership cleared.

    A scoped stop kills the instance's processes but must leave the gate in a
    state the *next* start can claim. The restart grab that precedes a scoped
    stop transitions the gate to the transient 'starting'; if the stop returned
    while still 'starting', the build_lock 'start'/'rebuild' that follows would
    be denied ("dashboard is starting"), the start would abort, and the gate
    would strand until the 60s transient TTL fired. 'stopped' is a clean resting
    state the stopped→start grant path accepts immediately. Lock-protected like
    record_crash/record_healthy_poll so it serializes with the gate.

    Records `stopped_at` so observers (dashboard_monitor) can tell a *recent*
    release — an agent stop+start sequence with the start still in flight —
    from a dashboard that has genuinely been left stopped. Ownership fields are
    cleared here, so without this timestamp the release window is invisible.
    """
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    lock_path = _gate_lock_file(target)
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _read_state(target)
        prev = state.get("state", "unknown")
        state["state"] = "stopped"
        state["owner"] = None
        state["owner_reason"] = None
        state["owner_since"] = None
        state["healthy_since"] = None
        state["stopped_at"] = datetime.now().isoformat()
        state["consecutive_healthy_polls"] = 0
        _write_state(state, target)
        log_event(actor, "stop", reason, instance=target, prev_state=prev, new_state="stopped")
        return state
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ═══════════════════════════════════════════════════════════════════════════════
# STABILITY & CRASH-LOOP TRACKING
# ═══════════════════════════════════════════════════════════════════════════════


def record_crash(
    actor: str,
    reason: str,
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> dict:
    """Record a dashboard crash. Updates state + recent_crashes."""
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    lock_path = _gate_lock_file(target)
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _read_state(target)
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
        state["owner_reason"] = None
        state["owner_since"] = None
        _write_state(state, target)

        log_event(actor, "crash_detected", reason,
                  instance=target,
                  prev_state=prev, new_state="crashed",
                  uptime_seconds=uptime)
        return state
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def is_crash_loop(
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> bool:
    """Check if dashboard is in a crash loop (3+ crashes in 10 min)."""
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    state = _read_state(target)
    crashes = state.get("recent_crashes", [])
    if len(crashes) < CRASH_LOOP_THRESHOLD:
        return False
    cutoff = (datetime.now() - timedelta(seconds=CRASH_LOOP_WINDOW_SECONDS)).isoformat()
    recent = [c for c in crashes if c > cutoff]
    return len(recent) >= CRASH_LOOP_THRESHOLD


def record_healthy_poll(
    *,
    instance: AugurDashboardInstance | None = None,
    project_root: Path | None = None,
    instance_id: str | None = None,
) -> str:
    """Record a successful health check. Returns new state name."""
    target = _resolve_instance(instance=instance, project_root=project_root, instance_id=instance_id)
    lock_path = _gate_lock_file(target)
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = _read_state(target)
        current = state.get("state", "unknown")
        if current in ("compiling", "stopping") and state.get("owner"):
            return current

        polls = state.get("consecutive_healthy_polls", 0) + 1
        state["consecutive_healthy_polls"] = polls

        if current in ("starting", "compiling", "stabilizing", "unknown", "crashed", "degraded"):
            if polls >= STABILIZATION_POLLS:
                state["state"] = "healthy"
                state["healthy_since"] = datetime.now().isoformat()
                state["owner"] = None
                state["owner_reason"] = None
                state["owner_since"] = None
                state["recovery_backoff_seconds"] = 0
                _write_state(state, target)
                log_event("dashboard_monitor", "stabilized", f"stable after {polls} polls",
                          instance=target,
                          prev_state=current, new_state="healthy")
                return "healthy"
            else:
                state["state"] = "stabilizing"
                if not state.get("healthy_since"):
                    state["healthy_since"] = datetime.now().isoformat()
                _write_state(state, target)
                return "stabilizing"

        if current == "healthy":
            # Already healthy, just update polls
            state = _prune_crash_history(state)
            _write_state(state, target)

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


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def _add_target_args(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--instance")
    command_parser.add_argument("--project-root")


def _cli_target(args: argparse.Namespace) -> AugurDashboardInstance:
    return _resolve_instance(
        project_root=Path(args.project_root) if getattr(args, "project_root", None) else None,
        instance_id=getattr(args, "instance", None),
    )


def _print_resolution_error(exc: RuntimeError) -> None:
    print(json.dumps({"decision": "denied", "reason": str(exc)}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dashboard Lifecycle Manager")
    sub = parser.add_subparsers(dest="command")

    # request-action
    ra = sub.add_parser("request-action", help="Request permission for a dashboard action")
    ra.add_argument("--actor", required=True)
    ra.add_argument("--action", required=True)
    ra.add_argument("--reason", required=True)
    ra.add_argument("--force", action="store_true")
    _add_target_args(ra)

    # log-event
    le = sub.add_parser("log-event", help="Log a lifecycle event (passive)")
    le.add_argument("--actor", required=True)
    le.add_argument("--action", required=True)
    le.add_argument("--reason", required=True)
    _add_target_args(le)

    # state
    state_parser = sub.add_parser("state", help="Print current state as JSON")
    _add_target_args(state_parser)

    args = parser.parse_args(argv)

    if args.command == "request-action":
        try:
            target = _cli_target(args)
        except RuntimeError as exc:
            _print_resolution_error(exc)
            return 1
        result = request_action(args.actor, args.action, args.reason, force=args.force, instance=target)
        print(json.dumps(result))
        return 0 if result["decision"] == "granted" else 1

    elif args.command == "log-event":
        try:
            target = _cli_target(args)
        except RuntimeError as exc:
            _print_resolution_error(exc)
            return 1
        log_event(args.actor, args.action, args.reason, instance=target)
        return 0

    elif args.command == "state":
        try:
            target = _cli_target(args)
        except RuntimeError as exc:
            _print_resolution_error(exc)
            return 1
        _init_state_if_missing(instance=target)
        print(json.dumps(get_state(instance=target), indent=2))
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
