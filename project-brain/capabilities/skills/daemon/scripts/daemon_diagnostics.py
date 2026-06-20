"""Pure runtime diagnostics helpers for daemon self-heal checks."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping
from uuid import uuid4

import yaml


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _windows_pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _default_pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_mapping_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        actual_type = type(data).__name__
        raise ValueError(f"expected mapping in {path}, got {actual_type}")
    return data


def check_path_writable(name: str, path: str | Path) -> dict[str, Any]:
    target = Path(path)
    probe = target / f".augur-write-probe-{uuid4().hex}.tmp"
    result: dict[str, Any] = {
        "name": name,
        "path": str(target),
        "status": "ok",
        "writable": True,
        "ok": True,
    }

    try:
        target.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
    except Exception as exc:
        result.update(
            {
                "status": "error",
                "writable": False,
                "ok": False,
                "error_type": type(exc).__name__,
                "detail": str(exc),
            }
        )
    finally:
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass

    return result


def collect_path_checks(paths: Mapping[str, str | Path]) -> list[dict[str, Any]]:
    return [check_path_writable(name, path) for name, path in paths.items()]


def read_daemon_status_file(
    status_path: str | Path,
    now: datetime | None = None,
    max_age_seconds: int = 90,
    pid_exists: Callable[[int], bool] | None = None,
) -> dict[str, Any]:
    path = Path(status_path)
    if not path.exists():
        return {
            "status": "missing",
            "path": str(path),
            "fresh": False,
            "pid_alive": False,
            "age_seconds": None,
            "daemon_pid": None,
            "issue": f"daemon status file missing: {path}",
            "issues": [f"daemon status file missing: {path}"],
            "services": {},
        }

    try:
        data = _read_mapping_file(path)
    except Exception as exc:
        return {
            "status": "malformed",
            "path": str(path),
            "fresh": False,
            "pid_alive": False,
            "age_seconds": None,
            "daemon_pid": None,
            "issue": f"daemon status file malformed: {path}",
            "error_type": type(exc).__name__,
            "detail": str(exc),
            "issues": [f"daemon status file malformed: {path}: {exc}"],
            "services": {},
        }
    if not data:
        return {
            "status": "malformed",
            "path": str(path),
            "fresh": False,
            "pid_alive": False,
            "age_seconds": None,
            "daemon_pid": None,
            "issue": f"daemon status file malformed: {path}",
            "issues": [f"daemon status file malformed: {path}: expected mapping"],
            "services": {},
        }

    checked_at = (now or _now_utc()).astimezone(timezone.utc)
    updated_at = _parse_datetime(data.get("updated_at"))
    age_seconds: float | None = None
    issues: list[str] = []

    if updated_at is None:
        issues.append("daemon status file has no valid updated_at timestamp")
    else:
        age_seconds = max(0.0, (checked_at - updated_at).total_seconds())
        if age_seconds > max_age_seconds:
            issues.append(f"daemon status file is stale: {int(age_seconds)}s old")

    pid = data.get("daemon_pid")
    pid_alive = False
    pid_malformed = False
    if type(pid) is int:
        pid_alive = (pid_exists or _default_pid_exists)(pid)
        if not pid_alive:
            issues.append(f"daemon pid {pid} is not alive")
    elif pid is None:
        pid_malformed = True
        issues.append("daemon_pid is missing")
    elif pid is not None:
        pid_malformed = True
        issues.append(f"daemon_pid is not an integer: {pid!r} ({type(pid).__name__})")

    services = data.get("services")
    if not isinstance(services, dict):
        services = {}

    if not issues:
        status = "fresh"
    elif age_seconds is not None and age_seconds > max_age_seconds:
        status = "stale"
    elif pid_malformed:
        status = "malformed"
    elif type(pid) is int and pid_alive is False:
        status = "stale"
    else:
        status = "malformed"

    return {
        "status": status,
        "path": str(path),
        "fresh": status == "fresh",
        "daemon_pid": pid,
        "pid_alive": pid_alive,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "age_seconds": age_seconds,
        "services": services,
        "issues": issues,
    }


def read_ai_monitor_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {
            "status": "missing",
            "enabled": False,
            "config_path": str(path),
            "config": {},
            "detail": "daemon config file is missing",
            "issue": f"ai_monitor config missing: {path}",
        }

    try:
        data = _read_mapping_file(path)
    except Exception as exc:
        return {
            "status": "error",
            "enabled": False,
            "config_path": str(path),
            "config": {},
            "error_type": type(exc).__name__,
            "detail": str(exc),
        }

    config = data.get("ai_monitor", {})
    if not isinstance(config, dict):
        config = {}
    enabled = bool(config.get("enabled", False))
    return {
        "status": "enabled" if enabled else "disabled",
        "enabled": enabled,
        "config_path": str(path),
        "config": config,
        "detail": "ai_monitor.enabled is true" if enabled else "ai_monitor.enabled is false",
    }


def collect_self_heal_summary(runtime_dir: str | Path) -> dict[str, Any]:
    root = Path(runtime_dir)
    report_path = root / "adaptive" / "reports" / "self-heal-latest.json"
    if not report_path.exists():
        return {
            "status": "missing",
            "report_path": str(report_path),
            "summary": f"No self-heal report found at {report_path}",
            "issue_count": 0,
        }

    try:
        report = _read_mapping_file(report_path)
    except Exception as exc:
        return {
            "status": "malformed",
            "report_path": str(report_path),
            "summary": f"Self-heal report is malformed: {exc}",
            "issue_count": 0,
            "error_type": type(exc).__name__,
            "detail": str(exc),
        }

    issue_count = report.get("issue_count")
    if not isinstance(issue_count, int):
        issues = report.get("issues")
        issue_count = len(issues) if isinstance(issues, list) else 0

    return {
        "status": "reported",
        "report_path": str(report_path),
        "summary": str(report.get("summary") or "Self-heal report available"),
        "issue_count": issue_count,
    }


def _normalize_task(task: Mapping[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {"status": "unknown"}

    status = str(task.get("status", "unknown"))
    if status == "not_found":
        status = "not_installed"

    normalized = dict(task)
    normalized["status"] = status
    return normalized


def aggregate_health(
    task: Mapping[str, Any] | None,
    paths: list[dict[str, Any]],
    status_file: Mapping[str, Any],
    sidecar: Mapping[str, Any],
) -> dict[str, Any]:
    task_result = _normalize_task(task)

    issues: list[str] = []
    task_status = task_result.get("status")
    if task_status == "not_installed":
        issues.append("scheduled task is not installed")
    elif task_status in {"degraded", "disabled", "error", "mismatch", "stopped", "unknown"}:
        detail = task_result.get("detail", "status unavailable")
        issues.append(f"scheduled task status is {task_status}: {detail}")

    for path_result in paths:
        path_ok = path_result.get("ok", path_result.get("writable", False))
        if not path_ok:
            issues.append(
                f"{path_result['name']} path is not writable: {path_result.get('detail', 'unknown error')}"
            )

    status = status_file.get("status")
    if status != "fresh":
        existing_issues = status_file.get("issues")
        if isinstance(existing_issues, list) and existing_issues:
            issues.extend(str(issue) for issue in existing_issues)
        elif status_file.get("issue"):
            issues.append(str(status_file["issue"]))
        else:
            issues.append(f"daemon status is {status or 'unknown'}")

    services = status_file.get("services")
    if isinstance(services, Mapping):
        for service_name, service in services.items():
            if not isinstance(service, Mapping):
                continue
            state = str(service.get("state") or "").strip()
            if not state or state == "running":
                continue
            restarts = service.get("total_restarts")
            restart_detail = f" ({restarts} restarts)" if isinstance(restarts, int) else ""
            issues.append(f"child service {service_name} is {state}{restart_detail}")

    if sidecar.get("status") in {"error", "missing"}:
        issues.append(str(sidecar.get("issue") or f"ai_monitor config is {sidecar.get('status')}"))

    return {
        "health": "not_installed" if task_status == "not_installed" else "degraded" if issues else "healthy",
        "issues": issues,
    }
