"""Process control and monitoring logic for the dashboard monitor.

Contains the main check_and_recover loop, unhealthy server recovery,
and the continuous monitor_loop.
"""

from __future__ import annotations

import os
import signal
import time
from datetime import datetime

from ._base import (
    CHECK_INTERVAL_SECONDS,
    FATAL_NOTIFY_COOLDOWN_SECONDS,
    HTTP_FAILURE_THRESHOLD,
    MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY,
    _out,
    dashboard_lifecycle,
    get_daemon_mode,
    is_production_mode,
    logger,
    notify,
)
from .health import (
    detect_fatal_build_errors,
    detect_runtime_incident,
    attempt_auto_fix,
    get_dashboard_status,
    reset_runtime_incident_cursor,
    write_status,
)
from .locks import is_build_process_running, is_rebuild_in_progress
from .recovery import run_recovery, stage_clear_cache

# Circuit breaker: stop auto-recovery after this many crash-loop detections
MAX_CRASH_LOOP_CYCLES = 3
# Reduced cooldown for escalation-level events (crash loop, recovery abandoned)
ESCALATION_NOTIFY_COOLDOWN_SECONDS = 60
# How long to keep the circuit breaker open before auto-resetting and trying
# again. Without this, a single transient failure (memory pressure, npm flake,
# external dependency) leaves the dashboard permanently dead until manual
# intervention. With it, abandonment becomes "back off and retry later"
# rather than "give up forever".
RECOVERY_ABANDONED_RESET_AFTER_SECONDS = 1800  # 30 minutes
# Grace window after the lifecycle gate is released to 'stopped'.
# An agent-driven restart (e.g. `aug dev build`'s scoped restart) stops the
# instance, releases the gate to 'stopped' via mark_stopped, and then starts
# the server itself. In that window the gate GRANTS a monitor 'restart'
# (stopped is a clean resting state), so the monitor would race the agent's
# start: two dev servers launch, Next's dev-singleton lock aborts the loser,
# and the loser's wrapper chain lingers as zombies. 30s comfortably covers
# the stop→start gap while still letting the next poll (30s interval) heal a
# start that never came.
AGENT_RESTART_GRACE_SECONDS = 30

# ---------------------------------------------------------------------------
# Module-level mutable state
# ---------------------------------------------------------------------------

# Tracks when we first noticed the dashboard was down (reset on recovery/up)
_first_down_at: datetime | None = None

# Tracks whether dashboard was stabilizing (for lifecycle recovery notifications)
_was_stabilizing: bool = False

# Tracks consecutive HTTP health check failures (process alive but returning errors)
_consecutive_http_failures: int = 0
_last_runtime_incident_signature: str | None = None

# Fatal error detection
_last_fatal_notify_at: datetime | None = None

# Circuit breaker state
_crash_loop_cycles: int = 0
_recovery_abandoned: bool = False
_recovery_abandoned_at: datetime | None = None
_last_escalation_notify_at: datetime | None = None


def _update_crash_loop_cycles(count: int) -> None:
    """Update the crash loop cycle counter."""
    global _crash_loop_cycles
    _crash_loop_cycles = count


def _set_recovery_abandoned(value: bool) -> None:
    """Set or clear the recovery-abandoned circuit breaker.

    Records the abandonment timestamp so a cooldown-based auto-reset
    can convert permanent abandonment into periodic retry.
    """
    global _recovery_abandoned, _crash_loop_cycles, _recovery_abandoned_at
    _recovery_abandoned = value
    if value:
        _recovery_abandoned_at = datetime.now()
    else:
        _crash_loop_cycles = 0
        _recovery_abandoned_at = None


def _should_auto_reset_circuit_breaker() -> bool:
    """True when circuit breaker has been open longer than the cooldown.

    Returning True from a check site means the caller should call
    `_set_recovery_abandoned(False)` and proceed with a fresh recovery
    attempt. Without this, dashboard_monitor never autonomously retries
    after abandonment — manual intervention is the only escape.
    """
    if not _recovery_abandoned or _recovery_abandoned_at is None:
        return False
    elapsed = (datetime.now() - _recovery_abandoned_at).total_seconds()
    return elapsed >= RECOVERY_ABANDONED_RESET_AFTER_SECONDS


def _should_notify_and_update(message: str, channel: str = "system") -> bool:
    """Send a notification if the cooldown has elapsed. Returns True if sent."""
    global _last_fatal_notify_at
    now = datetime.now()
    if (
        _last_fatal_notify_at is not None
        and (now - _last_fatal_notify_at).total_seconds() <= FATAL_NOTIFY_COOLDOWN_SECONDS
    ):
        return False
    _last_fatal_notify_at = now
    notify(message, channel=channel)
    return True


def _build_lock_owns_compile() -> bool:
    """Return True while the dashboard build lock intentionally owns downtime."""
    if not dashboard_lifecycle:
        return False
    try:
        state = dashboard_lifecycle.get_state(instance_id="main")
    except Exception:
        return False
    return state.get("state") == "compiling" and state.get("owner") == "build_lock"


def _prod_managed() -> bool:
    """Return True when the monitor must NOT auto-recover the dashboard.

    ADR-787: the main dashboard on :3000 is user-managed (started by `pnpm prod`
    or the user). Auto-recovery is destructive here — it wipes the production
    build (.next) and relaunches the dev server, silently defeating prod, and it
    races the build/serve startup window. So auto-recovery is OFF by default; the
    monitor still detects + reports down state, it just never acts. Opt back in
    with AUGUR_DASHBOARD_AUTORECOVER=1 (e.g. a pure dev-on-main setup).

    A prod marker (written by start-dev --prod) also forces skip even if recovery
    were opted in.
    """
    if os.environ.get("AUGUR_DASHBOARD_AUTORECOVER") != "1":
        return True
    try:
        from src.config.paths import get_runtime_dir

        return (get_runtime_dir() / "dashboard.prod_managed").exists()
    except Exception:
        return False


def _lifecycle_already_marked_down() -> bool:
    """Return True when lifecycle state already captured the down transition."""
    if not dashboard_lifecycle:
        return False
    try:
        state = dashboard_lifecycle.get_state(instance_id="main")
    except Exception:
        return False
    return state.get("state") in {"crashed", "degraded", "stopped"}


def _agent_restart_in_flight() -> str | None:
    """Return a skip reason while another actor's restart sequence is in flight.

    Closes the two windows where the gate alone does not stop the monitor
    from racing an agent-driven restart:

    - state == 'starting': another actor was granted a restart and is bringing
      the dashboard up. The gate would deny the monitor anyway; pre-checking
      skips the heal cycle without burning a gate_denied event each poll.
      Only honored inside the transient TTL so a starter that died mid-start
      cannot stall healing — past the TTL we fall through and let
      request_action expire the stale ownership.
    - state == 'stopped' with a recent `stopped_at`: an agent stop+start
      sequence released the gate between its stop and its start. The gate
      GRANTS a restart here, which is exactly the duplicate-start race; the
      recency grace is the only signal that a start is about to follow.
    """
    if not dashboard_lifecycle:
        return None
    try:
        state = dashboard_lifecycle.get_state(instance_id="main")
    except Exception:
        return None
    current = state.get("state")
    now = datetime.now()

    if current == "starting":
        owner = state.get("owner")
        owner_since = state.get("owner_since")
        if owner and owner_since:
            ttl = getattr(dashboard_lifecycle, "TRANSIENT_STATE_TTL_SECONDS", 60)
            try:
                age = (now - datetime.fromisoformat(owner_since)).total_seconds()
            except (ValueError, TypeError):
                return None
            if 0 <= age <= ttl:
                return f"gate is 'starting', owned by {owner} since {age:.0f}s ago"
        return None

    if current == "stopped":
        stopped_at = state.get("stopped_at")
        if stopped_at:
            try:
                age = (now - datetime.fromisoformat(stopped_at)).total_seconds()
            except (ValueError, TypeError):
                return None
            if 0 <= age <= AGENT_RESTART_GRACE_SECONDS:
                return (
                    f"gate released to 'stopped' {age:.0f}s ago "
                    "(agent stop+start sequence likely in flight)"
                )
        return None

    return None


def _escalation_notify(message: str, channel: str = "system") -> bool:
    """Send an escalation notification with a shorter cooldown (60s).

    Used for crash-loop and recovery-abandoned events that need faster
    user visibility than the standard 5-minute cooldown.
    """
    global _last_escalation_notify_at
    now = datetime.now()
    if (
        _last_escalation_notify_at is not None
        and (now - _last_escalation_notify_at).total_seconds() <= ESCALATION_NOTIFY_COOLDOWN_SECONDS
    ):
        return False
    _last_escalation_notify_at = now
    notify(message, channel=channel)
    return True


def _recover_unhealthy_server(status: dict) -> dict:
    """Handle a running server that fails HTTP health checks.

    Kills the broken process and runs recovery starting at stage_clear_cache,
    since Turbopack cache corruption is the most common cause of a running
    server returning 500 on all routes.
    """
    global _consecutive_http_failures

    if _prod_managed():
        status["action"] = "skipped_prod_managed"
        logger.info("Dashboard unhealthy but user-managed production (ADR-787); not auto-recovering")
        return status

    if status.get("rebuild_in_progress") or is_rebuild_in_progress():
        logger.info(
            "Dashboard unhealthy during an active rebuild/restart; "
            "skipping destructive recovery"
        )
        status["action"] = "skipped_rebuild_unhealthy"
        return status

    logger.warning(
        f"Dashboard process alive but unhealthy (HTTP {status.get('http_status')}, "
        f"{_consecutive_http_failures} consecutive failures) -- "
        "killing process and clearing cache"
    )

    for pid_str in status.get("pids", []):
        try:
            os.kill(int(pid_str), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, ValueError):
            pass
    time.sleep(2)

    if stage_clear_cache():
        _consecutive_http_failures = 0
        reset_runtime_incident_cursor()
        refreshed = get_dashboard_status()
        status.update(refreshed)
        status["action"] = "recovered_clear_cache_unhealthy"
        notify(
            f"Dashboard recovered from unhealthy state (was HTTP {status.get('http_status')}). "
            "Cleared Turbopack cache and restarted.",
            channel="system",
        )
    else:
        status["action"] = "recovery_failed_unhealthy"
        notify(
            "Dashboard is running but unhealthy (all routes returning errors). "
            "Cache clear failed -- manual intervention required.",
            channel="system",
        )

    return status


def check_and_recover() -> dict:
    """Check dashboard status and recover if needed.

    Returns:
        Status dict with action taken
    """
    global _first_down_at, _consecutive_http_failures, _last_fatal_notify_at
    global _was_stabilizing, _last_runtime_incident_signature

    status = get_dashboard_status()
    status["action"] = "none"
    runtime_incident = detect_runtime_incident()
    if runtime_incident:
        status["runtime_incident"] = runtime_incident

    if status["running"]:
        # Process is alive -- but is it actually serving requests?
        if status.get("healthy") and not runtime_incident:
            logger.debug("Dashboard is running and healthy")
            _first_down_at = None
            _consecutive_http_failures = 0
            _last_fatal_notify_at = None
            _last_runtime_incident_signature = None

            # Clear circuit breaker on healthy dashboard
            if _recovery_abandoned or _crash_loop_cycles > 0:
                _set_recovery_abandoned(False)
                logger.info("Circuit breaker cleared: dashboard is healthy")

            # Delegate stability tracking to lifecycle
            if dashboard_lifecycle:
                new_state = dashboard_lifecycle.record_healthy_poll(instance_id="main")
                if new_state == "healthy" and _was_stabilizing:
                    _was_stabilizing = False
                    notify("Dashboard recovered and stable", channel="system")
                elif new_state == "stabilizing":
                    _was_stabilizing = True

            write_status(status)
            return status

        # Process alive but unusable
        if runtime_incident:
            signature = str(runtime_incident.get("signature", ""))
            if signature and signature == _last_runtime_incident_signature:
                logger.info(
                    "Dashboard runtime incident already observed; "
                    "waiting for fresh stderr activity before escalating again"
                )
                status["action"] = "observed_runtime_incident"
                write_status(status)
                return status
            _last_runtime_incident_signature = signature or None
        _consecutive_http_failures += 1
        if runtime_incident:
            logger.warning(
                "Dashboard process alive but runtime degraded "
                f"({runtime_incident['summary']}, "
                f"failures={_consecutive_http_failures}/{HTTP_FAILURE_THRESHOLD})"
            )
            if dashboard_lifecycle:
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "health_check",
                    f"runtime degraded: {runtime_incident['summary']}",
                    instance_id="main",
                    prev_state="healthy",
                    new_state="healthy",
                )
        else:
            logger.warning(
                f"Dashboard process alive but HTTP unhealthy "
                f"(status={status.get('http_status')}, "
                f"failures={_consecutive_http_failures}/{HTTP_FAILURE_THRESHOLD})"
            )

        if _consecutive_http_failures >= HTTP_FAILURE_THRESHOLD:
            if is_production_mode():
                status = _recover_unhealthy_server(status)
            else:
                status["action"] = "notified_unhealthy"
                notify(
                    "Dashboard is running but degraded. "
                    f"Health={status.get('http_status')} "
                    f"details={runtime_incident['summary'] if runtime_incident else 'HTTP failures'}. "
                    "Try clearing the dashboard cache or restarting via the lifecycle gate.",
                    channel="system",
                )

        write_status(status)
        return status

    # Dashboard port not responding
    _consecutive_http_failures = 0
    now = datetime.now()

    build_lock_compiling = _build_lock_owns_compile()
    lifecycle_already_down = _lifecycle_already_marked_down()
    _dashboard_process_alive = (
        build_lock_compiling
        or is_build_process_running()
        or status.get("rebuild_in_progress")
    )
    if _first_down_at is None:
        _first_down_at = now
        if not _dashboard_process_alive:
            if lifecycle_already_down:
                logger.info("Dashboard already marked down by lifecycle; not recording duplicate crash")
            elif dashboard_lifecycle:
                dashboard_lifecycle.record_crash("dashboard_monitor", "process gone", instance_id="main")
        elif build_lock_compiling:
            logger.info("Dashboard down while build_lock owns compile; waiting")
            if dashboard_lifecycle:
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "health_check",
                    "build lock owns dashboard compile; waiting for build release",
                    instance_id="main",
                )
        else:
            logger.info(
                "Dashboard process alive but port not bound yet (compiling)"
            )
            if dashboard_lifecycle:
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "health_check",
                    "process alive, port not bound (compiling)",
                    instance_id="main",
                )
    down_seconds = (now - _first_down_at).total_seconds()

    logger.warning(
        f"Dashboard is not running (down for {down_seconds:.0f}s, "
        f"process_alive={_dashboard_process_alive})"
    )

    if _prod_managed():
        status["action"] = "skipped_prod_managed"
        logger.info(
            "Skipping recovery: main dashboard is user-managed production (ADR-787). "
            "Restart it with `pnpm prod`."
        )
        write_status(status)
        return status

    if build_lock_compiling:
        status["action"] = "skipped_build_lock"
        write_status(status)
        return status

    # Gate-aware heal skip: never race an agent-driven restart. An agent's
    # scoped stop releases the gate to 'stopped' moments before its own start;
    # healing in that window double-starts the dev server (see
    # _agent_restart_in_flight). Skip this cycle and re-check next poll.
    agent_restart_reason = _agent_restart_in_flight()
    if agent_restart_reason:
        status["action"] = "skipped_agent_restart_in_flight"
        logger.info(
            f"Skipping heal cycle: {agent_restart_reason}; re-checking next poll"
        )
        write_status(status)
        return status

    # If a build/rebuild is in progress, wait -- but with a hard timeout.
    if (
        status["rebuild_in_progress"]
        and down_seconds < MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY
    ):
        if down_seconds >= 60:
            _should_notify_and_update(
                f"Dashboard down for {down_seconds:.0f}s (build/compile in progress). "
                f"Will force-recover at {MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY}s.",
            )
        logger.info(
            f"Rebuild in progress, skipping recovery "
            f"(down {down_seconds:.0f}s/{MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY}s)"
        )
        status["action"] = "skipped_rebuild"
        write_status(status)
        return status

    if status["rebuild_in_progress"]:
        logger.warning(
            f"Dashboard down for {down_seconds:.0f}s despite apparent build -- "
            f"forcing recovery (threshold: {MAX_DOWN_SECONDS_BEFORE_FORCE_RECOVERY}s)"
        )
        notify(
            f"Dashboard down for {down_seconds:.0f}s despite build activity. "
            f"Force-recovering now.",
            channel="system",
        )

    # Before blind restarts, check stderr for fatal source errors and attempt auto-fix
    fatal = detect_fatal_build_errors()
    if fatal:
        description, auto_fix_cmds, manual_hint = fatal
        logger.error(f"Fatal build error detected: {description}")

        if auto_fix_cmds is not None:
            if attempt_auto_fix(description, auto_fix_cmds):
                logger.info(
                    "Auto-fix succeeded, proceeding to restart dashboard"
                )
                notify(
                    f"Dashboard down -- detected: {description}. "
                    f"Auto-fix applied, restarting.",
                    channel="system",
                )
                # Fall through to normal recovery below
            else:
                logger.error("Auto-fix failed, manual intervention required")
                status["action"] = "auto_fix_failed"
                status["fatal_error"] = description
                _should_notify_and_update(
                    f"Dashboard down -- {description}. Auto-fix failed. "
                    f"Manual fix: {manual_hint}",
                )
                write_status(status)
                return status
        else:
            status["action"] = "fatal_source_error"
            status["fatal_error"] = description
            _should_notify_and_update(
                f"Dashboard down -- {description}. "
                f"Cannot auto-fix. Manual fix: {manual_hint}",
            )
            write_status(status)
            return status

    # Dashboard is unexpectedly down (or force-recovery triggered)
    # ADR-787: the main :3000 dashboard is user-managed (pnpm prod / next start).
    # Auto-recovery here is destructive — it launches `npm run dev` and wipes the
    # production .next build. Report the down state but never act, unless the user
    # opts in with AUGUR_DASHBOARD_AUTORECOVER=1.
    if _prod_managed():
        status["action"] = "skipped_prod_managed"
        logger.info(
            "Dashboard reported down, but auto-recovery is disabled "
            "(user-managed prod). Set AUGUR_DASHBOARD_AUTORECOVER=1 to enable."
        )
        write_status(status)
        return status

    if is_production_mode():
        # Circuit breaker: if recovery was abandoned, don't attempt again —
        # UNLESS the cooldown has elapsed, in which case auto-reset and retry.
        if _recovery_abandoned:
            if _should_auto_reset_circuit_breaker():
                logger.warning(
                    "Circuit breaker auto-reset after "
                    f"{RECOVERY_ABANDONED_RESET_AFTER_SECONDS}s cooldown. "
                    "Resuming recovery attempts."
                )
                _set_recovery_abandoned(False)
                # Fall through to normal recovery path
            else:
                status["action"] = "recovery_abandoned"
                logger.info(
                    "Recovery previously abandoned (circuit breaker open). "
                    "Waiting for cooldown, manual fix, or healthy poll to clear."
                )
                write_status(status)
                return status

        # Check crash loop before recovery
        if dashboard_lifecycle and dashboard_lifecycle.is_crash_loop(instance_id="main"):
            _crash_loop_cycles_local = _crash_loop_cycles + 1
            _update_crash_loop_cycles(_crash_loop_cycles_local)

            if _crash_loop_cycles_local >= MAX_CRASH_LOOP_CYCLES:
                # Circuit breaker tripped: stop all auto-recovery
                _set_recovery_abandoned(True)
                status["action"] = "recovery_abandoned"
                logger.error(
                    f"Dashboard crash loop exceeded {MAX_CRASH_LOOP_CYCLES} cycles "
                    f"({_crash_loop_cycles_local * 3}+ total attempts). "
                    "Recovery abandoned -- manual intervention required."
                )
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "recovery_abandoned",
                    f"circuit breaker: {_crash_loop_cycles_local} crash-loop cycles, "
                    f"recovery permanently suspended",
                    instance_id="main",
                    prev_state=dashboard_lifecycle.get_state(instance_id="main").get("state", "crashed"),
                    new_state="degraded",
                )
                # Always notify on recovery_abandoned regardless of cooldown
                notify(
                    f"RECOVERY ABANDONED: Dashboard failed {_crash_loop_cycles_local} "
                    f"full crash-loop cycles ({_crash_loop_cycles_local * 3}+ restarts). "
                    "Auto-recovery disabled. Manual fix required.",
                    channel="system",
                )
                write_status(status)
                return status

            status["action"] = "crash_loop"
            logger.error(
                f"Dashboard in crash loop (cycle {_crash_loop_cycles_local}/{MAX_CRASH_LOOP_CYCLES}) "
                "-- recovery suspended this cycle"
            )
            dashboard_lifecycle.log_event(
                "dashboard_monitor",
                "crash_loop",
                f"3+ crashes in 10min (cycle {_crash_loop_cycles_local}/{MAX_CRASH_LOOP_CYCLES}), "
                "suspending recovery",
                instance_id="main",
                prev_state=dashboard_lifecycle.get_state(instance_id="main").get("state", "crashed"),
                new_state="degraded",
            )
            _escalation_notify(
                f"CRASH LOOP (cycle {_crash_loop_cycles_local}/{MAX_CRASH_LOOP_CYCLES}): "
                "Dashboard failed 3x in 10min. Recovery suspended. Manual fix needed.",
            )
            write_status(status)
            return status

        # Request permission from lifecycle gate
        if dashboard_lifecycle:
            gate = dashboard_lifecycle.request_action(
                "dashboard_monitor", "restart", "auto-recovery", instance_id="main"
            )
            if gate["decision"] == "denied":
                logger.info(f"Gate denied recovery: {gate['reason']}")
                status["action"] = "gate_denied"
                write_status(status)
                return status

        logger.info("Production mode: Attempting recovery...")

        success, stage, duration = run_recovery()

        if success:
            reset_runtime_incident_cursor()
            status.update(get_dashboard_status())
            status["action"] = f"recovered_{stage}"
            status["recovery_duration"] = duration
            if dashboard_lifecycle:
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "recovery_success",
                    f"recovered at stage {stage} in {duration:.1f}s",
                    instance_id="main",
                )
            notify(
                f"Dashboard recovered after crash. "
                f"Recovery stage: {stage}, took {duration:.1f}s",
                channel="system",
            )
        else:
            status["action"] = "recovery_failed"
            if dashboard_lifecycle:
                dashboard_lifecycle.log_event(
                    "dashboard_monitor",
                    "recovery_failed",
                    f"all stages exhausted after {duration:.1f}s",
                    instance_id="main",
                )
            notify(
                "Dashboard recovery failed! Manual intervention required.",
                channel="system",
            )
    else:
        # Dev mode: notify only
        logger.info("Dev mode: Notifying without auto-recovery")
        status["action"] = "notified"
        notify(
            "Dashboard is down. Run `npm run dev` in apps/dashboard/ to restart.",
            channel="system",
        )

    write_status(status)
    return status


def monitor_loop(interval: int = CHECK_INTERVAL_SECONDS) -> None:
    """Continuous monitoring loop."""
    logger.info(
        f"Starting dashboard monitor "
        f"(interval: {interval}s, mode: {get_daemon_mode()})"
    )

    while True:
        try:
            check_and_recover()
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")

        time.sleep(interval)
