"""Regression tests for dashboard monitor recovery flow."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

import dashboard_monitor
from monitor import process as _process_mod
from monitor import health as _health_mod
from monitor import recovery as _recovery_mod
from monitor import _base as _base_mod


@pytest.fixture(autouse=True)
def _disable_prod_managed_marker(monkeypatch) -> None:
    monkeypatch.setattr(_process_mod, "_prod_managed", lambda: False)


def test_run_recovery_attempts_all_configured_stages(monkeypatch) -> None:
    monkeypatch.setattr(_recovery_mod, "RECOVERY_STAGES", ["a", "b", "c", "d"])
    monkeypatch.setattr(_recovery_mod, "MAX_RESTART_ATTEMPTS", 4)

    attempted: list[str] = []

    def _make_stage(name: str, success: bool):
        def _run() -> bool:
            attempted.append(name)
            return success

        return _run

    monkeypatch.setattr(
        _recovery_mod,
        "RECOVERY_FUNCTIONS",
        {
            "a": _make_stage("a", False),
            "b": _make_stage("b", False),
            "c": _make_stage("c", False),
            "d": _make_stage("d", True),
        },
    )
    monkeypatch.setattr(_recovery_mod, "create_lock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_recovery_mod, "remove_lock", lambda *_args, **_kwargs: None)

    success, stage, _duration = dashboard_monitor.run_recovery()

    assert success is True
    assert stage == "d"
    assert attempted == ["a", "b", "c", "d"]


def test_stage_restart_uses_launchd_when_dashboard_plist_exists(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plist = tmp_path / "com.augur.dashboard.plist"
    plist.write_text("<plist />")
    launchctl_calls: list[list[str]] = []

    monkeypatch.setattr(_recovery_mod, "LAUNCHD_DASHBOARD_PLIST", plist)
    monkeypatch.setattr(_recovery_mod, "LAUNCHD_DASHBOARD_LABEL", "com.augur.dashboard")
    monkeypatch.setattr(_recovery_mod.sys, "platform", "darwin")
    monkeypatch.setattr(_recovery_mod, "_kill_zombie_dashboard_processes", lambda: 0)
    monkeypatch.setattr(_recovery_mod, "STAGE_RESTART_BIND_WAIT_SECONDS", 2)
    monkeypatch.setattr(_recovery_mod, "STAGE_RESTART_STABILITY_SECONDS", 0)
    monkeypatch.setattr(_recovery_mod, "STAGE_RESTART_HTTP_RETRIES", 1)
    monkeypatch.setattr(_recovery_mod.time, "sleep", lambda _seconds: None)
    running_states = iter([False, True, True])
    monkeypatch.setattr(_recovery_mod, "is_dashboard_running", lambda: next(running_states))
    monkeypatch.setattr(_recovery_mod, "check_dashboard_http_health", lambda timeout=5: 200)

    def _run(command: list[str], **_kwargs):
        launchctl_calls.append(command)
        if command[:3] == ["launchctl", "list", "com.augur.dashboard"]:
            return CompletedProcess(command, 1, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(_recovery_mod, "_run_command", _run)
    monkeypatch.setattr(
        _recovery_mod,
        "_popen_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stage_restart should use launchd when available")
        ),
    )

    assert _recovery_mod.stage_restart() is True
    assert launchctl_calls == [
        ["launchctl", "list", "com.augur.dashboard"],
        ["launchctl", "load", str(plist)],
    ]


def test_stage_full_rebuild_uses_launchd_after_successful_build(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plist = tmp_path / "com.augur.dashboard.plist"
    plist.write_text("<plist />")
    launchctl_calls: list[list[str]] = []

    monkeypatch.setattr(_recovery_mod, "LAUNCHD_DASHBOARD_PLIST", plist)
    monkeypatch.setattr(_recovery_mod, "LAUNCHD_DASHBOARD_LABEL", "com.augur.dashboard")
    monkeypatch.setattr(_recovery_mod.sys, "platform", "darwin")
    monkeypatch.setattr(_recovery_mod, "run_npm_command", lambda *_args, **_kwargs: (True, ""))
    monkeypatch.setattr(_recovery_mod.time, "sleep", lambda _seconds: None)
    running_states = iter([False, True])
    monkeypatch.setattr(_recovery_mod, "is_dashboard_running", lambda: next(running_states))

    def _run(command: list[str], **_kwargs):
        launchctl_calls.append(command)
        if command[:3] == ["launchctl", "list", "com.augur.dashboard"]:
            return CompletedProcess(command, 1, stdout="", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(_recovery_mod, "_run_command", _run)
    monkeypatch.setattr(
        _recovery_mod,
        "_popen_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stage_full_rebuild should use launchd when available")
        ),
    )

    assert _recovery_mod.stage_full_rebuild() is True
    assert launchctl_calls == [
        ["launchctl", "list", "com.augur.dashboard"],
        ["launchctl", "load", str(plist)],
    ]


def test_stage_clear_cache_removes_symlinked_next_cache(monkeypatch, tmp_path: Path) -> None:
    dashboard_dir = tmp_path / "dashboard"
    dashboard_dir.mkdir()
    cache_dir = tmp_path / "cache" / "next"
    cache_dir.mkdir(parents=True)
    marker = cache_dir / "stale.txt"
    marker.write_text("stale cache\n", encoding="utf-8")
    next_link = dashboard_dir / ".next"
    next_link.symlink_to(cache_dir, target_is_directory=True)

    monkeypatch.setattr(_recovery_mod, "is_rebuild_in_progress", lambda: False)
    monkeypatch.setattr(_recovery_mod, "get_dashboard_dir", lambda: dashboard_dir)
    monkeypatch.setattr(_recovery_mod, "stage_restart", lambda: True)

    assert _recovery_mod.stage_clear_cache() is True
    assert not marker.exists()
    assert not next_link.exists()


def test_check_and_recover_refreshes_status_after_success(monkeypatch) -> None:
    status_calls = iter(
        [
            {
                "running": False,
                "healthy": False,
                "http_status": None,
                "pids": [],
                "rebuild_in_progress": False,
                "checked_at": "before",
                "mode": "production",
            },
            {
                "running": True,
                "healthy": True,
                "http_status": 200,
                "pids": [12345],
                "rebuild_in_progress": False,
                "checked_at": "after",
                "mode": "production",
            },
        ]
    )
    written_status: dict = {}
    reset_calls: list[bool] = []

    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: next(status_calls))
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "run_recovery", lambda: (True, "full_rebuild", 1.5))
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda status: written_status.update(status))
    monkeypatch.setattr(_process_mod, "reset_runtime_incident_cursor", lambda: reset_calls.append(True))
    monkeypatch.setattr(_process_mod, "detect_runtime_incident", lambda: None)
    monkeypatch.setattr(_process_mod, "is_build_process_running", lambda: False)
    monkeypatch.setattr(_process_mod, "detect_fatal_build_errors", lambda: None)
    # Reset global state
    monkeypatch.setattr(_process_mod, "_first_down_at", None)
    monkeypatch.setattr(_process_mod, "_consecutive_http_failures", 0)
    if _base_mod.dashboard_lifecycle is not None:
        monkeypatch.setattr(_base_mod.dashboard_lifecycle, "is_crash_loop", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(
            _base_mod.dashboard_lifecycle,
            "request_action",
            lambda *_args, **_kwargs: {"decision": "granted", "reason": "test"},
        )
        monkeypatch.setattr(
            _base_mod.dashboard_lifecycle,
            "log_event",
            lambda *_args, **_kwargs: None,
        )
        # Keep the test hermetic: never read the real machine's lifecycle gate
        monkeypatch.setattr(
            _base_mod.dashboard_lifecycle,
            "get_state",
            lambda *_args, **_kwargs: {"state": "stopped", "owner": None},
        )
        monkeypatch.setattr(
            _base_mod.dashboard_lifecycle,
            "record_crash",
            lambda *_args, **_kwargs: None,
        )
    # Also patch lifecycle ref used in process module
    if _process_mod.dashboard_lifecycle is not None:
        monkeypatch.setattr(_process_mod.dashboard_lifecycle, "is_crash_loop", lambda *_args, **_kwargs: False)
        monkeypatch.setattr(
            _process_mod.dashboard_lifecycle,
            "request_action",
            lambda *_args, **_kwargs: {"decision": "granted", "reason": "test"},
        )
        monkeypatch.setattr(
            _process_mod.dashboard_lifecycle,
            "log_event",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            _process_mod.dashboard_lifecycle,
            "get_state",
            lambda *_args, **_kwargs: {"state": "stopped", "owner": None},
        )
        monkeypatch.setattr(
            _process_mod.dashboard_lifecycle,
            "record_crash",
            lambda *_args, **_kwargs: None,
        )

    status = dashboard_monitor.check_and_recover()

    assert status["running"] is True
    assert status["pids"] == [12345]
    assert status["action"] == "recovered_full_rebuild"
    assert status["recovery_duration"] == 1.5
    assert written_status["running"] is True
    assert reset_calls == [True]


def test_check_and_recover_detects_unhealthy_server(monkeypatch) -> None:
    """Running server returning 500 triggers recovery after threshold."""
    unhealthy_status = {
        "running": True,
        "healthy": False,
        "http_status": 500,
        "pids": ["99999"],
        "rebuild_in_progress": False,
        "checked_at": "now",
        "mode": "production",
    }
    recovered_status = {
        "running": True,
        "healthy": True,
        "http_status": 200,
        "pids": ["99998"],
        "rebuild_in_progress": False,
        "checked_at": "after",
        "mode": "production",
    }
    call_count = {"get_status": 0}

    def mock_get_status():
        call_count["get_status"] += 1
        # First 3 calls return unhealthy, then recovered
        if call_count["get_status"] <= 3:
            return dict(unhealthy_status)
        return dict(recovered_status)

    monkeypatch.setattr(_process_mod, "get_dashboard_status", mock_get_status)
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "stage_clear_cache", lambda: True)
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda _status: None)
    monkeypatch.setattr(_process_mod, "detect_runtime_incident", lambda: None)
    monkeypatch.setattr(_process_mod, "_consecutive_http_failures", 0)

    # Suppress os.kill since PID 99999 doesn't exist
    monkeypatch.setattr("os.kill", lambda *_args: None)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    # First two calls should just increment the counter
    status1 = dashboard_monitor.check_and_recover()
    assert status1["action"] == "none"
    assert _process_mod._consecutive_http_failures == 1

    status2 = dashboard_monitor.check_and_recover()
    assert status2["action"] == "none"
    assert _process_mod._consecutive_http_failures == 2

    # Third call hits the threshold and triggers recovery
    status3 = dashboard_monitor.check_and_recover()
    assert status3["action"] == "recovered_clear_cache_unhealthy"
    assert _process_mod._consecutive_http_failures == 0


def test_check_and_recover_detects_runtime_timeout_cluster(monkeypatch, tmp_path: Path) -> None:
    """A process that still serves `/` but is timing out internally should recover."""
    status = {
        "running": True,
        "healthy": True,
        "http_status": 200,
        "pids": ["99999"],
        "rebuild_in_progress": False,
        "checked_at": "now",
        "mode": "production",
    }
    stderr_log = tmp_path / "dashboard.stderr.log"
    stderr_log.write_text(
        "\n".join(
            [
                "[API Error] POST /api/mcp/context/preload Request 49 timed out after 60000ms",
                "[API Error] POST /api/mcp/context/switch Request 50 timed out after 60000ms",
                "[API Error] GET /api/registry Request 51 timed out after 60000ms",
            ]
        )
    )

    monkeypatch.setattr(_health_mod, "DASHBOARD_STDERR_LOG", stderr_log)
    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: dict(status))
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "stage_clear_cache", lambda: True)
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda _status: None)
    monkeypatch.setattr(_process_mod, "_consecutive_http_failures", 2)
    monkeypatch.setattr(_health_mod, "_runtime_incident_log_path", None)
    monkeypatch.setattr(_health_mod, "_runtime_incident_offset", 0)
    monkeypatch.setattr("os.kill", lambda *_args: None)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    result = dashboard_monitor.check_and_recover()
    assert result["action"] == "recovered_clear_cache_unhealthy"
    assert result["runtime_incident"]["timeout_count"] == 3


def test_check_and_recover_does_not_count_build_lock_compile_as_crash(monkeypatch) -> None:
    status = {
        "running": False,
        "healthy": False,
        "http_status": None,
        "pids": [],
        "rebuild_in_progress": False,
        "checked_at": "now",
        "mode": "production",
    }
    crash_calls: list[tuple[str, str]] = []
    health_events: list[tuple[str, str, str]] = []

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {"state": "compiling", "owner": "build_lock"}

        @staticmethod
        def record_crash(actor: str, reason: str, **_kwargs) -> None:
            crash_calls.append((actor, reason))

        @staticmethod
        def log_event(actor: str, action: str, reason: str, **_extra) -> None:
            health_events.append((actor, action, reason))

    monkeypatch.setattr(_process_mod, "dashboard_lifecycle", FakeLifecycle)
    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: dict(status))
    monkeypatch.setattr(_process_mod, "is_build_process_running", lambda: False)
    monkeypatch.setattr(_process_mod, "is_rebuild_in_progress", lambda: False)
    monkeypatch.setattr(_process_mod, "detect_runtime_incident", lambda: None)
    monkeypatch.setattr(_process_mod, "detect_fatal_build_errors", lambda: None)
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: False)
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda _status: None)
    monkeypatch.setattr(_process_mod, "_first_down_at", None)

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "skipped_build_lock"
    assert crash_calls == []
    assert health_events == [
        (
            "dashboard_monitor",
            "health_check",
            "build lock owns dashboard compile; waiting for build release",
        )
    ]


def test_check_and_recover_does_not_double_count_known_down_lifecycle_state(monkeypatch) -> None:
    status = {
        "running": False,
        "healthy": False,
        "http_status": None,
        "pids": [],
        "rebuild_in_progress": False,
        "checked_at": "now",
        "mode": "production",
    }
    crash_calls: list[tuple[str, str]] = []

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {"state": "crashed", "owner": None}

        @staticmethod
        def record_crash(actor: str, reason: str, **_kwargs) -> None:
            crash_calls.append((actor, reason))

        @staticmethod
        def is_crash_loop(*_args, **_kwargs) -> bool:
            return False

        @staticmethod
        def request_action(*_args, **_kwargs) -> dict:
            return {"decision": "denied", "reason": "test stops before recovery"}

    monkeypatch.setattr(_process_mod, "dashboard_lifecycle", FakeLifecycle)
    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: dict(status))
    monkeypatch.setattr(_process_mod, "is_build_process_running", lambda: False)
    monkeypatch.setattr(_process_mod, "is_rebuild_in_progress", lambda: False)
    monkeypatch.setattr(_process_mod, "detect_runtime_incident", lambda: None)
    monkeypatch.setattr(_process_mod, "detect_fatal_build_errors", lambda: None)
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "write_status", lambda _status: None)
    monkeypatch.setattr(_process_mod, "_first_down_at", None)

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "gate_denied"
    assert crash_calls == []


def test_check_and_recover_deduplicates_stale_runtime_incident(monkeypatch, tmp_path: Path) -> None:
    """The same stderr incident should not keep escalating on every poll."""
    status = {
        "running": True,
        "healthy": True,
        "http_status": 200,
        "pids": ["99999"],
        "rebuild_in_progress": False,
        "checked_at": "now",
        "mode": "production",
    }
    stderr_log = tmp_path / "dashboard.stderr.log"
    stderr_log.write_text(
        "\n".join(
            [
                "[API Error] POST /api/mcp/context/preload Request 49 timed out after 60000ms",
                "[API Error] POST /api/mcp/context/switch Request 50 timed out after 60000ms",
                "[API Error] GET /api/registry Request 51 timed out after 60000ms",
            ]
        )
    )

    written_status: dict = {}
    monkeypatch.setattr(_health_mod, "DASHBOARD_STDERR_LOG", stderr_log)
    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: dict(status))
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda current: written_status.update(current))
    monkeypatch.setattr(_process_mod, "_consecutive_http_failures", 0)
    monkeypatch.setattr(_process_mod, "_last_runtime_incident_signature", None)
    monkeypatch.setattr(_health_mod, "_runtime_incident_log_path", None)
    monkeypatch.setattr(_health_mod, "_runtime_incident_offset", 0)

    dashboard_monitor.check_and_recover()
    assert _process_mod._consecutive_http_failures == 1

    second = dashboard_monitor.check_and_recover()
    assert second["action"] == "none"
    assert "runtime_incident" not in second
    assert _process_mod._consecutive_http_failures == 0


# ---------------------------------------------------------------------------
# Gate-aware heal: never race an agent-driven restart (2026-06-11 regression).
# A scoped stop releases the gate to 'stopped' moments before the agent's own
# start; the gate GRANTS a monitor restart in that window, so monitor and
# build engine both spawned dev servers (Next's dev-singleton lock aborted the
# loser, stranding its wrapper chain as zombies).
# ---------------------------------------------------------------------------

_DOWN_STATUS = {
    "running": False,
    "healthy": False,
    "http_status": None,
    "pids": [],
    "rebuild_in_progress": False,
    "checked_at": "now",
    "mode": "production",
}


def _patch_down_cycle(monkeypatch, fake_lifecycle) -> dict:
    """Patch the standard seams for a 'dashboard is down' check_and_recover run."""
    written_status: dict = {}
    monkeypatch.setattr(_process_mod, "dashboard_lifecycle", fake_lifecycle)
    monkeypatch.setattr(_process_mod, "get_dashboard_status", lambda: dict(_DOWN_STATUS))
    monkeypatch.setattr(_process_mod, "is_build_process_running", lambda: False)
    monkeypatch.setattr(_process_mod, "is_rebuild_in_progress", lambda: False)
    monkeypatch.setattr(_process_mod, "detect_runtime_incident", lambda: None)
    monkeypatch.setattr(_process_mod, "detect_fatal_build_errors", lambda: None)
    monkeypatch.setattr(_process_mod, "is_production_mode", lambda: True)
    monkeypatch.setattr(_process_mod, "notify", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_process_mod, "write_status", lambda status: written_status.update(status))
    monkeypatch.setattr(_process_mod, "reset_runtime_incident_cursor", lambda: None)
    monkeypatch.setattr(_process_mod, "_first_down_at", None)
    monkeypatch.setattr(_process_mod, "_consecutive_http_failures", 0)
    monkeypatch.setattr(_process_mod, "_recovery_abandoned", False)
    monkeypatch.setattr(_process_mod, "_crash_loop_cycles", 0)
    return written_status


def _no_recovery(monkeypatch) -> None:
    monkeypatch.setattr(
        _process_mod,
        "run_recovery",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("monitor must not run recovery while an agent restart is in flight")
        ),
    )


def test_check_and_recover_skips_heal_while_gate_starting(monkeypatch) -> None:
    """Gate 'starting' (another actor mid-start, within TTL) → skip heal cycle."""
    from datetime import datetime as _dt

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {
                "state": "starting",
                "owner": "agent:aug-dev-build",
                "owner_since": _dt.now().isoformat(),
            }

        @staticmethod
        def record_crash(*_args, **_kwargs) -> None:
            pass

        @staticmethod
        def request_action(*_args, **_kwargs) -> dict:
            raise AssertionError("monitor must not reach the gate while a start is in flight")

        @staticmethod
        def is_crash_loop(*_args, **_kwargs) -> bool:
            return False

    _patch_down_cycle(monkeypatch, FakeLifecycle)
    _no_recovery(monkeypatch)

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "skipped_agent_restart_in_flight"


def test_agent_restart_in_flight_ignores_stale_starting_owner(monkeypatch) -> None:
    """A starter that died mid-start (TTL expired) must not stall healing forever."""
    from datetime import datetime as _dt, timedelta as _td

    class FakeLifecycle:
        TRANSIENT_STATE_TTL_SECONDS = 60

        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {
                "state": "starting",
                "owner": "agent:aug-dev-build",
                "owner_since": (_dt.now() - _td(seconds=120)).isoformat(),
            }

    monkeypatch.setattr(_process_mod, "dashboard_lifecycle", FakeLifecycle)

    assert _process_mod._agent_restart_in_flight() is None


def test_check_and_recover_skips_heal_within_grace_after_stop(monkeypatch) -> None:
    """Gate released to 'stopped' seconds ago (agent stop+start in flight) → skip."""
    from datetime import datetime as _dt, timedelta as _td

    crash_calls: list[tuple] = []

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {
                "state": "stopped",
                "owner": None,
                "stopped_at": (_dt.now() - _td(seconds=5)).isoformat(),
            }

        @staticmethod
        def record_crash(*args, **_kwargs) -> None:
            crash_calls.append(args)

        @staticmethod
        def request_action(*_args, **_kwargs) -> dict:
            raise AssertionError(
                "monitor must not request a restart inside the post-stop grace window"
            )

        @staticmethod
        def is_crash_loop(*_args, **_kwargs) -> bool:
            return False

    _patch_down_cycle(monkeypatch, FakeLifecycle)
    _no_recovery(monkeypatch)

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "skipped_agent_restart_in_flight"
    assert crash_calls == []  # 'stopped' is a known-down state, no duplicate crash


def test_check_and_recover_heals_after_grace_window(monkeypatch) -> None:
    """A dashboard left 'stopped' beyond the grace window is healed normally."""
    from datetime import datetime as _dt, timedelta as _td

    gate_requests: list[tuple] = []

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {
                "state": "stopped",
                "owner": None,
                "stopped_at": (
                    _dt.now() - _td(seconds=_process_mod.AGENT_RESTART_GRACE_SECONDS + 90)
                ).isoformat(),
            }

        @staticmethod
        def record_crash(*_args, **_kwargs) -> None:
            pass

        @staticmethod
        def request_action(*args, **_kwargs) -> dict:
            gate_requests.append(args)
            return {"decision": "granted", "reason": "test"}

        @staticmethod
        def is_crash_loop(*_args, **_kwargs) -> bool:
            return False

        @staticmethod
        def log_event(*_args, **_kwargs) -> None:
            pass

    _patch_down_cycle(monkeypatch, FakeLifecycle)
    monkeypatch.setattr(_process_mod, "run_recovery", lambda: (True, "restart", 1.0))

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "recovered_restart"
    assert gate_requests == [("dashboard_monitor", "restart", "auto-recovery")]


def test_check_and_recover_heals_on_genuine_crash(monkeypatch) -> None:
    """A genuine crash (gate 'crashed', no recent stop) still heals immediately."""
    gate_requests: list[tuple] = []

    class FakeLifecycle:
        @staticmethod
        def get_state(*_args, **_kwargs) -> dict:
            return {"state": "crashed", "owner": None, "stopped_at": None}

        @staticmethod
        def record_crash(*_args, **_kwargs) -> None:
            pass

        @staticmethod
        def request_action(*args, **_kwargs) -> dict:
            gate_requests.append(args)
            return {"decision": "granted", "reason": "test"}

        @staticmethod
        def is_crash_loop(*_args, **_kwargs) -> bool:
            return False

        @staticmethod
        def log_event(*_args, **_kwargs) -> None:
            pass

    _patch_down_cycle(monkeypatch, FakeLifecycle)
    monkeypatch.setattr(_process_mod, "run_recovery", lambda: (True, "restart", 1.0))

    result = dashboard_monitor.check_and_recover()

    assert result["action"] == "recovered_restart"
    assert gate_requests == [("dashboard_monitor", "restart", "auto-recovery")]


def test_detect_runtime_incident_ignores_historical_live_log_backlog(monkeypatch, tmp_path: Path) -> None:
    stderr_log = tmp_path / "dashboard.stderr.log"
    stderr_log.write_text(
        "\n".join(
            [
                "[API Error] POST /api/mcp/context/preload Request 49 timed out after 60000ms",
                "[API Error] POST /api/mcp/context/switch Request 50 timed out after 60000ms",
                "[API Error] GET /api/registry Request 51 timed out after 60000ms",
            ]
        )
    )

    monkeypatch.setattr(_health_mod, "DASHBOARD_STDERR_LOG", stderr_log)
    monkeypatch.setattr(_health_mod, "_runtime_incident_log_path", str(stderr_log))
    monkeypatch.setattr(_health_mod, "_runtime_incident_offset", stderr_log.stat().st_size)

    stderr_log.write_text(
        stderr_log.read_text() + "\n[MCPBridge] Server warning: unrelated fresh warning\n"
    )

    result = dashboard_monitor.detect_runtime_incident()

    assert result is None
