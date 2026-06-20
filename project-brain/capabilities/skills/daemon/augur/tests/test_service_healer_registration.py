from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def _shared_daemon_root(project_root: Path) -> Path:
    return project_root / "project-brain" / "capabilities" / "skills" / "daemon"


def test_service_label_and_task_name_are_project_scoped():
    import service_healer

    with patch.object(service_healer, "get_project_name", return_value="AugurOS"):
        assert service_healer._service_label() == "com.auguros.daemon"
        assert service_healer._task_name() == "com.auguros.daemon"
        assert service_healer._plist_filename() == "com.auguros.daemon.plist"


def test_build_registration_spec_windows_uses_repo_venv_and_daemon_supervisor(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()
    logs_dir.mkdir()

    with (
        patch.object(service_healer, "get_logs_dir", return_value=logs_dir),
        patch.object(service_healer, "_service_label", return_value="com.augur.daemon"),
    ):
        spec = service_healer._build_registration_spec(
            "daemon",
            project_root,
            platform_name="win32",
        )

    assert spec.label == "com.augur.daemon"
    assert spec.task_name == "com.augur.daemon"
    assert spec.plist_name == "com.augur.daemon.plist"
    assert spec.working_dir == project_root
    assert (
        spec.daemon_script
        == _shared_daemon_root(project_root) / "scripts" / "daemon_supervisor.py"
    )
    # Windows launches the daemon via pythonw.exe (GUI subsystem) so no console
    # window appears at logon. python.exe would pop a visible command window.
    assert spec.python_path == project_root / ".venv" / "Scripts" / "pythonw.exe"
    assert spec.stdout_path == logs_dir / "daemon.stdout.log"
    assert spec.stderr_path == logs_dir / "daemon.stderr.log"


def test_render_windows_task_xml_includes_logon_trigger_restart_and_working_directory(
    tmp_path,
):
    import service_healer

    project_root = tmp_path / "repo root"
    daemon_root = _shared_daemon_root(project_root)
    daemon_script = daemon_root / "scripts" / "unified_daemon.py"
    spec = service_healer.DaemonRegistrationSpec(
        label="com.augur.daemon",
        plist_name="com.augur.daemon.plist",
        task_name="com.augur.daemon",
        working_dir=project_root,
        daemon_script=daemon_script,
        python_path=project_root / ".venv" / "Scripts" / "pythonw.exe",
        macos_app_executable=daemon_root
        / "assets"
        / "bundle"
        / "Augur Daemon.app"
        / "Contents"
        / "MacOS"
        / "Augur",
        stdout_path=tmp_path / "logs" / "daemon.stdout.log",
        stderr_path=tmp_path / "logs" / "daemon.stderr.log",
    )

    xml = service_healer._render_windows_task_xml(spec, user_id="tester")

    assert "<LogonTrigger>" in xml
    assert "<Command>" in xml and "pythonw.exe" in xml
    assert "<Arguments>" in xml and f'"{daemon_script}"' in xml
    assert "<WorkingDirectory>" in xml
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
    assert "<RestartOnFailure>" in xml
    assert "<EnvironmentVariables>" not in xml


@patch("sys.platform", "win32")
def test_install_services_windows_uses_task_scheduler_backend():
    import service_healer

    with (
        patch.object(service_healer, "get_project_root", return_value=Path("/repo")),
        patch.object(
            service_healer, "_register_windows_task", return_value=True
        ) as register,
        patch.object(
            service_healer,
            "_build_registration_spec",
            return_value=service_healer.DaemonRegistrationSpec(
                label="com.augur.daemon",
                plist_name="com.augur.daemon.plist",
                task_name="com.augur.daemon",
                working_dir=Path("/repo"),
                daemon_script=Path(
                    "/repo/project-brain/capabilities/skills/daemon/scripts/unified_daemon.py"
                ),
                python_path=Path("/repo/.venv/Scripts/python.exe"),
                macos_app_executable=Path(
                    "/repo/project-brain/capabilities/skills/daemon/assets/bundle/Augur Daemon.app/Contents/MacOS/Augur"
                ),
                stdout_path=Path("/logs/daemon.stdout.log"),
                stderr_path=Path("/logs/daemon.stderr.log"),
            ),
        ),
        patch.object(
            service_healer, "_start_windows_task", return_value={"status": "started"}
        ) as start,
    ):
        result = service_healer.install_services()

    assert result["daemon"] == "running"
    register.assert_called_once_with("daemon", Path("/repo"))
    start.assert_called_once_with("com.augur.daemon")


@patch("sys.platform", "win32")
def test_heal_service_windows_uses_windows_backend():
    import service_healer

    with patch.object(
        service_healer, "_heal_windows_service", return_value=True
    ) as heal:
        assert service_healer.heal_service_if_needed("daemon") is True

    heal.assert_called_once_with("daemon")


@patch("sys.platform", "win32")
def test_cleanup_legacy_services_windows_removes_old_nightly_task():
    import service_healer

    with patch.object(
        service_healer,
        "_unregister_windows_task",
        return_value={"status": "uninstalled"},
    ) as unregister:
        result = service_healer.cleanup_legacy_services()

    assert result["nightly_windows_task"] == "removed"
    unregister.assert_called_once_with("Augur Nightly Maintenance")


@patch("sys.platform", "win32")
def test_cleanup_legacy_services_windows_surfaces_task_delete_errors():
    import service_healer

    with patch.object(
        service_healer,
        "_unregister_windows_task",
        return_value={"status": "error", "detail": "ERROR: Access is denied."},
    ) as unregister:
        result = service_healer.cleanup_legacy_services()

    assert result["nightly_windows_task"] == "error: ERROR: Access is denied."
    unregister.assert_called_once_with("Augur Nightly Maintenance")


def test_unregister_windows_task_distinguishes_not_found_from_scheduler_errors():
    import service_healer

    with patch.object(
        service_healer,
        "_run_command",
        return_value=CompletedProcess(
            args=["schtasks"],
            returncode=1,
            stdout="",
            stderr="ERROR: Access is denied.",
        ),
    ):
        result = service_healer._unregister_windows_task("Augur Daemon")

    assert result == {"status": "error", "detail": "ERROR: Access is denied."}


def test_read_windows_task_state_uses_numeric_state_output():
    import service_healer

    with patch.object(
        service_healer,
        "_run_command",
        return_value=CompletedProcess(
            args=["powershell"],
            returncode=0,
            stdout="4\n",
            stderr="",
        ),
    ):
        state = service_healer._read_windows_task_state("com.augur.daemon")

    assert state == "running"


def test_query_windows_task_state_reports_disabled_state_separately():
    import service_healer

    with patch.object(
        service_healer,
        "_run_command",
        return_value=CompletedProcess(
            args=["powershell"],
            returncode=0,
            stdout="1\n",
            stderr="",
        ),
    ):
        state = service_healer._query_windows_task_state("com.augur.daemon")

    assert state == {"status": "ok", "state": "disabled"}


def test_query_windows_task_state_treats_missing_task_message_as_not_found():
    import service_healer

    with patch.object(
        service_healer,
        "_run_command",
        return_value=CompletedProcess(
            args=["powershell"],
            returncode=1,
            stdout=(
                "No MSFT_ScheduledTask objects found with property 'TaskName' "
                "equal to 'com.augur.daemon'."
            ),
            stderr="",
        ),
    ):
        state = service_healer._query_windows_task_state("com.augur.daemon")

    assert state == {"status": "not_found"}


@patch("sys.platform", "win32")
def test_collect_windows_status_surfaces_query_errors():
    import service_healer

    def query_state(task_name: str) -> dict[str, str]:
        if task_name == "Augur Nightly Maintenance":
            return {"status": "error", "detail": "scheduler unavailable"}
        return {"status": "error", "detail": "powershell failure"}

    with (
        patch.object(service_healer, "get_project_root", return_value=Path("/repo")),
        patch.object(
            service_healer, "_query_windows_task_state", side_effect=query_state
        ),
    ):
        result = service_healer._collect_windows_status_results(Path("/repo"))

    assert result["daemon"] == "error: powershell failure"
    assert result["legacy_nightly_windows_task"] == "error: scheduler unavailable"


@patch("sys.platform", "win32")
def test_collect_windows_status_reports_disabled_task_without_treating_it_as_installed():
    import service_healer

    def query_state(task_name: str) -> dict[str, str]:
        if task_name == "Augur Nightly Maintenance":
            return {"status": "not_found"}
        return {"status": "ok", "state": "disabled"}

    with (
        patch.object(service_healer, "get_project_root", return_value=Path("/repo")),
        patch.object(
            service_healer, "_query_windows_task_state", side_effect=query_state
        ),
    ):
        result = service_healer._collect_windows_status_results(Path("/repo"))

    assert result["daemon"] == "disabled"
    assert result["legacy_nightly_windows_task"] == "cleaned"


def test_collect_windows_daemon_diagnostics_reports_missing_task(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()

    with (
        patch.object(service_healer, "get_runtime_dir", return_value=runtime_dir),
        patch.object(service_healer, "get_logs_dir", return_value=logs_dir),
        patch.object(
            service_healer,
            "_query_windows_task_state",
            return_value={"status": "not_found"},
        ),
        patch.object(
            service_healer.daemon_diagnostics,
            "collect_path_checks",
            return_value=[],
        ) as collect_path_checks,
    ):
        result = service_healer._collect_windows_daemon_diagnostics(project_root)

    path_checks = collect_path_checks.call_args.args[0]
    assert path_checks["logs"] == logs_dir
    assert path_checks["state"] == runtime_dir
    assert path_checks["locks"] == runtime_dir / "locks"
    assert path_checks["daemon_stderr"] == logs_dir / "daemon" / "stderr"
    assert path_checks["daemon_status"] == runtime_dir / "stats"
    assert result["health"] == "not_installed"
    assert result["task"]["status"] == "not_installed"
    assert "scheduled task is not installed" in result["issues"]
    assert result["status_file"]["status"] == "missing"
    assert result["sidecar"]["status"] in {"missing", "disabled"}
    assert result["sidecar"]["enabled"] is False


def test_collect_windows_daemon_diagnostics_reports_task_path_mismatch(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()
    config_dir = project_root / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "daemon.yaml").write_text(
        "ai_monitor:\n  enabled: true\n", encoding="utf-8"
    )
    expected_status_path = runtime_dir / "stats" / "daemon_status.json"
    expected_status_path.parent.mkdir(parents=True)
    expected_status_path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "daemon_pid": os.getpid(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )

    with (
        patch.object(service_healer, "get_runtime_dir", return_value=runtime_dir),
        patch.object(service_healer, "get_logs_dir", return_value=logs_dir),
        patch.object(
            service_healer,
            "_query_windows_task_state",
            return_value={"status": "ok", "state": "running"},
        ),
        patch.object(
            service_healer,
            "_read_windows_task_details",
            return_value={
                "command": str(project_root / ".venv" / "Scripts" / "python.exe.old"),
                "arguments": f'"{project_root.joinpath("skills", "daemon", "scripts", "unified_daemon.py")}"',
                "working_dir": str(project_root),
            },
        ),
    ):
        result = service_healer._collect_windows_daemon_diagnostics(project_root)

    assert result["health"] == "degraded"
    assert result["task"]["status"] == "mismatch"
    expected_parts = Path(result["task"]["expected"]["command"]).parts
    assert expected_parts[-3:] == (".venv", "Scripts", "pythonw.exe")
    assert "command mismatch" in result["task"]["issues"]


def test_start_windows_task_runs_task_and_waits_until_running():
    import service_healer

    calls: list[list[str]] = []
    states = iter(
        [
            {"status": "ok", "state": "installed"},
            {"status": "ok", "state": "installed"},
            {"status": "ok", "state": "running"},
        ]
    )

    def fake_run(command: list[str], **kwargs):
        calls.append(command)
        return CompletedProcess(args=command, returncode=0, stdout="SUCCESS", stderr="")

    with (
        patch.object(
            service_healer,
            "_query_windows_task_state",
            side_effect=lambda _task: next(states),
        ),
        patch.object(service_healer, "_run_command", side_effect=fake_run),
        patch.object(service_healer.time, "sleep"),
    ):
        result = service_healer._start_windows_task(
            "com.augur.daemon", timeout_seconds=1, poll_interval=0
        )

    assert result == {"status": "started"}
    assert calls == [["schtasks", "/run", "/tn", "com.augur.daemon"]]


def test_start_windows_task_rejects_disabled_task():
    import service_healer

    with (
        patch.object(
            service_healer,
            "_query_windows_task_state",
            return_value={"status": "ok", "state": "disabled"},
        ),
        patch.object(service_healer, "_run_command") as run,
    ):
        result = service_healer._start_windows_task("com.augur.daemon")

    assert result == {"status": "error", "detail": "com.augur.daemon is disabled"}
    run.assert_not_called()


@patch("sys.platform", "win32")
def test_heal_windows_service_starts_existing_stopped_task(tmp_path):
    import service_healer

    spec = service_healer.DaemonRegistrationSpec(
        label="com.augur.daemon",
        plist_name="com.augur.daemon.plist",
        task_name="com.augur.daemon",
        working_dir=tmp_path / "repo",
        daemon_script=_shared_daemon_root(tmp_path / "repo")
        / "scripts"
        / "unified_daemon.py",
        python_path=tmp_path / "repo" / ".venv" / "Scripts" / "python.exe",
        macos_app_executable=_shared_daemon_root(tmp_path / "repo")
        / "assets"
        / "bundle"
        / "Augur Daemon.app"
        / "Contents"
        / "MacOS"
        / "Augur",
        stdout_path=tmp_path / "logs" / "daemon.stdout.log",
        stderr_path=tmp_path / "logs" / "daemon.stderr.log",
    )
    current = {
        "command": str(spec.python_path),
        "arguments": f'"{spec.daemon_script}"',
        "working_dir": str(spec.working_dir),
    }

    with (
        patch.object(service_healer, "get_project_root", return_value=spec.working_dir),
        patch.object(service_healer, "_build_registration_spec", return_value=spec),
        patch.object(
            service_healer, "_read_windows_task_details", return_value=current
        ),
        patch.object(
            service_healer, "_start_windows_task", return_value={"status": "started"}
        ) as start,
    ):
        result = service_healer._heal_windows_service_status("daemon")

    assert result == {"status": "healed"}
    start.assert_called_once_with("com.augur.daemon")


def test_service_results_failed_flags_failed_daemon_status():
    import service_healer

    assert service_healer._service_results_failed({"daemon": "failed"}) is True
    assert (
        service_healer._service_results_failed(
            {"install": {"daemon": "error: access denied"}}
        )
        is True
    )
    assert service_healer._service_results_failed({"daemon": "running"}) is False


@patch("sys.platform", "win32")
def test_heal_all_services_windows_reports_failed_repair_as_error(tmp_path):
    import service_healer

    spec = service_healer.DaemonRegistrationSpec(
        label="com.augur.daemon",
        plist_name="com.augur.daemon.plist",
        task_name="com.augur.daemon",
        working_dir=tmp_path / "repo",
        daemon_script=_shared_daemon_root(tmp_path / "repo")
        / "scripts"
        / "unified_daemon.py",
        python_path=tmp_path / "repo" / ".venv" / "Scripts" / "python.exe",
        macos_app_executable=_shared_daemon_root(tmp_path / "repo")
        / "assets"
        / "bundle"
        / "Augur Daemon.app"
        / "Contents"
        / "MacOS"
        / "Augur",
        stdout_path=tmp_path / "logs" / "daemon.stdout.log",
        stderr_path=tmp_path / "logs" / "daemon.stderr.log",
    )
    current = {
        "command": str(spec.python_path) + ".old",
        "arguments": f'"{spec.daemon_script}"',
        "working_dir": str(spec.working_dir),
    }

    with (
        patch.object(service_healer, "get_project_root", return_value=spec.working_dir),
        patch.object(service_healer, "_build_registration_spec", return_value=spec),
        patch.object(
            service_healer, "_read_windows_task_details", return_value=current
        ),
        patch.object(
            service_healer,
            "_unregister_windows_task",
            return_value={"status": "error", "detail": "access denied"},
        ),
        patch.object(
            service_healer,
            "_check_attention_sync",
            return_value={"skipped": True, "reason": "interval_not_elapsed"},
        ),
        patch.object(service_healer, "_execute_critical_actions", return_value=0),
    ):
        result = service_healer.heal_all_services()

    assert result["daemon"] == "error: access denied"


@patch("sys.platform", "win32")
def test_heal_all_services_windows_contains_exceptions_per_service():
    import service_healer

    with (
        patch.object(
            service_healer,
            "_heal_windows_service_status",
            side_effect=RuntimeError("boom"),
        ),
        patch.object(
            service_healer,
            "_check_attention_sync",
            return_value={"skipped": True, "reason": "interval_not_elapsed"},
        ),
        patch.object(service_healer, "_execute_critical_actions", return_value=0),
    ):
        result = service_healer.heal_all_services()

    assert result["daemon"] == "error: boom"


@patch("sys.platform", "win32")
def test_install_services_windows_contains_exceptions_per_service():
    import service_healer

    with (
        patch.object(service_healer, "get_project_root", return_value=Path("/repo")),
        patch.object(
            service_healer, "_register_windows_task", side_effect=OSError("disk full")
        ),
    ):
        result = service_healer.install_services()

    assert result["daemon"] == "error: disk full"
