# Windows Daemon Self-Heal Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Windows daemon and self-heal status explicit, repairable, and notification-testable without relying on an open terminal as proof of daemon health.

**Architecture:** Add a focused daemon diagnostics helper and wire it into `service_healer.py`, `unified_daemon.py`, and notification test surfaces. Keep Task Scheduler as the Windows OS manager, keep `unified_daemon.py` as the supervisor, and leave `ai_monitor.enabled` disabled unless config already enables it.

**Tech Stack:** Python 3.12, pytest, Windows Task Scheduler via `schtasks` and PowerShell, JSON/YAML runtime state, existing Augur path helpers.

---

## File Structure

- Modify: `src/logging/config.py`
  - Responsibility: logger setup must degrade to console logging when entity log directories are not writable.
- Create: `skills/daemon/scripts/daemon_diagnostics.py`
  - Responsibility: pure diagnostics for runtime path writability, daemon status file freshness, AI monitor sidecar config, self-heal report summary, and health aggregation.
- Modify: `skills/daemon/scripts/service_healer.py`
  - Responsibility: Windows status/heal/install uses diagnostics and reports exact OS registration/runtime evidence.
- Modify: `skills/daemon/scripts/unified_daemon.py`
  - Responsibility: status output distinguishes missing, stale, fresh, malformed, and stopped daemon states.
- Modify: `skills/daemon/scripts/notification_service.py`
  - Responsibility: Windows notification self-test reports which backend succeeded or failed.
- Modify: `skills/daemon/scripts/mcp/_notifications.py`
  - Responsibility: MCP `send-test-notification` includes notification backend details.
- Modify: `tests/test_logging.py`
  - Responsibility: regression coverage for logging fallback.
- Create: `skills/daemon/augur/tests/test_daemon_diagnostics.py`
  - Responsibility: fast pure tests for diagnostics behavior.
- Modify: `skills/daemon/augur/tests/test_service_healer_registration.py`
  - Responsibility: Windows Task Scheduler diagnostics and heal/status integration tests.
- Modify: `skills/daemon/augur/tests/test_unified_daemon.py`
  - Responsibility: daemon status CLI behavior for missing/stale/fresh status files.
- Modify: `skills/daemon/augur/tests/test_notification_service.py`
  - Responsibility: notification backend reporting tests.

## Task 1: Logger Fallback For Status Commands

**Files:**
- Modify: `src/logging/config.py`
- Modify: `tests/test_logging.py`

- [ ] **Step 1: Write the failing logging fallback test**

Append this test to `tests/test_logging.py`:

```python
def test_entity_logger_falls_back_to_console_when_log_dir_unwritable(monkeypatch):
    """Logger construction must not crash status commands when logs are unwritable."""
    import logging

    from src.logging.config import EntityLogger

    def deny_log_dir(self):
        raise PermissionError("[WinError 5] Access is denied: 'C:\\\\Users\\\\intel\\\\AppData\\\\Local\\\\Augur\\\\logs\\\\service_healer'")  # audit-ignore: illustrative Windows path in archived ADR

    monkeypatch.setattr(EntityLogger, "_get_log_dir", deny_log_dir)

    entity_logger = EntityLogger("service_healer")
    logger = entity_logger.get_logger()

    assert entity_logger.log_dir is None
    assert "Access is denied" in (entity_logger.file_logging_error or "")
    assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
```

- [ ] **Step 2: Run the failing logging test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_logging.py::test_entity_logger_falls_back_to_console_when_log_dir_unwritable -q
```

Expected: FAIL because `EntityLogger.__init__` currently lets `_get_log_dir()` raise before console logging is configured.

- [ ] **Step 3: Implement console-only fallback**

In `src/logging/config.py`, replace `EntityLogger.__init__` with:

```python
    def __init__(self, entity_name: str, log_level: str = "INFO"):
        """
        Initialize entity logger.

        Args:
            entity_name: Name of entity (e.g., "cli", "mcp", "skills/careers")
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.entity_name = entity_name
        self.log_level = log_level
        self.log_dir: Path | None = None
        self.file_logging_error: str | None = None
        try:
            self.log_dir = self._get_log_dir()
        except (OSError, PermissionError) as exc:
            self.file_logging_error = str(exc)
        self._setup_logger()
```

Then in `_setup_logger`, before `pid = _PID`, add:

```python
        if self.file_logging_error:
            file_handler_failures = [f"log-dir: {self.file_logging_error}"]
        else:
            file_handler_failures = []
```

Replace the existing line:

```python
        file_handler_failures: list[str] = []
```

with no line, because the list is now initialized before handlers are attached.

Wrap the main/error/tools file handler attachment blocks so they only run when `self.file_logging_error is None`:

```python
        if self.file_logging_error is None:
            _attach_handler(_make_main_handler, label="main-log")
```

```python
        if self.file_logging_error is None:
            _attach_handler(_make_error_handler, label="error-log")
```

```python
            if self.file_logging_error is None:
                _attach_handler(_make_tools_handler, label="tools-log")
```

- [ ] **Step 4: Run logging tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_logging.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit logging fallback**

```powershell
git add src\logging\config.py tests\test_logging.py
git -c user.name="Codex" -c user.email="codex@openai.com" commit -m "fix(logging): keep status commands alive without writable logs"
```

## Task 2: Add Pure Daemon Diagnostics

**Files:**
- Create: `skills/daemon/scripts/daemon_diagnostics.py`
- Create: `skills/daemon/augur/tests/test_daemon_diagnostics.py`

- [ ] **Step 1: Write failing diagnostics tests**

Create `skills/daemon/augur/tests/test_daemon_diagnostics.py`:

```python
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def test_check_path_writable_reports_permission_error(tmp_path):
    import daemon_diagnostics

    target = tmp_path / "logs"

    with patch.object(Path, "mkdir", side_effect=PermissionError("access denied")):
        result = daemon_diagnostics.check_path_writable("logs", target)

    assert result["name"] == "logs"
    assert result["path"] == str(target)
    assert result["ok"] is False
    assert "access denied" in result["detail"]


def test_read_daemon_status_file_reports_missing(tmp_path):
    import daemon_diagnostics

    result = daemon_diagnostics.read_daemon_status_file(tmp_path / "missing.json")

    assert result["status"] == "missing"
    assert result["fresh"] is False
    assert result["pid_alive"] is False


def test_read_daemon_status_file_reports_fresh_alive_status(tmp_path):
    import daemon_diagnostics

    status_path = tmp_path / "daemon_status.json"
    now = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    status_path.write_text(
        json.dumps(
            {
                "daemon_pid": 1234,
                "updated_at": now.isoformat(),
                "services": {"log_monitor": {"state": "running", "pid": 88}},
            }
        ),
        encoding="utf-8",
    )

    result = daemon_diagnostics.read_daemon_status_file(
        status_path,
        now=now + timedelta(seconds=30),
        max_age_seconds=90,
        pid_exists=lambda pid: pid == 1234,
    )

    assert result["status"] == "fresh"
    assert result["fresh"] is True
    assert result["age_seconds"] == 30
    assert result["pid_alive"] is True
    assert result["services"]["log_monitor"]["state"] == "running"


def test_read_daemon_status_file_reports_stale_dead_pid(tmp_path):
    import daemon_diagnostics

    status_path = tmp_path / "daemon_status.json"
    updated = datetime(2026, 5, 6, 9, 55, tzinfo=timezone.utc)
    status_path.write_text(
        json.dumps({"daemon_pid": 1234, "updated_at": updated.isoformat(), "services": {}}),
        encoding="utf-8",
    )

    result = daemon_diagnostics.read_daemon_status_file(
        status_path,
        now=datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc),
        max_age_seconds=90,
        pid_exists=lambda _pid: False,
    )

    assert result["status"] == "stale"
    assert result["fresh"] is False
    assert result["age_seconds"] == 300
    assert result["pid_alive"] is False


def test_read_ai_monitor_config_reports_disabled_with_path(tmp_path):
    import daemon_diagnostics

    config_path = tmp_path / "daemon.yaml"
    config_path.write_text(yaml.safe_dump({"ai_monitor": {"enabled": False}}), encoding="utf-8")

    result = daemon_diagnostics.read_ai_monitor_config(config_path)

    assert result == {
        "status": "disabled",
        "enabled": False,
        "config_path": str(config_path),
        "detail": "ai_monitor.enabled is false",
    }


def test_collect_self_heal_summary_reads_latest_report(tmp_path):
    import daemon_diagnostics

    report_dir = tmp_path / "adaptive" / "reports"
    report_dir.mkdir(parents=True)
    report = report_dir / "self-heal-latest.json"
    report.write_text(json.dumps({"summary": "clean", "issues": []}), encoding="utf-8")

    result = daemon_diagnostics.collect_self_heal_summary(tmp_path)

    assert result["status"] == "reported"
    assert result["report_path"] == str(report)
    assert result["summary"] == "clean"


def test_aggregate_health_marks_missing_task_as_not_installed():
    import daemon_diagnostics

    result = daemon_diagnostics.aggregate_health(
        task={"status": "not_installed"},
        paths=[{"ok": True}],
        status_file={"status": "missing", "fresh": False},
        sidecar={"status": "disabled"},
    )

    assert result["health"] == "not_installed"
    assert "scheduled task is not installed" in result["issues"]
```

- [ ] **Step 2: Run the failing diagnostics tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_daemon_diagnostics.py -q
```

Expected: FAIL because `daemon_diagnostics.py` does not exist.

- [ ] **Step 3: Create diagnostics helper**

Create `skills/daemon/scripts/daemon_diagnostics.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError):
        return False
    return True


def check_path_writable(name: str, path: Path) -> dict[str, Any]:
    probe = path / ".augur-write-test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"name": name, "path": str(path), "ok": True, "detail": ""}
    except Exception as exc:
        try:
            probe.unlink(missing_ok=True)
        except Exception:
            pass
        return {"name": name, "path": str(path), "ok": False, "detail": str(exc)}


def collect_path_checks(paths: dict[str, Path]) -> list[dict[str, Any]]:
    return [check_path_writable(name, path) for name, path in paths.items()]


def read_daemon_status_file(
    status_path: Path,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 90,
    pid_exists: Callable[[int], bool] | None = None,
) -> dict[str, Any]:
    now = now or _now_utc()
    pid_exists = pid_exists or _default_pid_exists
    base: dict[str, Any] = {
        "path": str(status_path),
        "status": "missing",
        "fresh": False,
        "age_seconds": None,
        "daemon_pid": None,
        "pid_alive": False,
        "services": {},
        "detail": "",
    }
    if not status_path.exists():
        return base
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {**base, "status": "malformed", "detail": str(exc)}

    updated_at = _parse_datetime(data.get("updated_at"))
    if updated_at is None:
        return {
            **base,
            "status": "malformed",
            "daemon_pid": data.get("daemon_pid"),
            "services": data.get("services", {}) if isinstance(data.get("services"), dict) else {},
            "detail": "missing or invalid updated_at",
        }

    age_seconds = max(0, int((now - updated_at).total_seconds()))
    daemon_pid = data.get("daemon_pid")
    pid_alive = isinstance(daemon_pid, int) and pid_exists(daemon_pid)
    services = data.get("services", {})
    if not isinstance(services, dict):
        services = {}
    status = "fresh" if age_seconds <= max_age_seconds else "stale"
    return {
        **base,
        "status": status,
        "fresh": status == "fresh",
        "age_seconds": age_seconds,
        "daemon_pid": daemon_pid,
        "pid_alive": pid_alive,
        "services": services,
    }


def read_ai_monitor_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {
            "status": "missing",
            "enabled": False,
            "config_path": str(config_path),
            "detail": "daemon config file is missing",
        }
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {
            "status": "error",
            "enabled": False,
            "config_path": str(config_path),
            "detail": str(exc),
        }
    ai_monitor = data.get("ai_monitor", {})
    enabled = bool(ai_monitor.get("enabled", False)) if isinstance(ai_monitor, dict) else False
    return {
        "status": "enabled" if enabled else "disabled",
        "enabled": enabled,
        "config_path": str(config_path),
        "detail": "ai_monitor.enabled is true" if enabled else "ai_monitor.enabled is false",
    }


def collect_self_heal_summary(runtime_dir: Path) -> dict[str, Any]:
    report_path = runtime_dir / "adaptive" / "reports" / "self-heal-latest.json"
    if not report_path.exists():
        return {"status": "missing", "report_path": str(report_path), "summary": "no self-heal report found"}
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "malformed", "report_path": str(report_path), "summary": str(exc)}
    summary = data.get("summary") or data.get("status") or "self-heal report present"
    issues = data.get("issues", [])
    issue_count = len(issues) if isinstance(issues, list) else 0
    return {
        "status": "reported",
        "report_path": str(report_path),
        "summary": str(summary),
        "issue_count": issue_count,
    }


def aggregate_health(
    *,
    task: dict[str, Any],
    paths: list[dict[str, Any]],
    status_file: dict[str, Any],
    sidecar: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    task_status = task.get("status")
    if task_status == "not_installed":
        issues.append("scheduled task is not installed")
    elif task_status in {"disabled", "error", "mismatch"}:
        issues.append(f"scheduled task status is {task_status}")
    for path_check in paths:
        if not path_check.get("ok"):
            issues.append(f"{path_check.get('name')} is not writable: {path_check.get('detail')}")
    if status_file.get("status") == "missing":
        issues.append("daemon status file is missing")
    elif status_file.get("status") in {"stale", "malformed"}:
        issues.append(f"daemon status file is {status_file.get('status')}")
    if status_file.get("fresh") and not status_file.get("pid_alive"):
        issues.append("daemon status file is fresh but daemon pid is not alive")
    if sidecar.get("status") == "error":
        issues.append(f"ai monitor config error: {sidecar.get('detail')}")

    if task_status == "not_installed":
        health = "not_installed"
    elif issues:
        health = "degraded"
    else:
        health = "healthy"
    return {"health": health, "issues": issues}
```

- [ ] **Step 4: Run diagnostics tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_daemon_diagnostics.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit diagnostics helper**

```powershell
git add skills\daemon\scripts\daemon_diagnostics.py skills\daemon\augur\tests\test_daemon_diagnostics.py
git -c user.name="Codex" -c user.email="codex@openai.com" commit -m "feat(daemon): add runtime diagnostics helper"
```

## Task 3: Wire Windows Diagnostics Into Service Healer

**Files:**
- Modify: `skills/daemon/scripts/service_healer.py`
- Modify: `skills/daemon/augur/tests/test_service_healer_registration.py`

- [ ] **Step 1: Write failing service-healer diagnostics tests**

Append these tests to `skills/daemon/augur/tests/test_service_healer_registration.py`:

```python
@patch("sys.platform", "win32")
def test_collect_windows_daemon_diagnostics_reports_missing_task(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    runtime_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()

    with patch.object(service_healer, "get_runtime_dir", return_value=runtime_dir), patch.object(
        service_healer, "get_logs_dir", return_value=logs_dir
    ), patch.object(service_healer, "_query_windows_task_state", return_value={"status": "not_found"}), patch.object(
        service_healer, "_read_windows_task_details", return_value=None
    ):
        result = service_healer._collect_windows_daemon_diagnostics(project_root)

    assert result["health"] == "not_installed"
    assert result["task"]["status"] == "not_installed"
    assert "scheduled task is not installed" in result["issues"]
    assert result["status_file"]["status"] == "missing"
    assert result["sidecar"]["status"] in {"missing", "disabled"}


@patch("sys.platform", "win32")
def test_collect_windows_daemon_diagnostics_reports_task_path_mismatch(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    runtime_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()
    (project_root / "config" / "system").mkdir(parents=True)
    (project_root / "config" / "system" / "daemon.yaml").write_text("ai_monitor:\n  enabled: false\n", encoding="utf-8")

    current = {
        "command": str(project_root / ".venv" / "Scripts" / "python.exe.old"),
        "arguments": f'"{project_root / "skills" / "daemon" / "scripts" / "unified_daemon.py"}"',
        "working_dir": str(project_root),
    }

    with patch.object(service_healer, "get_runtime_dir", return_value=runtime_dir), patch.object(
        service_healer, "get_logs_dir", return_value=logs_dir
    ), patch.object(service_healer, "_query_windows_task_state", return_value={"status": "ok", "state": "installed"}), patch.object(
        service_healer, "_read_windows_task_details", return_value=current
    ):
        result = service_healer._collect_windows_daemon_diagnostics(project_root)

    assert result["health"] == "degraded"
    assert result["task"]["status"] == "mismatch"
    assert result["task"]["expected_command"].endswith(".venv\\Scripts\\python.exe")
    assert "command mismatch" in result["task"]["issues"]
```

- [ ] **Step 2: Run failing service-healer diagnostics tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_service_healer_registration.py::test_collect_windows_daemon_diagnostics_reports_missing_task skills\daemon\augur\tests\test_service_healer_registration.py::test_collect_windows_daemon_diagnostics_reports_task_path_mismatch -q
```

Expected: FAIL because `_collect_windows_daemon_diagnostics` does not exist.

- [ ] **Step 3: Add service-healer diagnostics collection**

In `skills/daemon/scripts/service_healer.py`, add this import near the existing imports after logger setup imports:

```python
import daemon_diagnostics
```

Add this helper near `_collect_windows_status_results`:

```python
def _windows_task_diagnostics(spec: DaemonRegistrationSpec) -> dict[str, Any]:
    state_result = _query_windows_task_state(spec.task_name)
    details = _read_windows_task_details(spec.task_name)
    expected_arguments = f'"{spec.daemon_script}"'
    task: dict[str, Any] = {
        "task_name": spec.task_name,
        "status": "unknown",
        "state": "",
        "command": details.get("command") if details else "",
        "arguments": details.get("arguments") if details else "",
        "working_dir": details.get("working_dir") if details else "",
        "expected_command": str(spec.python_path),
        "expected_arguments": expected_arguments,
        "expected_working_dir": str(spec.working_dir),
        "issues": [],
        "detail": "",
    }
    if state_result["status"] == "not_found":
        task["status"] = "not_installed"
        return task
    if state_result["status"] == "error":
        task["status"] = "error"
        task["detail"] = state_result.get("detail", "unknown scheduler error")
        return task
    task["state"] = state_result.get("state", "")
    task["status"] = task["state"] or "installed"
    if details is None:
        task["status"] = "mismatch"
        task["issues"].append("task details unavailable")
        return task
    if _normalize_windows_path(details.get("command")) != _normalize_windows_path(str(spec.python_path)):
        task["issues"].append("command mismatch")
    if details.get("arguments", "").strip() != expected_arguments:
        task["issues"].append("arguments mismatch")
    if _normalize_windows_path(details.get("working_dir")) != _normalize_windows_path(str(spec.working_dir)):
        task["issues"].append("working directory mismatch")
    if task["issues"]:
        task["status"] = "mismatch"
    return task
```

Add this helper after `_windows_task_diagnostics`:

```python
def _collect_windows_daemon_diagnostics(project_root: Path) -> dict[str, Any]:
    spec = _build_registration_spec("daemon", project_root, platform_name="win32")
    runtime_dir = get_runtime_dir()
    logs_dir = get_logs_dir()
    paths = daemon_diagnostics.collect_path_checks(
        {
            "logs": logs_dir,
            "state": runtime_dir,
            "locks": runtime_dir / "locks",
            "daemon_stderr": logs_dir / "daemon" / "stderr",
            "daemon_status": runtime_dir / "stats",
        }
    )
    task = _windows_task_diagnostics(spec)
    status_file = daemon_diagnostics.read_daemon_status_file(runtime_dir / "stats" / "daemon_status.json")
    sidecar = daemon_diagnostics.read_ai_monitor_config(project_root / "config" / "system" / "daemon.yaml")
    self_heal = daemon_diagnostics.collect_self_heal_summary(runtime_dir)
    aggregate = daemon_diagnostics.aggregate_health(
        task=task,
        paths=paths,
        status_file=status_file,
        sidecar=sidecar,
    )
    return {
        **aggregate,
        "task": task,
        "paths": paths,
        "status_file": status_file,
        "sidecar": sidecar,
        "self_heal": self_heal,
    }
```

- [ ] **Step 4: Replace Windows status output with evidence-rich diagnostics**

In the `if args.action == "status"` branch for `sys.platform == "win32"`, replace the current Windows block with:

```python
        if sys.platform == "win32":
            diagnostics = _collect_windows_daemon_diagnostics(get_project_root())
            results = {"daemon": diagnostics["health"]}
            legacy = _collect_windows_status_results(get_project_root())
            results["legacy_nightly_windows_task"] = legacy["legacy_nightly_windows_task"]
            _out(f"  Health: {diagnostics['health']}")
            _out(f"  Task: {diagnostics['task']['status']} ({diagnostics['task'].get('state') or 'no-state'})")
            if diagnostics["task"].get("issues"):
                _out(f"  Task issues: {', '.join(diagnostics['task']['issues'])}")
            _out(f"  Status file: {diagnostics['status_file']['status']} ({diagnostics['status_file']['path']})")
            _out(f"  AI monitor: {diagnostics['sidecar']['status']} - {diagnostics['sidecar']['detail']}")
            _out(f"  Self-heal: {diagnostics['self_heal']['status']} - {diagnostics['self_heal']['summary']}")
            for issue in diagnostics["issues"]:
                _out(f"  Issue: {issue}")
            _out("\n  Legacy Services:")
            _out(f"    nightly_windows_task: {results['legacy_nightly_windows_task']}")
```

- [ ] **Step 5: Run service-healer tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_service_healer_registration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit service-healer diagnostics**

```powershell
git add skills\daemon\scripts\service_healer.py skills\daemon\augur\tests\test_service_healer_registration.py
git -c user.name="Codex" -c user.email="codex@openai.com" commit -m "feat(daemon): report Windows service diagnostics"
```

## Task 4: Improve Unified Daemon Status Semantics

**Files:**
- Modify: `skills/daemon/scripts/unified_daemon.py`
- Modify: `skills/daemon/augur/tests/test_unified_daemon.py`

- [ ] **Step 1: Write failing status tests**

Append these tests to `skills/daemon/augur/tests/test_unified_daemon.py`:

```python
def test_cmd_status_reports_missing_status_file(monkeypatch, tmp_path, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    monkeypatch.setattr(mod, "STATUS_FILE", tmp_path / "missing.json")

    assert mod.cmd_status() == 1
    output = capsys.readouterr().out
    assert "Status file: MISSING" in output
    assert "Daemon: STOPPED" in output


def test_cmd_status_reports_stale_status_file(monkeypatch, tmp_path, capsys):
    import importlib
    import json
    from datetime import datetime, timedelta, timezone

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        json.dumps(
            {
                "daemon_pid": 1234,
                "started_at": "2026-05-06T09:00:00",
                "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "uptime_seconds": 60,
                "services": {"log_monitor": {"state": "running", "pid": 111, "total_restarts": 0}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATUS_FILE", status_path)
    monkeypatch.setattr(mod, "_read_pid", lambda: None)

    assert mod.cmd_status() == 1
    output = capsys.readouterr().out
    assert "Status file: STALE" in output
    assert "Daemon: STOPPED" in output


def test_cmd_status_reports_fresh_running_status(monkeypatch, tmp_path, capsys):
    import importlib
    import json
    from datetime import datetime, timezone

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        json.dumps(
            {
                "daemon_pid": 1234,
                "started_at": "2026-05-06T09:00:00",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": 60,
                "services": {"log_monitor": {"state": "running", "pid": 111, "total_restarts": 0}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATUS_FILE", status_path)
    monkeypatch.setattr(mod, "_read_pid", lambda: 1234)

    assert mod.cmd_status() == 0
    output = capsys.readouterr().out
    assert "Status file: FRESH" in output
    assert "Daemon: RUNNING" in output
    assert "log_monitor: RUNNING" in output
```

- [ ] **Step 2: Run failing unified-daemon status tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_unified_daemon.py::test_cmd_status_reports_missing_status_file skills\daemon\augur\tests\test_unified_daemon.py::test_cmd_status_reports_stale_status_file skills\daemon\augur\tests\test_unified_daemon.py::test_cmd_status_reports_fresh_running_status -q
```

Expected: at least the missing/stale assertions fail because current output does not distinguish these states.

- [ ] **Step 3: Use diagnostics in `cmd_status`**

In `skills/daemon/scripts/unified_daemon.py`, add this import with the other daemon script imports:

```python
import daemon_diagnostics
```

Replace `cmd_status()` with:

```python
def cmd_status() -> int:
    """Show daemon status from status file."""
    diagnostic = daemon_diagnostics.read_daemon_status_file(
        STATUS_FILE,
        max_age_seconds=90,
        pid_exists=lambda pid: _read_pid() == pid,
    )
    if diagnostic["status"] == "missing":
        _out(f"Status file: MISSING ({STATUS_FILE})")
        _out("Daemon: STOPPED")
        return 1
    if diagnostic["status"] == "malformed":
        _out(f"Status file: MALFORMED ({STATUS_FILE})")
        _out(f"Detail: {diagnostic['detail']}")
        _out("Daemon: STOPPED")
        return 1

    running = diagnostic["pid_alive"] and diagnostic["fresh"]
    status_label = str(diagnostic["status"]).upper()
    _out(f"Status file: {status_label} ({STATUS_FILE})")
    if diagnostic["age_seconds"] is not None:
        _out(f"Status age: {diagnostic['age_seconds']}s")
    _out(f"Daemon: {'RUNNING' if running else 'STOPPED'} (PID {diagnostic.get('daemon_pid', '?')})")

    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    _out(f"Started: {data.get('started_at', '?')}")
    _out(f"Uptime: {data.get('uptime_seconds', 0)}s")
    _out()

    services = diagnostic.get("services", {})
    for name, info in services.items():
        if not isinstance(info, dict):
            continue
        state = info.get("state", "unknown")
        pid_str = f" (PID {info['pid']})" if info.get("pid") else ""
        restarts = info.get("total_restarts", 0)
        restart_str = f" [{restarts} restarts]" if restarts > 0 else ""
        _out(f"  {name}: {str(state).upper()}{pid_str}{restart_str}")

    return 0 if running else 1
```

- [ ] **Step 4: Run unified-daemon tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_unified_daemon.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit unified status semantics**

```powershell
git add skills\daemon\scripts\unified_daemon.py skills\daemon\augur\tests\test_unified_daemon.py
git -c user.name="Codex" -c user.email="codex@openai.com" commit -m "feat(daemon): distinguish missing stale and fresh status"
```

## Task 5: Add Notification Backend Details

**Files:**
- Modify: `skills/daemon/scripts/notification_service.py`
- Modify: `skills/daemon/scripts/mcp/_notifications.py`
- Modify: `skills/daemon/augur/tests/test_notification_service.py`

- [ ] **Step 1: Write failing notification backend tests**

Append these tests to `skills/daemon/augur/tests/test_notification_service.py`:

```python
def test_notification_result_has_backend_field():
    result = NotificationResult(success=True, channel="windows", message="ok", backend="powershell")
    assert result.backend == "powershell"


def test_send_windows_reports_powershell_backend_when_plyer_missing(tmp_path):
    svc = NotificationService(data_dir=tmp_path / "notif")
    svc._system = "Windows"

    with patch.dict(sys.modules, {"plyer": None}), patch.object(
        notification_service,
        "_run_command",
        return_value=notification_service.CompletedProcess(args=["powershell"], returncode=0, stdout="", stderr=""),
    ):
        result = svc._send_windows("hello", "Augur Test")

    assert result.success is True
    assert result.channel == "windows"
    assert result.backend == "powershell"


def test_send_windows_reports_backend_error_when_powershell_fails(tmp_path):
    svc = NotificationService(data_dir=tmp_path / "notif")
    svc._system = "Windows"

    with patch.dict(sys.modules, {"plyer": None}), patch.object(
        notification_service,
        "_run_command",
        return_value=notification_service.CompletedProcess(args=["powershell"], returncode=1, stdout="", stderr="toast failed"),
    ):
        result = svc._send_windows("hello", "Augur Test")

    assert result.success is False
    assert result.channel == "windows"
    assert result.backend == "powershell"
    assert "toast failed" in (result.error or "")
```

- [ ] **Step 2: Run failing notification tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_notification_service.py::test_notification_result_has_backend_field skills\daemon\augur\tests\test_notification_service.py::test_send_windows_reports_powershell_backend_when_plyer_missing skills\daemon\augur\tests\test_notification_service.py::test_send_windows_reports_backend_error_when_powershell_fails -q
```

Expected: FAIL because `NotificationResult` has no `backend` field and `_send_windows` does not populate backend details.

- [ ] **Step 3: Add backend field and populate Windows results**

In `skills/daemon/scripts/notification_service.py`, change `NotificationResult` to:

```python
@dataclass
class NotificationResult:
    """Result of sending a notification."""

    success: bool
    channel: str
    message: str = ""
    error: Optional[str] = None
    backend: str = ""
```

In `_send_windows`, update result construction:

```python
            self._log_notification("windows", message, success=True)
            return NotificationResult(success=True, channel="windows", message=message, backend="plyer")
```

For successful PowerShell fallback:

```python
                self._log_notification("windows", message, success=True)
                return NotificationResult(success=True, channel="windows", message=message, backend="powershell")
```

For PowerShell nonzero exit:

```python
                return NotificationResult(
                    success=False,
                    channel="windows",
                    error=f"PowerShell error: {result.stderr.strip()}",
                    backend="powershell",
                )
```

For exception fallback:

```python
            return NotificationResult(success=False, channel="windows", error=str(e), backend="powershell")
```

- [ ] **Step 4: Include backend in MCP send-test response**

In `skills/daemon/scripts/mcp/_notifications.py`, in `send_test_notification_tool`, add `backend` to the JSON payload:

```python
                    "backend": result.backend,
```

- [ ] **Step 5: Run notification tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest skills\daemon\augur\tests\test_notification_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit notification backend details**

```powershell
git add skills\daemon\scripts\notification_service.py skills\daemon\scripts\mcp\_notifications.py skills\daemon\augur\tests\test_notification_service.py
git -c user.name="Codex" -c user.email="codex@openai.com" commit -m "feat(daemon): report notification backend in self-test"
```

## Task 6: Focused Regression Run

**Files:**
- No new files. This task verifies the implementation.

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_logging.py skills\daemon\augur\tests\test_daemon_diagnostics.py skills\daemon\augur\tests\test_service_healer_registration.py skills\daemon\augur\tests\test_unified_daemon.py skills\daemon\augur\tests\test_notification_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run service status without mutating OS registration**

Run:

```powershell
.\.venv\Scripts\python.exe skills\daemon\scripts\service_healer.py status
```

Expected on the current machine before install: output includes `Health: not_installed`, `Task: not_installed`, `Status file: missing`, and `AI monitor: disabled` or `AI monitor: missing`. If the task is already installed by the time this runs, expected output includes `Health: healthy` or `Health: degraded` with exact issues.

- [ ] **Step 3: Handle final test-only corrections**

Expected: no commit is needed if Tasks 1-5 already passed. If Step 1 exposed a real defect, return to the smallest relevant implementation task above, add a regression test there, apply the fix there, rerun that task's tests, and use that task's commit command.

## Task 7: Live Windows Smoke

**Files:**
- No source files unless the live smoke exposes a bug. If a bug appears, return to the smallest relevant task and add a regression test before fixing.

- [ ] **Step 1: Install or heal the scheduled task**

This step changes Windows Task Scheduler state and may require user approval in Codex.

Run:

```powershell
.\.venv\Scripts\python.exe skills\daemon\scripts\service_healer.py heal
```

Expected: command exits 0, or exits nonzero with exact blocker text. Acceptable success statuses are `daemon: healed`, `daemon: ok`, or `daemon: running`.

- [ ] **Step 2: Verify Task Scheduler registration**

Run:

```powershell
schtasks /query /tn "com.augur.daemon" /v /fo LIST
```

Expected: output contains `TaskName: \com.augur.daemon` or `TaskName: com.augur.daemon` and no `ERROR: The system cannot find the file specified.`

- [ ] **Step 3: Verify daemon internal status**

Run:

```powershell
.\.venv\Scripts\python.exe skills\daemon\scripts\unified_daemon.py status
```

Expected: output includes `Status file: FRESH`, `Daemon: RUNNING`, and child services such as `log_monitor`, `adaptive_loop_engine`, and `notification_processor`.

- [ ] **Step 4: Send notification self-test**

Run:

```powershell
.\.venv\Scripts\python.exe skills\daemon\scripts\notification_service.py
```

Expected: output includes `Platform: Windows`, `Success: True`, and no unhandled traceback. If success is false, output includes the backend-specific error.

- [ ] **Step 5: Record live smoke result in final handoff**

Include these exact facts in the implementation final answer:

- `service_healer.py status`: exit code and health string from Step 2.
- `service_healer.py heal`: exit code and daemon result from Step 1.
- `schtasks query`: whether the task was registered, running, disabled, or errored.
- `unified_daemon.py status`: status freshness and daemon running state.
- `notification self-test`: success/failure plus backend name or backend error.

Expected: no source commit is needed unless live smoke exposes a code defect.

## Final Verification

Run:

```powershell
git status --short --branch
.\.venv\Scripts\python.exe -m pytest tests\test_logging.py skills\daemon\augur\tests\test_daemon_diagnostics.py skills\daemon\augur\tests\test_service_healer_registration.py skills\daemon\augur\tests\test_unified_daemon.py skills\daemon\augur\tests\test_notification_service.py -q
.\.venv\Scripts\python.exe skills\daemon\scripts\service_healer.py status
```

Expected:

- Git shows only intentional changes or a clean tree after commits.
- Focused pytest command passes.
- `service_healer.py status` prints Windows daemon evidence instead of crashing.

Do not report Windows daemon parity unless Task 7 live smoke has also passed or the final answer explicitly says which live smoke step failed.

## Implementation Notes

- Use `.\.venv\Scripts\python.exe`; do not use bare `python` or `python3` on Windows.
- Do not run `unified_daemon.py start` manually as the daemon path. Use `service_healer.py heal` or `service_healer.py install` so Task Scheduler owns the process.
- Do not enable `ai_monitor.enabled` in `config/system/daemon.yaml` as part of this plan.
- Keep status output evidence-rich and short: exact state, exact path, exact error.
- If Task Scheduler mutation fails because of sandboxing, rerun the same command with escalated approval and preserve the exact failing output.
