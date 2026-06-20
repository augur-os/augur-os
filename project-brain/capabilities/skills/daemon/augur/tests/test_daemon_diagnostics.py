from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

import daemon_diagnostics as diagnostics


def test_default_pid_exists_uses_windows_helper_without_os_kill(monkeypatch):
    seen: list[int] = []

    def fake_windows_pid_exists(pid: int) -> bool:
        seen.append(pid)
        return True

    def fail_os_kill(_pid: int, _signal: int) -> None:
        raise AssertionError("os.kill must not be used for Windows pid checks")

    monkeypatch.setattr(diagnostics.sys, "platform", "win32")
    monkeypatch.setattr(diagnostics, "_windows_pid_exists", fake_windows_pid_exists)
    monkeypatch.setattr(diagnostics.os, "kill", fail_os_kill)

    assert diagnostics._default_pid_exists(1234) is True
    assert seen == [1234]


def test_check_path_writable_reports_permission_error_details(tmp_path, monkeypatch):
    target = tmp_path / "runtime"

    def deny_write(self: Path, *_args, **_kwargs):
        raise PermissionError(13, "Access is denied", str(self))

    monkeypatch.setattr(Path, "write_text", deny_write)

    result = diagnostics.check_path_writable("runtime", target)

    assert result["name"] == "runtime"
    assert result["path"] == str(target)
    assert result["status"] == "error"
    assert result["writable"] is False
    assert result["ok"] is False
    assert result["error_type"] == "PermissionError"
    assert "Access is denied" in result["detail"]


def test_read_daemon_status_file_reports_missing(tmp_path):
    result = diagnostics.read_daemon_status_file(tmp_path / "daemon_status.json")

    assert result["status"] == "missing"
    assert result["fresh"] is False
    assert result["pid_alive"] is False
    assert result["age_seconds"] is None
    assert result["daemon_pid"] is None
    assert result["services"] == {}
    assert "missing" in result["issue"]


def test_read_daemon_status_file_reports_fresh_alive_status_with_age_and_services(tmp_path):
    now = datetime(2026, 5, 6, 8, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        yaml.safe_dump(
            {
                "daemon_pid": 1234,
                "updated_at": (now - timedelta(seconds=12)).isoformat(),
                "services": {
                    "log_monitor": {"state": "running"},
                    "ai_monitor_sidecar": {"state": "scheduled"},
                },
            }
        ),
        encoding="utf-8",
    )

    result = diagnostics.read_daemon_status_file(
        status_path,
        now=now,
        max_age_seconds=90,
        pid_exists=lambda pid: pid == 1234,
    )

    assert result["status"] == "fresh"
    assert result["fresh"] is True
    assert result["pid_alive"] is True
    assert result["age_seconds"] == pytest.approx(12)
    assert result["daemon_pid"] == 1234
    assert result["services"] == {
        "log_monitor": {"state": "running"},
        "ai_monitor_sidecar": {"state": "scheduled"},
    }


def test_read_daemon_status_file_reports_stale_dead_pid(tmp_path):
    now = datetime(2026, 5, 6, 8, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        yaml.safe_dump(
            {
                "daemon_pid": 4321,
                "updated_at": (now - timedelta(minutes=5)).isoformat(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )

    result = diagnostics.read_daemon_status_file(
        status_path,
        now=now,
        max_age_seconds=90,
        pid_exists=lambda _pid: False,
    )

    assert result["status"] == "stale"
    assert result["fresh"] is False
    assert result["pid_alive"] is False
    assert result["age_seconds"] == pytest.approx(300)
    assert any("stale" in issue for issue in result["issues"])
    assert any("pid 4321" in issue for issue in result["issues"])


def test_read_daemon_status_file_reports_fresh_non_integer_pid_as_malformed(tmp_path):
    now = datetime(2026, 5, 6, 8, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        yaml.safe_dump(
            {
                "daemon_pid": "1234",
                "updated_at": (now - timedelta(seconds=12)).isoformat(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )

    result = diagnostics.read_daemon_status_file(
        status_path,
        now=now,
        max_age_seconds=90,
        pid_exists=lambda _pid: True,
    )

    assert result["status"] == "malformed"
    assert result["fresh"] is False
    assert result["pid_alive"] is False
    assert any("daemon_pid" in issue for issue in result["issues"])


def test_read_daemon_status_file_reports_boolean_pid_as_malformed(tmp_path):
    now = datetime(2026, 5, 6, 8, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        yaml.safe_dump(
            {
                "daemon_pid": True,
                "updated_at": (now - timedelta(seconds=12)).isoformat(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )

    result = diagnostics.read_daemon_status_file(
        status_path,
        now=now,
        max_age_seconds=90,
        pid_exists=lambda _pid: True,
    )

    assert result["status"] == "malformed"
    assert result["fresh"] is False
    assert any(
        "daemon_pid" in issue and "bool" in issue and "True" in issue
        for issue in result["issues"]
    )


def test_read_daemon_status_file_reports_malformed(tmp_path):
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text("[", encoding="utf-8")

    result = diagnostics.read_daemon_status_file(status_path)

    assert result["status"] == "malformed"
    assert result["fresh"] is False
    assert result["pid_alive"] is False
    assert result["services"] == {}
    assert "malformed" in result["issue"]


def test_read_ai_monitor_config_reports_error_for_non_mapping_file(tmp_path):
    config_path = tmp_path / "daemon.yaml"
    config_path.write_text("- ai_monitor\n- enabled\n", encoding="utf-8")

    result = diagnostics.read_ai_monitor_config(config_path)

    assert result["status"] == "error"
    assert result["enabled"] is False
    assert result["config_path"] == str(config_path)
    assert result["config"] == {}
    assert "mapping" in result["detail"]


def test_read_ai_monitor_config_reports_disabled_with_config_path(tmp_path):
    config_path = tmp_path / "daemon.yaml"
    config_path.write_text(
        yaml.safe_dump({"ai_monitor": {"enabled": False, "debounce_seconds": 2}}),
        encoding="utf-8",
    )

    result = diagnostics.read_ai_monitor_config(config_path)

    assert result["status"] == "disabled"
    assert result["enabled"] is False
    assert result["config_path"] == str(config_path)
    assert result["detail"] == "ai_monitor.enabled is false"
    assert result["config"]["debounce_seconds"] == 2


def test_collect_self_heal_summary_reads_latest_report(tmp_path):
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    latest = reports_dir / "self-heal-latest.json"
    latest.write_text(
        yaml.safe_dump({"summary": "self-heal finished", "issue_count": 2}),
        encoding="utf-8",
    )

    result = diagnostics.collect_self_heal_summary(tmp_path)

    assert result["status"] == "reported"
    assert result["report_path"] == str(latest)
    assert result["summary"] == "self-heal finished"
    assert result["issue_count"] == 2


def test_collect_self_heal_summary_reports_malformed_for_non_mapping_report(tmp_path):
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    latest = reports_dir / "self-heal-latest.json"
    latest.write_text("[1, 2, 3]", encoding="utf-8")

    result = diagnostics.collect_self_heal_summary(tmp_path)

    assert result["status"] == "malformed"
    assert result["report_path"] == str(latest)
    assert "malformed" in result["summary"]
    assert "mapping" in result["detail"]


def test_collect_self_heal_summary_reports_missing_planned_path(tmp_path):
    report_path = tmp_path / "adaptive" / "reports" / "self-heal-latest.json"

    result = diagnostics.collect_self_heal_summary(tmp_path)

    assert result["status"] == "missing"
    assert result["report_path"] == str(report_path)
    assert "No self-heal report" in result["summary"]


def test_aggregate_health_uses_precollected_inputs_for_planned_task3_call_shape():
    path_result = {
        "name": "runtime",
        "status": "ok",
        "writable": True,
        "ok": True,
    }
    daemon_status = {
        "status": "fresh",
        "fresh": True,
        "issues": [],
    }
    sidecar = {
        "status": "disabled",
        "enabled": False,
        "config_path": "C:\\repo\\config\\system\\daemon.yaml",
    }

    result = diagnostics.aggregate_health(
        task={"status": "not_found", "task_name": "com.augur.daemon"},
        paths=[path_result],
        status_file=daemon_status,
        sidecar=sidecar,
    )

    assert result == {
        "health": "not_installed",
        "issues": ["scheduled task is not installed"],
    }


@pytest.mark.parametrize("task_status", ["disabled", "stopped", "mismatch", "degraded"])
def test_aggregate_health_degrades_for_unhealthy_task_statuses(task_status):
    result = diagnostics.aggregate_health(
        task={"status": task_status, "detail": "task state does not match expected daemon"},
        paths=[{"name": "runtime", "status": "ok", "writable": True, "ok": True}],
        status_file={"status": "fresh", "fresh": True, "issues": []},
        sidecar={"status": "enabled", "enabled": True},
    )

    assert result["health"] == "degraded"
    assert any(task_status in issue for issue in result["issues"])


def test_aggregate_health_degrades_for_critical_child_services():
    result = diagnostics.aggregate_health(
        task={"status": "running"},
        paths=[],
        status_file={
            "status": "fresh",
            "services": {
                "log_monitor": {"state": "critical_failure", "total_restarts": 4},
                "mcp_health_monitor": {"state": "running", "total_restarts": 0},
            },
        },
        sidecar={"status": "disabled"},
    )

    assert result["health"] == "degraded"
    assert result["issues"] == ["child service log_monitor is critical_failure (4 restarts)"]
