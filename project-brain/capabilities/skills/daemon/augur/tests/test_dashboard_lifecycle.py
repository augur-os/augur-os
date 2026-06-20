"""Tests for dashboard lifecycle manager."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def lifecycle_env(tmp_path, monkeypatch):
    """Set up isolated lifecycle environment."""
    state_dir = tmp_path / "daemon"
    state_dir.mkdir()
    log_file = tmp_path / "dashboard_lifecycle.jsonl"
    repo_root = tmp_path / "Augur"
    repo_root.mkdir()
    (repo_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")

    monkeypatch.setattr(
        "dashboard_lifecycle.get_runtime_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "dashboard_lifecycle.LOG_FILE",
        log_file,
    )
    monkeypatch.chdir(repo_root)

    import dashboard_lifecycle
    dashboard_lifecycle._init_state_if_missing()
    return {"state_dir": state_dir, "log_file": log_file, "module": dashboard_lifecycle, "repo_root": repo_root}


# ═══════════════════════════════════════════════════════════════════════════════
# Task 1: Core State Machine & Event Log
# ═══════════════════════════════════════════════════════════════════════════════


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


def test_get_state_normalizes_stale_owner_metadata(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "owner": None,
        "owner_reason": "stale reason",
        "owner_since": "2026-03-20T12:00:00",
    }))

    state = mod.get_state()
    assert state["owner"] is None
    assert state["owner_reason"] is None
    assert state["owner_since"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2: Lifecycle Gate (request_action)
# ═══════════════════════════════════════════════════════════════════════════════


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


def test_gate_denies_restart_when_compiling(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
    }))

    result = mod.request_action("dashboard_monitor", "restart", "auto-recovery")
    assert result["decision"] == "denied"
    assert "compiling" in result["reason"]
    assert "build_lock" in result["reason"]


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


def test_gate_grants_start_and_tracks_compiling_owner(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "unknown",
        "owner": None,
    }))

    result = mod.request_action("build_lock", "start", "build-lock.sh: start-dev")
    assert result["decision"] == "granted"

    state = mod.get_state()
    assert state["state"] == "compiling"
    assert state["owner"] == "build_lock"


def test_gate_grants_rebuild_as_compiling_owned_by_build_lock(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-05-06T14:00:00",
        "consecutive_healthy_polls": 5,
    }))

    result = mod.request_action("build_lock", "rebuild", "build-lock.mjs: pnpm run build")

    assert result["decision"] == "granted"
    state = mod.get_state()
    assert state["state"] == "compiling"
    assert state["owner"] == "build_lock"
    assert state["healthy_since"] is None
    assert state["consecutive_healthy_polls"] == 0


def test_build_lock_success_does_not_restore_stale_crashed_state(lifecycle_env):
    mod = lifecycle_env["module"]
    previous_crash_at = "2026-05-24T17:29:41.299068"
    now = datetime(2026, 5, 24, 20, 42, 7)
    previous = {
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "last_crash_at": previous_crash_at,
        "recent_crashes": [previous_crash_at],
        "recovery_backoff_seconds": 90,
        "consecutive_healthy_polls": 383,
    }
    current = {
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
        "owner_reason": "build-lock.sh: scripts/build.sh",
        "owner_since": "2026-05-24T20:41:23.631862",
    }

    restored = mod.restore_build_lock_state(previous, current, succeeded=True, now=now)

    assert restored is not None
    assert restored["state"] == "healthy"
    assert restored["owner"] is None
    assert restored["owner_reason"] is None
    assert restored["owner_since"] is None
    assert restored["healthy_since"] == now.isoformat()
    assert restored["last_crash_at"] == previous_crash_at
    assert restored["recent_crashes"] == []
    assert restored["recovery_backoff_seconds"] == 0
    assert restored["consecutive_healthy_polls"] >= mod.STABILIZATION_POLLS


def test_build_lock_success_keeps_previously_healthy_state_healthy(lifecycle_env):
    mod = lifecycle_env["module"]
    previous = {
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-05-24T20:40:00",
        "consecutive_healthy_polls": 12,
    }
    current = {
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
        "owner_reason": "build-lock.mjs: pnpm run build",
        "owner_since": "2026-05-24T20:41:23",
    }

    restored = mod.restore_build_lock_state(previous, current, succeeded=True)

    assert restored is not None
    assert restored["state"] == "healthy"
    assert restored["owner"] is None
    assert restored["healthy_since"] is not None
    assert restored["consecutive_healthy_polls"] == 12


def test_build_lock_failure_preserves_previous_crashed_state(lifecycle_env):
    mod = lifecycle_env["module"]
    now = datetime(2026, 5, 24, 17, 30, 0)
    previous_crash_at = "2026-05-24T17:29:41.299068"
    previous = {
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "last_crash_at": previous_crash_at,
        "recent_crashes": [previous_crash_at],
        "recovery_backoff_seconds": 90,
    }
    current = {
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
        "owner_reason": "build-lock.sh: scripts/build.sh",
    }

    restored = mod.restore_build_lock_state(previous, current, succeeded=False, now=now)

    assert restored is not None
    assert restored["state"] == "crashed"
    assert restored["last_crash_at"] == previous["last_crash_at"]
    assert restored["recent_crashes"] == previous["recent_crashes"]
    assert restored["recovery_backoff_seconds"] == 90


def test_build_lock_restore_ignores_state_not_owned_by_build_lock(lifecycle_env):
    mod = lifecycle_env["module"]
    previous = {
        **mod.DEFAULT_STATE,
        "state": "crashed",
    }
    current = {
        **mod.DEFAULT_STATE,
        "state": "starting",
        "owner": "dashboard_monitor",
    }

    restored = mod.restore_build_lock_state(previous, current, succeeded=True)

    assert restored is None


def test_recovery_success_clears_owner_and_sets_healthy_since(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "starting",
        "owner": "dashboard_monitor",
        "owner_reason": "auto-recovery",
        "owner_since": "2026-05-06T14:42:52",
    }))

    mod.log_event("dashboard_monitor", "recovery_success", "recovered")

    state = mod.get_state()
    assert state["state"] == "healthy"
    assert state["owner"] is None
    assert state["owner_reason"] is None
    assert state["owner_since"] is None
    assert state["healthy_since"]


def test_gate_denies_duplicate_start_when_compiling(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
    }))

    result = mod.request_action("build_lock", "start", "build-lock.sh: duplicate")
    assert result["decision"] == "denied"
    assert "compiling" in result["reason"]


def test_gate_denies_duplicate_start_when_stabilizing_without_rendering_none_owner(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "stabilizing",
        "owner": None,
    }))

    result = mod.request_action("build_lock", "start", "build-lock.sh: duplicate")
    assert result["decision"] == "denied"
    assert "stabilizing" in result["reason"]
    assert "None" not in result["reason"]
    assert "unknown" in result["reason"]


def test_mark_stopped_releases_gate_for_next_start(lifecycle_env):
    """A scoped stop must leave the gate 'stopped' so the build_lock start that
    follows it is granted — not deadlocked.

    Regression (2026-06-09): `aug dev build` grabbed the gate with action
    'restart' (→ 'starting') for its scoped stop, then `start-dev.sh`'s
    build-lock requested 'start' and was DENIED ('dashboard is starting,
    owned by agent:aug-dev-build'). The prebuild exited 1, `set -e` aborted
    start-dev.sh before the dev server launched, and the gate stranded in
    'starting'.
    """
    mod = lifecycle_env["module"]

    # 1. Orchestrator's scoped-stop gate grab: restart from a clean state → starting.
    grant = mod.request_action("agent:aug-dev-build", "restart", "scoped restart")
    assert grant["decision"] == "granted"
    assert mod.get_state()["state"] == "starting"

    # 2. Without releasing, the nested build_lock 'start' would deadlock.
    denied = mod.request_action("build_lock", "start", "build-lock.sh: start-dev")
    assert denied["decision"] == "denied"
    assert "starting" in denied["reason"]

    # 3. The stop completes → gate released to 'stopped' (clean, unowned).
    mod.mark_stopped("agent:aug-dev-build", "scoped stop complete")
    stopped = mod.get_state()
    assert stopped["state"] == "stopped"
    assert stopped["owner"] is None

    # 4. The nested build_lock 'start' is now granted, not deadlocked.
    gate = mod.request_action("build_lock", "start", "build-lock.sh: start-dev")
    assert gate["decision"] == "granted", gate
    final = mod.get_state()
    assert final["state"] == "compiling"
    assert final["owner"] == "build_lock"


def test_mark_stopped_records_stopped_at_timestamp(lifecycle_env):
    """mark_stopped must stamp `stopped_at` so observers (dashboard_monitor)
    can tell a just-released agent stop+start window from a dashboard that has
    genuinely been left stopped. Ownership fields are cleared on stop, so this
    timestamp is the only recency signal."""
    mod = lifecycle_env["module"]

    before = datetime.now() - timedelta(seconds=1)
    mod.mark_stopped("agent:aug-dev-build", "scoped stop complete")
    after = datetime.now() + timedelta(seconds=1)

    state = mod.get_state()
    assert state["state"] == "stopped"
    assert state["owner"] is None
    stopped_at = datetime.fromisoformat(state["stopped_at"])
    assert before <= stopped_at <= after


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


def test_starting_state_uses_short_ttl_so_stuck_gate_self_clears(lifecycle_env):
    """Starting/compiling/stopping must expire faster than the 300s default.

    Real-world incident (2026-05-17): dashboard_monitor took the "starting"
    lock after cleanup_processes, never released it, launchctl restart
    attempts were denied for the full TTL. Healthy starts complete in <20s
    — a 60s ceiling fails fast without false-expiring real work.
    See project_dashboard_monitor_stuck_gate_fix memory.
    """
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    # 90s ago: past the new starting/compiling/stopping TTL (60s) but
    # well under the old 300s default that left the gate stuck.
    stuck_time = (datetime.now() - timedelta(seconds=90)).isoformat()
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "starting",
        "owner": "dashboard_monitor",
        "owner_since": stuck_time,
    }))

    result = mod.request_action("launchd", "start", "post-stuck launch")
    assert result["decision"] == "granted", result
    # State is now compiling (post-grant) AND the stuck owner is no longer holding the gate
    persisted = mod._read_state(mod._resolve_instance())
    assert persisted["owner"] == "launchd"
    assert persisted["state"] == "compiling"


def test_healthy_state_keeps_full_ttl(lifecycle_env):
    """Healthy state typically has no owner; if one lingers, it shouldn't be
    snap-expired by the new short TTL — only the long 300s default applies."""
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    moderate_time = (datetime.now() - timedelta(seconds=90)).isoformat()
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "owner": "old_actor",
        "owner_since": moderate_time,
    }))

    # Health-state with lingering owner at 90s should NOT have been TTL-cleared
    # by the short-state TTL (which only applies to starting/compiling/stopping).
    # Calling request_action with action="rebuild" should still see owner intact.
    state_before = mod._read_state(mod._resolve_instance())
    state_after = mod._check_ownership_ttl(dict(state_before), mod._resolve_instance())
    assert state_after.get("owner") == "old_actor", "healthy state TTL should not fire at 90s"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 3: Stability Tracking & Crash-Loop Detection
# ═══════════════════════════════════════════════════════════════════════════════


def test_record_crash_adds_to_recent_crashes(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "owner": "build_lock",
        "owner_reason": "build-lock.sh: start-dev",
    }))

    mod.record_crash("dashboard_monitor", "process gone")
    state = mod.get_state()
    assert state["state"] == "crashed"
    assert len(state["recent_crashes"]) == 1
    assert state["owner"] is None
    assert state["owner_reason"] is None


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


def test_get_state_clears_recent_crashes_after_sustained_health(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    healthy_since = (datetime.now() - timedelta(seconds=mod.HEALTHY_RESET_SECONDS + 30)).isoformat()
    recent = [(datetime.now() - timedelta(seconds=s)).isoformat() for s in [120, 60, 0]]
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": healthy_since,
        "recent_crashes": recent,
        "recovery_backoff_seconds": 90,
    }))

    state = mod.get_state()
    assert state["recent_crashes"] == []
    assert state["recovery_backoff_seconds"] == 0


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


def test_record_healthy_poll_clears_owner_reason_when_promoted_healthy(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "stabilizing",
        "owner": "build_lock",
        "owner_reason": "build-lock.sh: mount-plugins",
        "consecutive_healthy_polls": 1,
    }))

    result = mod.record_healthy_poll()
    assert result == "healthy"
    state = mod.get_state()
    assert state["owner"] is None
    assert state["owner_reason"] is None


def test_record_healthy_poll_does_not_revive_stopping_state(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "stopping",
        "owner": "build_lock",
        "owner_reason": "build-lock.mjs: pnpm run build",
        "consecutive_healthy_polls": 1,
    }))

    result = mod.record_healthy_poll()

    assert result == "stopping"
    state = mod.get_state()
    assert state["state"] == "stopping"
    assert state["owner"] == "build_lock"
    assert state["consecutive_healthy_polls"] == 1


def test_record_healthy_poll_does_not_release_build_lock_compiling_state(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "compiling",
        "owner": "build_lock",
        "owner_reason": "build-lock.mjs: pnpm run build",
        "consecutive_healthy_polls": 1,
    }))

    result = mod.record_healthy_poll()

    assert result == "compiling"
    state = mod.get_state()
    assert state["state"] == "compiling"
    assert state["owner"] == "build_lock"
    assert state["consecutive_healthy_polls"] == 1


def test_record_healthy_poll_prunes_stale_crash_history_while_healthy(lifecycle_env):
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    healthy_since = (datetime.now() - timedelta(seconds=mod.HEALTHY_RESET_SECONDS + 30)).isoformat()
    recent = [(datetime.now() - timedelta(seconds=s)).isoformat() for s in [120, 60, 0]]
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": healthy_since,
        "recent_crashes": recent,
        "recovery_backoff_seconds": 30,
        "consecutive_healthy_polls": 4,
    }))

    result = mod.record_healthy_poll()
    assert result == "healthy"
    state = mod.get_state()
    assert state["recent_crashes"] == []
    assert state["recovery_backoff_seconds"] == 0


def test_get_recovery_backoff(lifecycle_env):
    mod = lifecycle_env["module"]
    assert mod.get_recovery_backoff(0) == 0  # first attempt, no wait
    assert mod.get_recovery_backoff(1) == 30
    assert mod.get_recovery_backoff(2) == 90
    assert mod.get_recovery_backoff(3) == 270


# ═══════════════════════════════════════════════════════════════════════════════
# Task 9: Integration Tests — Full Lifecycle Flow
# ═══════════════════════════════════════════════════════════════════════════════


def test_full_lifecycle_flow(lifecycle_env):
    """Simulate: healthy -> stop -> crash -> restart -> stabilize -> healthy."""
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-03-20T11:00:00",
        "consecutive_healthy_polls": 5,
    }))

    # Agent requests stop
    result = mod.request_action("dev_build", "stop", "rebuild requested")
    assert result["decision"] == "granted"
    assert mod.get_state()["state"] == "stopping"

    # Another agent tries to stop — denied
    result = mod.request_action("agent:xyz", "stop", "me too")
    assert result["decision"] == "denied"

    # Simulate: dashboard stops, then crash detected
    mod.record_crash("dashboard_monitor", "process gone after stop")
    assert mod.get_state()["state"] == "crashed"

    # Monitor requests restart
    result = mod.request_action("dashboard_monitor", "restart", "auto-recovery")
    assert result["decision"] == "granted"
    assert mod.get_state()["state"] == "starting"

    # Health polls: stabilizing -> healthy
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
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-03-20T11:00:00",
    }))

    for i in range(3):
        mod.record_crash("dashboard_monitor", f"crash #{i+1}")
        # Simulate quick recovery between crashes
        if i < 2:
            state = mod.get_state()
            state["state"] = "healthy"
            state["healthy_since"] = datetime.now().isoformat()
            state_file.write_text(json.dumps(state))

    assert mod.is_crash_loop() is True


def test_crash_loop_does_not_block_lifecycle_gate(lifecycle_env):
    """Verify that crash-loop detection does NOT block the lifecycle gate itself.

    Design rationale (ADR-459 Gap #2):
    The lifecycle gate (request_action) is a low-level coordination primitive.
    It decides based on state ownership and transitions, NOT on crash-loop status.
    Crash-loop blocking is the responsibility of the *caller* — specifically
    dashboard_monitor.py, which checks is_crash_loop() before calling
    request_action(). This separation keeps the gate simple and testable:

        dashboard_monitor.py:  if is_crash_loop(): apply backoff, skip restart
        dashboard_lifecycle.py: gate grants/denies based on state + ownership only

    This test proves the gate grants restart even during a crash loop,
    confirming the blocking logic lives upstream in the monitor, not here.
    """
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"

    # Set up crash-loop conditions: 3 recent crashes within the window
    now = datetime.now()
    recent = [(now - timedelta(seconds=s)).isoformat() for s in [120, 60, 0]]
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "crashed",
        "recent_crashes": recent,
        "owner": None,
    }))

    # Confirm crash loop IS detected
    assert mod.is_crash_loop() is True

    # Gate still grants restart — it doesn't check crash-loop status
    result = mod.request_action("dashboard_monitor", "restart", "auto-recovery")
    assert result["decision"] == "granted"
    assert mod.get_state()["state"] == "starting"


def test_concurrent_actor_coordination(lifecycle_env):
    """Verify mutual exclusion: only one actor can drive a state transition.

    ADR-459 Gap #4: Tests that the lifecycle gate correctly serializes
    concurrent actors attempting overlapping state changes.

    Scenario:
      1. Actor 1 (dev_build) requests stop while healthy -> granted, state=stopping
      2. Actor 2 (agent:xyz) requests stop while stopping -> denied
      3. Actor 3 (dashboard_monitor) requests rebuild while stopping -> denied
    """
    mod = lifecycle_env["module"]
    state_file = lifecycle_env["state_dir"] / "dashboard_state.json"

    # Start from healthy state
    state_file.write_text(json.dumps({
        **mod.DEFAULT_STATE,
        "state": "healthy",
        "healthy_since": "2026-03-20T11:00:00",
        "consecutive_healthy_polls": 5,
    }))

    # Actor 1: dev_build requests stop -> granted
    result1 = mod.request_action("dev_build", "stop", "rebuild requested")
    assert result1["decision"] == "granted"
    state = mod.get_state()
    assert state["state"] == "stopping"
    assert state["owner"] == "dev_build"

    # Actor 2: another agent requests stop while stopping -> denied
    result2 = mod.request_action("agent:xyz", "stop", "I also want to stop")
    assert result2["decision"] == "denied"
    assert "shutdown in progress" in result2["reason"]
    assert "dev_build" in result2["reason"]

    # Actor 3: monitor requests rebuild while stopping -> denied
    result3 = mod.request_action("dashboard_monitor", "rebuild", "needs rebuild")
    assert result3["decision"] == "denied"
    assert "shutdown in progress" in result3["reason"]

    # State unchanged — still stopping, still owned by dev_build
    final_state = mod.get_state()
    assert final_state["state"] == "stopping"
    assert final_state["owner"] == "dev_build"

    # Verify denial events were logged
    log_lines = lifecycle_env["log_file"].read_text().strip().splitlines()
    denial_events = [json.loads(l) for l in log_lines if "gate_denied" in l]
    assert len(denial_events) >= 2
    denied_actors = {e["actor"] for e in denial_events}
    assert "agent:xyz" in denied_actors
    assert "dashboard_monitor" in denied_actors
