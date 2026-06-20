#!/usr/bin/env python3
"""
Cross-Platform Background Service Manager.

Manages the unified Augur daemon as a single macOS LaunchAgent.
The daemon runs inside a lightweight .app bundle so macOS Background Activity
shows "Augur" with a proper icon instead of multiple "python3" entries.

Also handles migration from legacy per-service plists to the unified daemon.

Usage:
    python service_healer.py install    # Install unified daemon
    python service_healer.py uninstall  # Remove unified daemon
    python service_healer.py heal       # Fix paths if project moved
    python service_healer.py status     # Show service status
    python service_healer.py migrate    # Migrate from legacy plists
"""
# TODO_CLEANUP: This file is 1222 lines — consider splitting into smaller modules

import os
import plistlib
import shutil
import sys
import re
import time
import defusedxml.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, DEVNULL, Popen, run  # nosec B404
from typing import Any, Optional
from xml.sax.saxutils import escape as xml_escape

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent

try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

BOOTSTRAP_ROOT = ensure_project_paths(__file__)

# daemon_diagnostics lives next to this file; bootstrap_paths above guarantees
# SCRIPTS_DIR is on sys.path so the bare import resolves on every entrypoint.
import daemon_diagnostics

try:
    from src.config.paths import (
        get_documents_dir,
        get_launch_agents_dir,
        get_logs_dir,
        get_project_name,
        get_project_root,
        get_runtime_dir,
        get_python_executable,
        get_skill_root,
        get_vault_dir,
    )
    try:
        SKILL_ROOT = get_skill_root("daemon")
    except Exception:
        shared_skill_root = BOOTSTRAP_ROOT / "project-brain" / "capabilities" / "skills" / "daemon"
        SKILL_ROOT = shared_skill_root
except ImportError:
    # Fallback for standalone execution outside monorepo
    SKILL_ROOT = SCRIPTS_DIR.parent
    if SKILL_ROOT.parent.parent.name == "project-brain":
        BOOTSTRAP_ROOT = SKILL_ROOT.parent.parent.parent
    else:
        BOOTSTRAP_ROOT = SKILL_ROOT.parent.parent
    if str(BOOTSTRAP_ROOT) not in sys.path:
        sys.path.insert(0, str(BOOTSTRAP_ROOT))
    from src.config.paths import (
        get_documents_dir,
        get_launch_agents_dir,
        get_logs_dir,
        get_project_name,
        get_project_root,
        get_runtime_dir,
        get_python_executable,
        get_skill_root,
        get_vault_dir,
    )
from src.logging import get_entity_logger

logger = get_entity_logger("service_healer")


def _resolve_daemon_skill_root(project_root: Path) -> Path:
    """Return the canonical daemon skill root under project-brain."""
    return project_root / "project-brain" / "capabilities" / "skills" / "daemon"


@dataclass(frozen=True)
class DaemonRegistrationSpec:
    label: str
    plist_name: str
    task_name: str
    working_dir: Path
    daemon_script: Path
    python_path: Path
    macos_app_executable: Path
    stdout_path: Path
    stderr_path: Path


def _service_label() -> str:
    return f"com.{get_project_name().lower()}.daemon"


def _task_name() -> str:
    return _service_label()


def _build_registration_spec(
    service_name: str,
    project_root: Path,
    platform_name: str | None = None,
) -> DaemonRegistrationSpec:
    service = SERVICES.get(service_name)
    if not service:
        raise KeyError(service_name)

    platform_name = platform_name or sys.platform
    label = _service_label()
    daemon_root = _resolve_daemon_skill_root(project_root)
    # ADR-787 Part B: the in-process supervisor replaces the unified_daemon
    # subprocess fleet as the canonical daemon launcher.
    daemon_script = daemon_root / "scripts" / "daemon_supervisor.py"
    stdout_path = get_logs_dir() / service["stdout"]
    stderr_path = get_logs_dir() / service["stderr"]
    # Windows: launch via pythonw.exe (GUI subsystem) so the logon-triggered
    # scheduled task runs the daemon with no console window. python.exe is a
    # console-subsystem host and would pop a visible command window in the
    # user's interactive session. Child services still use python.exe but are
    # spawned with CREATE_NO_WINDOW (see unified_daemon._apply_no_window).
    python_path = (
        project_root / ".venv" / "Scripts" / "pythonw.exe"
        if platform_name == "win32"
        else project_root / ".venv" / "bin" / "python"
    )

    return DaemonRegistrationSpec(
        label=label,
        plist_name=f"{label}.plist",
        task_name=_task_name(),
        working_dir=project_root,
        daemon_script=daemon_script,
        python_path=python_path,
        macos_app_executable=daemon_root / service["executable"],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def _plist_label() -> str:
    return _service_label()


def _plist_filename() -> str:
    return f"{_plist_label()}.plist"


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable to absolute path where available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    try:
        resolved = shutil.which(executable)
    except AttributeError:
        return command

    if not resolved:
        return command

    return [resolved, *command[1:]]


_NO_WINDOW_CREATIONFLAGS = (
    getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
    if sys.platform == "win32"
    else 0
)


def _apply_no_window(kwargs: dict[str, object]) -> dict[str, object]:
    """Inject CREATE_NO_WINDOW on Windows so child consoles never flash a window."""
    if _NO_WINDOW_CREATIONFLAGS:
        existing = int(kwargs.get("creationflags", 0) or 0)
        kwargs["creationflags"] = existing | _NO_WINDOW_CREATIONFLAGS
    return kwargs


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable path."""
    return run(_resolve_command(command), **_apply_no_window(kwargs))  # nosec B603

# =============================================================================
# Service Definitions
# =============================================================================

# Unified daemon — single source of truth
SERVICES = {
    "daemon": {
        "plist_name": _plist_filename(),
        "template": "daemon.plist.template",
        "executable": "assets/bundle/Augur Daemon.app/Contents/MacOS/Augur",
        "keep_alive": True,
        "stdout": "daemon.stdout.log",
        "stderr": "daemon.stderr.log",
    },
}

# Legacy services (for migration cleanup)
LEGACY_SERVICES = {
    "log_monitor": {"plist_name": "com.augur.logmonitor.plist"},
    "nightly": {"plist_name": "com.augur.nightly.plist"},
    "continuous_executor": {"plist_name": "com.augur.continuous.plist"},
}

_DAEMON_BUNDLE_EXECUTABLE = Path("assets/bundle/Augur Daemon.app/Contents/MacOS/Augur")
# ADR-787 Part B: in-process supervisor replaces the unified_daemon fleet.
_DAEMON_SCRIPT = Path("scripts/daemon_supervisor.py")


# =============================================================================
# macOS LaunchAgent Support
# =============================================================================


def _get_plist_templates_dir(project_root: Path) -> Path:
    return _resolve_daemon_skill_root(project_root) / "assets" / "plists"


def _render_template(template_path: Path, replacements: dict[str, str]) -> str:
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(key, value)
    return content


def _read_plist_paths(plist_path: Path) -> dict:
    """Read paths from a macOS plist file."""
    if not plist_path.exists():
        return {}

    content = plist_path.read_text()
    paths = {}

    # Extract WorkingDirectory
    match = re.search(r'<key>WorkingDirectory</key>\s*<string>([^<]+)</string>', content)
    if match:
        paths["working_dir"] = match.group(1)

    # Extract executable from ProgramArguments (first <string> in the array)
    args = re.findall(r'<key>ProgramArguments</key>\s*<array>(.*?)</array>', content, re.DOTALL)
    if args:
        strings = re.findall(r'<string>([^<]+)</string>', args[0])
        if strings:
            paths["executable"] = strings[0]
            paths["program_arguments"] = strings

    return paths


def _daemon_program_arguments(project_root: Path) -> list[str]:
    """Return the canonical launch command for the unified daemon."""
    daemon_root = _resolve_daemon_skill_root(project_root)
    bundle_executable = daemon_root / _DAEMON_BUNDLE_EXECUTABLE
    if bundle_executable.exists():
        return [str(bundle_executable)]

    return [
        str(get_python_executable()),
        str(daemon_root / _DAEMON_SCRIPT),
    ]


def _expected_program_arguments(service_name: str, project_root: Path) -> list[str]:
    """Return the expected ProgramArguments array for a service."""
    if service_name == "daemon":
        return _daemon_program_arguments(project_root)

    service = SERVICES[service_name]
    return [str(_resolve_daemon_skill_root(project_root) / service["executable"])]


def _launch_target_exists(program_arguments: list[str]) -> bool:
    """Return True when the plist launch target resolves to real files."""
    if not program_arguments:
        return False

    executable = Path(program_arguments[0])
    if not executable.exists():
        return False

    if executable.name.startswith("python") and len(program_arguments) > 1:
        return Path(program_arguments[1]).exists()

    return True


def _service_install_issue(service_name: str, project_root: Path, plist_path: Path) -> str | None:
    """Describe why a LaunchAgent install is missing or broken."""
    if not plist_path.exists():
        return "missing_plist"

    current_paths = _read_plist_paths(plist_path)
    current_args = current_paths.get("program_arguments") or []
    expected_root = str(project_root)
    expected_args = _expected_program_arguments(service_name, project_root)

    if current_paths.get("working_dir") != expected_root:
        return "working_dir_mismatch"
    if current_args != expected_args:
        return "program_arguments_mismatch"
    if not _launch_target_exists(current_args):
        return "missing_launch_target"

    return None


def _generate_plist_content(service_name: str, project_root: Path) -> Optional[str]:
    """Generate plist content for the unified daemon."""
    service = SERVICES.get(service_name)
    if not service:
        return None

    stdout_path = get_logs_dir() / service["stdout"]
    stderr_path = get_logs_dir() / service["stderr"]

    # Ensure log directory exists
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    program_arguments = _expected_program_arguments(service_name, project_root)
    payload = {
        "Label": service["plist_name"].replace(".plist", ""),
        "ProgramArguments": program_arguments,
        "RunAtLoad": True,
        "KeepAlive": bool(service.get("keep_alive", True)),
        "WorkingDirectory": str(project_root),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "AUGUR_VAULT": str(get_vault_dir()),
            "AUGUR_DOCUMENTS": str(get_documents_dir()),
            "AUGUR_SKILL_ROOT": str(_resolve_daemon_skill_root(project_root).parent),
        },
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
    }
    return plistlib.dumps(payload, sort_keys=False).decode("utf-8")


def _render_windows_task_xml(spec: DaemonRegistrationSpec, user_id: str) -> str:
    command = xml_escape(str(spec.python_path))
    arguments = xml_escape(f'"{spec.daemon_script}"')
    working_dir = xml_escape(str(spec.working_dir))
    label = xml_escape(spec.task_name)
    user_id = xml_escape(user_id)

    return "\n".join(
        [
            "<?xml version=\"1.0\" encoding=\"UTF-16\"?>",
            "<Task version=\"1.4\" xmlns=\"http://schemas.microsoft.com/windows/2004/02/mit/task\">",
            "  <RegistrationInfo>",
            f"    <URI>{label}</URI>",
            "  </RegistrationInfo>",
            "  <Triggers>",
            "    <LogonTrigger>",
            f"      <UserId>{user_id}</UserId>",
            "    </LogonTrigger>",
            "  </Triggers>",
            "  <Principals>",
            "    <Principal id=\"Author\">",
            f"      <UserId>{user_id}</UserId>",
            "      <LogonType>InteractiveToken</LogonType>",
            "      <RunLevel>LeastPrivilege</RunLevel>",
            "    </Principal>",
            "  </Principals>",
            "  <Settings>",
            "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>",
            "    <RestartOnFailure>",
            "      <Interval>PT1M</Interval>",
            "      <Count>3</Count>",
            "    </RestartOnFailure>",
            "  </Settings>",
            "  <Actions Context=\"Author\">",
            "    <Exec>",
            f"      <Command>{command}</Command>",
            f"      <Arguments>{arguments}</Arguments>",
            f"      <WorkingDirectory>{working_dir}</WorkingDirectory>",
            "    </Exec>",
            "  </Actions>",
            "</Task>",
        ]
    )


def _get_windows_task_xml_path(task_name: str) -> Path:
    runtime_dir = get_runtime_dir() / "daemon" / "scheduled-tasks"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / f"{task_name}.xml"


def _get_windows_user_id() -> str:
    username = os.environ.get("USERNAME", "").strip()
    userdomain = os.environ.get("USERDOMAIN", "").strip()
    if username and userdomain:
        return f"{userdomain}\\{username}"
    if username:
        return username

    try:
        result = _run_command(["whoami"], capture_output=True, text=True)
    except Exception:
        return ""

    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _escape_powershell_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def _normalize_windows_path(value: str | None) -> str:
    if not value:
        return ""
    return os.path.normcase(os.path.normpath(value.strip().strip('"')))


def _windows_task_not_found_detail(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "scheduledtasknotfoundexception" in lowered
        or "no msft_scheduledtask objects found" in lowered
    )


def _query_windows_task_state(task_name: str) -> dict[str, str]:
    escaped_task_name = _escape_powershell_single_quoted(task_name)
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"try {{ [int](Get-ScheduledTask -TaskName '{escaped_task_name}').State }} "
        "catch { "
        "if ($_.CategoryInfo.Reason -eq 'ScheduledTaskNotFoundException') { exit 3 } "
        "Write-Output $_.Exception.Message; exit 1 "
        "}"
    )
    try:
        result = _run_command(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {"status": "error", "detail": "powershell not found"}

    if result.returncode == 3:
        return {"status": "not_found"}
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"powershell exit code {result.returncode}").strip()
        if _windows_task_not_found_detail(detail):
            return {"status": "not_found"}
        return {"status": "error", "detail": detail}

    state_code = result.stdout.strip()
    if state_code == "4":
        return {"status": "ok", "state": "running"}
    if state_code == "1":
        return {"status": "ok", "state": "disabled"}
    if state_code in {"0", "2", "3"}:
        return {"status": "ok", "state": "installed"}

    return {"status": "error", "detail": f"unexpected task state {state_code!r}"}


def _read_windows_task_details(task_name: str) -> dict[str, str] | None:
    try:
        result = _run_command(
            ["schtasks", "/query", "/tn", task_name, "/xml"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        root = ET.fromstring(result.stdout.lstrip("\ufeff"))
    except ET.ParseError:
        return None

    details: dict[str, str] = {}
    for element in root.iter():
        name = _strip_xml_namespace(element.tag)
        text = (element.text or "").strip()
        if not text:
            continue
        if name == "Command":
            details["command"] = text
        elif name == "Arguments":
            details["arguments"] = text
        elif name == "WorkingDirectory":
            details["working_dir"] = text

    return details or None


def _read_windows_task_state(task_name: str) -> str | None:
    state_result = _query_windows_task_state(task_name)
    if state_result["status"] != "ok":
        return None
    return state_result["state"]


def _register_windows_task(service_name: str, project_root: Path) -> bool:
    spec = _build_registration_spec(service_name, project_root, platform_name="win32")
    xml_path = _get_windows_task_xml_path(spec.task_name)
    xml_path.write_text(_render_windows_task_xml(spec, user_id=_get_windows_user_id()), encoding="utf-16")
    try:
        result = _run_command(
            ["schtasks", "/create", "/tn", spec.task_name, "/xml", str(xml_path), "/f"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False

    return result.returncode == 0


def _windows_task_running_status(result: dict[str, str]) -> bool:
    return result.get("status") in {"running", "started"}


def _start_windows_task(
    task_name: str,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.25,
) -> dict[str, str]:
    state_result = _query_windows_task_state(task_name)
    if state_result["status"] == "ok":
        if state_result["state"] == "running":
            return {"status": "running"}
        if state_result["state"] == "disabled":
            return {"status": "error", "detail": f"{task_name} is disabled"}
    elif state_result["status"] == "not_found":
        return {"status": "error", "detail": f"{task_name} is not registered"}
    else:
        return {"status": "error", "detail": state_result.get("detail", "unknown scheduler error")}

    try:
        result = _run_command(
            ["schtasks", "/run", "/tn", task_name],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {"status": "error", "detail": "schtasks not found"}

    detail = (result.stderr or result.stdout or f"schtasks exit code {result.returncode}").strip()
    if result.returncode != 0:
        if "already running" in detail.lower():
            return {"status": "running"}
        return {"status": "error", "detail": detail}

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        state_result = _query_windows_task_state(task_name)
        if state_result["status"] == "ok" and state_result.get("state") == "running":
            return {"status": "started"}
        if state_result["status"] == "ok" and state_result.get("state") == "disabled":
            return {"status": "error", "detail": f"{task_name} is disabled"}
        if state_result["status"] == "error":
            return {"status": "error", "detail": state_result.get("detail", "unknown scheduler error")}
        time.sleep(poll_interval)

    state = state_result.get("state") if state_result["status"] == "ok" else state_result["status"]
    return {"status": "error", "detail": f"{task_name} did not enter running state after start (state={state})"}


def _unregister_windows_task(task_name: str) -> dict[str, str]:
    state_result = _query_windows_task_state(task_name)
    if state_result["status"] != "ok":
        if state_result["status"] == "not_found":
            return {"status": "not_found"}
        return {"status": "error", "detail": state_result.get("detail", "unknown error")}

    try:
        result = _run_command(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {"status": "error", "detail": "schtasks not found"}

    if result.returncode == 0:
        return {"status": "uninstalled"}

    detail = (result.stderr or result.stdout or f"schtasks exit code {result.returncode}").strip()
    return {"status": "error", "detail": detail}


def _collect_windows_status_results(project_root: Path) -> dict[str, str]:
    results: dict[str, str] = {}

    for service_name in SERVICES:
        spec = _build_registration_spec(service_name, project_root, platform_name="win32")
        state_result = _query_windows_task_state(spec.task_name)
        if state_result["status"] == "ok":
            results[service_name] = state_result["state"]
        elif state_result["status"] == "not_found":
            results[service_name] = "not_installed"
        else:
            results[service_name] = f"error: {state_result.get('detail', 'unknown error')}"

    legacy_state = _query_windows_task_state("Augur Nightly Maintenance")
    if legacy_state["status"] == "ok":
        results["legacy_nightly_windows_task"] = "present (needs migration)"
    elif legacy_state["status"] == "not_found":
        results["legacy_nightly_windows_task"] = "cleaned"
    else:
        results["legacy_nightly_windows_task"] = f"error: {legacy_state.get('detail', 'unknown error')}"

    return results


def _windows_task_diagnostics(spec: DaemonRegistrationSpec) -> dict[str, Any]:
    state_result = _query_windows_task_state(spec.task_name)
    expected = {
        "command": str(spec.python_path),
        "arguments": f'"{spec.daemon_script}"',
        "working_dir": str(spec.working_dir),
    }
    task: dict[str, Any] = {
        "task_name": spec.task_name,
        "status": "unknown",
        "state": None,
        "current": {},
        "expected": expected,
        "issues": [],
        "detail": "",
    }

    if state_result["status"] == "not_found":
        task.update(
            {
                "status": "not_installed",
                "detail": "scheduled task is not installed",
                "issues": ["scheduled task is not installed"],
            }
        )
        return task

    if state_result["status"] == "error":
        detail = state_result.get("detail", "unknown scheduler error")
        task.update(
            {
                "status": "error",
                "detail": detail,
                "issues": [detail],
            }
        )
        return task

    task["state"] = state_result.get("state")
    current = _read_windows_task_details(spec.task_name)
    if current is None:
        task.update(
            {
                "status": "mismatch",
                "detail": "scheduled task details are unavailable",
                "issues": ["scheduled task details unavailable"],
            }
        )
        return task

    task["current"] = current
    issues: list[str] = []
    if _normalize_windows_path(current.get("command")) != _normalize_windows_path(expected["command"]):
        issues.append("command mismatch")
    if current.get("arguments", "").strip() != expected["arguments"]:
        issues.append("arguments mismatch")
    if _normalize_windows_path(current.get("working_dir")) != _normalize_windows_path(expected["working_dir"]):
        issues.append("working directory mismatch")

    if issues:
        task.update(
            {
                "status": "mismatch",
                "issues": issues,
                "detail": ", ".join(issues),
            }
        )
        return task

    task.update(
        {
            "status": task["state"] or "installed",
            "detail": f"scheduled task is {task['state'] or 'installed'}",
        }
    )
    return task


def _collect_windows_daemon_diagnostics(project_root: Path) -> dict[str, Any]:
    spec = _build_registration_spec("daemon", project_root, platform_name="win32")
    runtime_dir = get_runtime_dir()
    logs_dir = get_logs_dir()
    status_dir = runtime_dir / "stats"
    status_path = status_dir / "daemon_status.json"
    paths = daemon_diagnostics.collect_path_checks(
        {
            "logs": logs_dir,
            "state": runtime_dir,
            "locks": runtime_dir / "locks",
            "daemon_stderr": logs_dir / "daemon" / "stderr",
            "daemon_status": status_dir,
        }
    )
    task = _windows_task_diagnostics(spec)
    status_file = daemon_diagnostics.read_daemon_status_file(status_path)
    sidecar = daemon_diagnostics.read_ai_monitor_config(project_root / "config" / "system" / "daemon.yaml")
    self_heal = daemon_diagnostics.collect_self_heal_summary(runtime_dir)
    aggregate = daemon_diagnostics.aggregate_health(task, paths, status_file, sidecar)

    return {
        **aggregate,
        "task": task,
        "paths": paths,
        "status_file": status_file,
        "sidecar": sidecar,
        "self_heal": self_heal,
    }


def _heal_windows_service_status(service_name: str) -> dict[str, str]:
    project_root = get_project_root()
    spec = _build_registration_spec(service_name, project_root, platform_name="win32")
    current = _read_windows_task_details(spec.task_name)
    expected_arguments = f'"{spec.daemon_script}"'

    if current is None:
        _out(f"Creating missing scheduled task: {spec.task_name}")
        if _register_windows_task(service_name, project_root):
            start_result = _start_windows_task(spec.task_name)
            if _windows_task_running_status(start_result):
                return {"status": "healed"}
            return {"status": "error", "detail": start_result.get("detail", f"{spec.task_name} is not running")}
        return {"status": "error", "detail": f"failed to register {spec.task_name}"}

    needs_healing = (
        _normalize_windows_path(current.get("command")) != _normalize_windows_path(str(spec.python_path))
        or current.get("arguments", "").strip() != expected_arguments
        or _normalize_windows_path(current.get("working_dir")) != _normalize_windows_path(str(spec.working_dir))
    )

    if not needs_healing:
        start_result = _start_windows_task(spec.task_name)
        if start_result.get("status") == "running":
            return {"status": "ok"}
        if _windows_task_running_status(start_result):
            return {"status": "healed"}
        return {"status": "error", "detail": start_result.get("detail", f"{spec.task_name} is not running")}

    _out(f"Path mismatch detected in scheduled task: {spec.task_name}")
    _out(f"  Task command:     {current.get('command')}")
    _out(f"  Expected:         {spec.python_path}")
    _out(f"Self-healing: recreating {spec.task_name}...")
    unregister_result = _unregister_windows_task(spec.task_name)
    if unregister_result.get("status") != "uninstalled":
        return {"status": "error", "detail": unregister_result.get("detail", f"failed to unregister {spec.task_name}")}
    success = _register_windows_task(service_name, project_root)
    if not success:
        return {"status": "error", "detail": f"failed to register {spec.task_name}"}
    start_result = _start_windows_task(spec.task_name)
    if not _windows_task_running_status(start_result):
        return {"status": "error", "detail": start_result.get("detail", f"{spec.task_name} is not running")}
    _out("Windows service healed successfully!")
    return {"status": "healed"}


def _heal_windows_service(service_name: str) -> bool:
    return _heal_windows_service_status(service_name)["status"] == "healed"


def _regenerate_macos_plist(service_name: str, project_root: Path) -> bool:
    """Regenerate a macOS LaunchAgent plist file."""
    service = SERVICES.get(service_name)
    if not service:
        return False

    plist_path = get_launch_agents_dir() / service["plist_name"]
    content = _generate_plist_content(service_name, project_root)

    if not content:
        return False

    # Ensure the preferred launch target is executable when it exists
    program_arguments = _expected_program_arguments(service_name, project_root)
    executable_path = Path(program_arguments[0])
    if executable_path.exists():
        executable_path.chmod(0o755)

    # Clear Gatekeeper quarantine on the .app bundle when we still ship one
    app_bundle = _resolve_daemon_skill_root(project_root) / _DAEMON_BUNDLE_EXECUTABLE.parent.parent.parent
    if app_bundle.exists() and app_bundle.name.endswith(".app"):
        _run_command(
            ["xattr", "-cr", str(app_bundle)],
            capture_output=True,
        )

    try:
        # Unload if exists
        if plist_path.exists():
            _run_command(["launchctl", "unload", str(plist_path)], capture_output=True)

        plist_path.write_text(content)
        _run_command(["launchctl", "load", "-w", str(plist_path)], capture_output=True)
        return True
    except Exception as e:
        _out(f"Failed to regenerate macOS plist: {e}")
        return False


def _heal_macos_service(service_name: str) -> bool:
    """Check and heal a macOS LaunchAgent service."""
    service = SERVICES.get(service_name)
    if not service:
        return False

    project_root = get_project_root()
    plist_path = get_launch_agents_dir() / service["plist_name"]

    if not plist_path.exists():
        _out(f"Creating missing plist: {service['plist_name']}")
        return _regenerate_macos_plist(service_name, project_root)

    install_issue = _service_install_issue(service_name, project_root, plist_path)
    if install_issue:
        current_paths = _read_plist_paths(plist_path)
        _out(f"Path mismatch detected in {service['plist_name']}")
        _out(f"  Install issue:    {install_issue}")
        _out(f"  Plist executable: {current_paths.get('executable')}")
        _out(f"  Expected:         {_expected_program_arguments(service_name, project_root)[0]}")
        _out(f"Self-healing: regenerating {service['plist_name']}...")
        success = _regenerate_macos_plist(service_name, project_root)
        if success:
            _out("macOS service healed successfully!")
        return success

    return False


# =============================================================================
# Legacy Migration
# =============================================================================


def cleanup_legacy_services() -> dict:
    """Remove old individual service plists (pre-unified-daemon)."""
    results = {}

    if sys.platform == "win32":
        unregister_result = _unregister_windows_task("Augur Nightly Maintenance")
        if unregister_result["status"] == "uninstalled":
            return {"nightly_windows_task": "removed"}
        if unregister_result["status"] == "not_found":
            return {"nightly_windows_task": "not_found"}
        return {"nightly_windows_task": f"error: {unregister_result.get('detail', 'unknown error')}"}

    if sys.platform != "darwin":
        return {"error": "Only macOS and Windows are currently supported"}

    for name, service in LEGACY_SERVICES.items():
        plist_path = get_launch_agents_dir() / service["plist_name"]

        if not plist_path.exists():
            results[name] = "not_found"
        else:
            try:
                _run_command(["launchctl", "unload", str(plist_path)], capture_output=True)
                plist_path.unlink()
                results[name] = "removed"
            except Exception as e:
                results[name] = f"error: {e}"

    return results


def _reset_background_activity() -> bool:
    """Reset macOS Background Activity cache to clear stale entries.

    Uses sfltool resetbtm (macOS 13+) to clear the BTM database.
    After reset, the user may need to re-approve the new daemon.
    """
    try:
        result = _run_command(
            ["sfltool", "resetbtm"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # sfltool not available (pre-macOS 13)
        return False


# =============================================================================
# Attention Sync (ADR-435 step 2.5)
# =============================================================================

# Interval between attention sync cycles (seconds).
# Override with AUGUR_ATTENTION_SYNC_INTERVAL env var.
_ATTENTION_SYNC_INTERVAL = int(os.environ.get("AUGUR_ATTENTION_SYNC_INTERVAL", "300"))

# Track last sync time at module level so callers in the daemon loop can
# invoke _check_attention_sync() every iteration; the function itself
# enforces the interval.
_last_attention_sync: float = 0.0


def _check_attention_sync() -> dict:
    """Run attention system Reminders sync cycle.

    Interval: every 5 minutes (configurable via AUGUR_ATTENTION_SYNC_INTERVAL).
    Imports the attention skill's sync_reminders module lazily so this
    function degrades gracefully when the attention skill is not installed.

    Returns a dict with sync results or an error description.
    """
    global _last_attention_sync

    now = time.time()
    if now - _last_attention_sync < _ATTENTION_SYNC_INTERVAL:
        return {"skipped": True, "reason": "interval_not_elapsed"}

    _last_attention_sync = now

    try:
        # Lazy import — the attention skill may not be installed
        from src.config.paths import get_skill_root

        attention_scripts = get_skill_root("attention") / "scripts"
        if str(attention_scripts) not in sys.path:
            sys.path.insert(0, str(attention_scripts))

        from sync_reminders import sync_cycle_default  # type: ignore[import-untyped]

        result = sync_cycle_default()
        pushed = result.get("pushed", 0)
        resolved = result.get("resolved", 0)
        logger.info(
            "Attention sync complete: pushed %d, resolved %d", pushed, resolved,
        )
        return result
    except (ImportError, ValueError):
        logger.debug("Attention skill not installed, skipping sync")
        return {"skipped": True, "reason": "attention_skill_not_installed"}
    except Exception as exc:
        logger.warning("Attention sync failed: %s", exc)
        return {"error": str(exc)}


# =============================================================================
# Critical Action Executor (ADR-435 step 2.5)
# =============================================================================

# Maximum critical action executions per hour.
_MAX_CRITICAL_EXECUTIONS_PER_HOUR = 3

# Track execution timestamps for rate limiting.
_critical_exec_timestamps: list[float] = []

# Track in-flight processes: mapping action_id -> Popen object
_critical_processes: dict[str, Popen] = {}  # type: ignore[type-arg]


def _get_attention_dirs() -> dict[str, Path]:
    """Resolve attention system vault directories."""
    vault = get_vault_dir()
    base = vault / "admin" / "attention" / "pending-actions"
    return {
        "critical": base / "critical",
        "processing": base / "processing",
        "failed": base / "failed",
        "log": vault / "admin" / "attention" / "execution-log.yaml",
    }


def _check_critical_rate_limit() -> bool:
    """Return True if we can execute another critical action this hour."""
    global _critical_exec_timestamps
    one_hour_ago = time.time() - 3600
    _critical_exec_timestamps = [
        t for t in _critical_exec_timestamps if t > one_hour_ago
    ]
    return len(_critical_exec_timestamps) < _MAX_CRITICAL_EXECUTIONS_PER_HOUR


def _append_execution_log(log_path: Path, entry: dict) -> None:
    """Append an entry to the execution log YAML file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if log_path.exists():
        try:
            raw = yaml.safe_load(log_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = raw
        except Exception:
            pass

    existing.append(entry)

    # Keep last 200 entries to prevent unbounded growth
    if len(existing) > 200:
        existing = existing[-200:]

    log_path.write_text(
        yaml.safe_dump(existing, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _check_completed_actions() -> int:
    """Check in-flight critical processes for completion.

    Moves completed actions to execution log (success) or failed dir.
    Returns number of completed processes checked.
    """
    dirs = _get_attention_dirs()
    completed = 0

    for action_id, proc in list(_critical_processes.items()):
        exit_code = proc.poll()
        if exit_code is None:
            # Still running
            continue

        completed += 1
        processing_file = dirs["processing"] / f"{action_id}.yaml"

        if exit_code == 0:
            # Success — log and remove from processing
            _append_execution_log(dirs["log"], {
                "id": action_id,
                "status": "success",
                "exit_code": exit_code,
                "completed_at": datetime.now().isoformat(),
            })
            if processing_file.exists():
                processing_file.unlink()
            logger.info("Critical action %s completed successfully", action_id)
        else:
            # Failure — move to failed dir, log, create new attention item
            _append_execution_log(dirs["log"], {
                "id": action_id,
                "status": "failed",
                "exit_code": exit_code,
                "completed_at": datetime.now().isoformat(),
            })
            dirs["failed"].mkdir(parents=True, exist_ok=True)
            failed_file = dirs["failed"] / f"{action_id}.yaml"
            if processing_file.exists():
                processing_file.rename(failed_file)

                # Enrich with failure metadata
                try:
                    data = yaml.safe_load(failed_file.read_text(encoding="utf-8")) or {}
                    data["failed_at"] = datetime.now().isoformat()
                    data["exit_code"] = exit_code
                    failed_file.write_text(
                        yaml.safe_dump(data, default_flow_style=False, allow_unicode=True),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

            logger.warning(
                "Critical action %s failed (exit %d), moved to failed/",
                action_id, exit_code,
            )

            # Raise attention item so the failure surfaces in the triage UI
            try:
                from channels.augur.lib.registry import raise_attention  # type: ignore[import-untyped]

                raise_attention(
                    skill="daemon",
                    source_type="notification",
                    title=f"Critical action failed (exit {exit_code})",
                    priority="critical",
                )
            except Exception:
                logger.debug("Could not raise attention for failed action %s", action_id)

        del _critical_processes[action_id]

    return completed


def _execute_critical_actions() -> int:
    """Check for approved critical actions and dispatch via claude -p.

    Max 3 executions per hour to control cost.
    Scans pending-actions/critical/ for .yaml files.

    Returns number of actions dispatched this cycle.
    """
    # First, check any in-flight processes from previous cycles
    _check_completed_actions()

    dirs = _get_attention_dirs()
    critical_dir = dirs["critical"]
    processing_dir = dirs["processing"]

    if not critical_dir.is_dir():
        return 0

    # Find claude binary
    claude_bin = shutil.which("claude")
    if not claude_bin:
        logger.debug("claude CLI not found on PATH, skipping critical action execution")
        return 0

    dispatched = 0

    for action_file in sorted(critical_dir.glob("*.yaml")):
        if not _check_critical_rate_limit():
            logger.info(
                "Critical action rate limit reached (%d/hour), deferring remaining",
                _MAX_CRITICAL_EXECUTIONS_PER_HOUR,
            )
            break

        try:
            data = yaml.safe_load(action_file.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("Cannot read action file %s: %s", action_file, exc)
            continue

        action_id = data.get("id", action_file.stem)
        action_prompt = data.get("action_prompt") or data.get("prompt")

        if not action_prompt:
            # Build a default prompt from action metadata
            action = data.get("action", "execute")
            title = data.get("reminder_title", data.get("title", ""))
            target = data.get("target", "")
            action_prompt = (
                f"Execute approved attention action: {action}. "
                f"Item: {title}. "
                f"{'Target: ' + target + '. ' if target else ''}"
                f"Action ID: {action_id}."
            )

        # Skip if already in processing (from a previous cycle)
        if action_id in _critical_processes:
            continue

        # Move to processing state
        processing_dir.mkdir(parents=True, exist_ok=True)
        processing_file = processing_dir / action_file.name
        try:
            data["dispatched_at"] = datetime.now().isoformat()
            processing_file.write_text(
                yaml.safe_dump(data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
            action_file.unlink()
        except Exception as exc:
            logger.warning("Failed to move action %s to processing: %s", action_id, exc)
            continue

        # Dispatch via claude -p (non-blocking)
        try:
            proc = Popen(  # nosec B603
                _resolve_command([claude_bin, "-p", action_prompt]),
                stdout=DEVNULL,
                stderr=DEVNULL,
                cwd=str(get_project_root()),
                creationflags=_NO_WINDOW_CREATIONFLAGS,
            )
            _critical_processes[action_id] = proc
            _critical_exec_timestamps.append(time.time())
            dispatched += 1
            logger.info(
                "Dispatched critical action %s (PID %d): %s",
                action_id, proc.pid, action_prompt[:80],
            )
        except Exception as exc:
            logger.warning("Failed to dispatch action %s: %s", action_id, exc)
            # Move back to critical dir on dispatch failure
            try:
                processing_file.rename(action_file)
            except Exception:
                pass

    return dispatched


# =============================================================================
# Cross-Platform API
# =============================================================================


def heal_service_if_needed(service_name: str) -> bool:
    """Check if a background service needs healing and fix it."""
    if sys.platform == "darwin":
        return _heal_macos_service(service_name)
    if sys.platform == "win32":
        return _heal_windows_service(service_name)
    return False


def heal_all_services() -> dict:
    """Heal all augur background services.

    Also runs attention sync and critical action checks alongside
    the standard service health checks (ADR-435).
    """
    results: dict[str, Any] = {}

    if sys.platform == "win32":
        for service_name in SERVICES.keys():
            try:
                status = _heal_windows_service_status(service_name)
                if status["status"] == "error":
                    results[service_name] = f"error: {status.get('detail', 'unknown error')}"
                else:
                    results[service_name] = status["status"]
            except Exception as e:
                results[service_name] = f"error: {e}"
    else:
        for service_name in SERVICES.keys():
            try:
                healed = heal_service_if_needed(service_name)
                results[service_name] = "healed" if healed else "ok"
            except Exception as e:
                results[service_name] = f"error: {e}"

    # ADR-435: Attention sync (respects its own interval internally)
    try:
        sync_result = _check_attention_sync()
        if sync_result.get("skipped"):
            results["attention_sync"] = f"skipped ({sync_result.get('reason', '')})"
        elif "error" in sync_result:
            results["attention_sync"] = f"error: {sync_result['error']}"
        else:
            pushed = sync_result.get("pushed", 0)
            resolved = sync_result.get("resolved", 0)
            results["attention_sync"] = f"pushed={pushed} resolved={resolved}"
    except Exception as e:
        results["attention_sync"] = f"error: {e}"

    # ADR-435: Critical action execution
    try:
        dispatched = _execute_critical_actions()
        in_flight = len(_critical_processes)
        results["critical_actions"] = f"dispatched={dispatched} in_flight={in_flight}"
    except Exception as e:
        results["critical_actions"] = f"error: {e}"

    return results


def install_services() -> dict:
    """Install the unified daemon (creates plist if missing)."""
    project_root = get_project_root()
    results = {}

    if sys.platform == "win32":
        for service_name in SERVICES:
            try:
                spec = _build_registration_spec(service_name, project_root, platform_name="win32")
                success = _register_windows_task(service_name, project_root)
                if not success:
                    results[service_name] = "failed"
                    continue
                start_result = _start_windows_task(spec.task_name)
                if _windows_task_running_status(start_result):
                    results[service_name] = "running"
                else:
                    results[service_name] = f"error: {start_result.get('detail', f'{spec.task_name} is not running')}"
            except Exception as e:
                results[service_name] = f"error: {e}"
        return results

    if sys.platform != "darwin":
        return {"error": "Only macOS and Windows are currently supported"}

    for service_name, service in SERVICES.items():
        plist_path = get_launch_agents_dir() / service["plist_name"]
        install_issue = _service_install_issue(service_name, project_root, plist_path)

        if install_issue is None:
            results[service_name] = "already_installed"
        else:
            success = _regenerate_macos_plist(service_name, project_root)
            if success:
                results[service_name] = "installed" if install_issue == "missing_plist" else "healed"
            else:
                results[service_name] = "failed"

    return results


def _service_status_failed(status: object) -> bool:
    text = str(status).strip().lower()
    return (
        text == "failed"
        or text in {"degraded", "disabled", "not_running", "not_installed"}
        or text.startswith("error:")
    )


def _service_results_failed(results: dict) -> bool:
    for service_name, status in results.items():
        if isinstance(status, dict):
            if _service_results_failed(status):
                return True
            continue
        if service_name in SERVICES and _service_status_failed(status):
            return True
    return False


def uninstall_services() -> dict:
    """Uninstall the unified daemon."""
    results = {}

    if sys.platform == "win32":
        project_root = get_project_root()
        for service_name in SERVICES:
            spec = _build_registration_spec(service_name, project_root, platform_name="win32")
            unregister_result = _unregister_windows_task(spec.task_name)
            if unregister_result["status"] == "uninstalled":
                results[service_name] = "uninstalled"
            elif unregister_result["status"] == "not_found":
                results[service_name] = "not_installed"
            else:
                results[service_name] = f"error: {unregister_result.get('detail', 'unknown error')}"
        return results

    if sys.platform != "darwin":
        return {"error": "Only macOS and Windows are currently supported"}

    for service_name, service in SERVICES.items():
        plist_path = get_launch_agents_dir() / service["plist_name"]

        if not plist_path.exists():
            results[service_name] = "not_installed"
        else:
            try:
                _run_command(["launchctl", "unload", str(plist_path)], capture_output=True)
                plist_path.unlink()
                results[service_name] = "uninstalled"
            except Exception as e:
                results[service_name] = f"error: {e}"

    return results


def migrate_to_unified() -> dict:
    """Full migration: cleanup legacy plists, install unified daemon, reset BTM."""
    results = {}

    _out("Step 1: Cleaning up legacy services...")
    legacy_results = cleanup_legacy_services()
    results["legacy_cleanup"] = legacy_results
    for name, status in legacy_results.items():
        icon = "removed" if status == "removed" else status
        _out(f"  {name}: {icon}")

    _out("\nStep 2: Installing unified daemon...")
    install_results = install_services()
    results["install"] = install_results
    for name, status in install_results.items():
        _out(f"  {name}: {status}")

    _out("\nStep 3: Resetting Background Activity cache...")
    btm_reset = _reset_background_activity()
    results["btm_reset"] = "success" if btm_reset else "skipped (macOS 13+ required)"
    _out(f"  BTM reset: {results['btm_reset']}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Augur Background Service Manager")
    parser.add_argument(
        "action",
        choices=["heal", "install", "uninstall", "status", "migrate"],
        help="Action to perform",
    )
    args = parser.parse_args()

    _out("Augur Service Manager")
    _out(f"  Platform: {sys.platform}")
    _out(f"  Project root: {get_project_root()}")
    _out("=" * 50)

    if args.action == "heal":
        _out("\nHealing Services:")
        results = heal_all_services()
    elif args.action == "install":
        _out("\nInstalling Services:")
        results = install_services()
    elif args.action == "uninstall":
        _out("\nUninstalling Services:")
        results = uninstall_services()
    elif args.action == "migrate":
        _out("\nMigrating to Unified Daemon:")
        results = migrate_to_unified()
    elif args.action == "status":
        _out("\nService Status:")
        results = {}
        if sys.platform == "win32":
            project_root = get_project_root()
            diagnostics = _collect_windows_daemon_diagnostics(project_root)
            results = _collect_windows_status_results(project_root)
            results["daemon"] = diagnostics["health"]
            task = diagnostics["task"]
            status_file = diagnostics["status_file"]
            sidecar = diagnostics["sidecar"]
            self_heal = diagnostics["self_heal"]
            _out(f"  Health: {diagnostics['health']}")
            _out(f"  Scheduled task: {task['status']} ({task.get('state') or 'state unavailable'})")
            if task.get("detail"):
                _out(f"    detail: {task['detail']}")
            _out(f"    expected command: {task['expected']['command']}")
            _out(f"    current command: {task.get('current', {}).get('command', 'unavailable')}")
            _out(f"  Status file: {status_file.get('status')} ({status_file.get('path')})")
            _out(f"  AI monitor: {sidecar.get('status')} ({sidecar.get('detail', 'no detail')})")
            _out(f"  Self-heal: {self_heal.get('status')} ({self_heal.get('summary')})")
            _out("  Issues:")
            if diagnostics["issues"]:
                for issue in diagnostics["issues"]:
                    _out(f"    - {issue}")
            else:
                _out("    - none")
            _out("\n  Legacy Services:")
            _out(f"    nightly_windows_task: {results['legacy_nightly_windows_task']}")
        else:
            for service_name, service in SERVICES.items():
                plist_path = get_launch_agents_dir() / service["plist_name"]
                if plist_path.exists():
                    label = service["plist_name"].replace(".plist", "")
                    install_issue = _service_install_issue(service_name, get_project_root(), plist_path)
                    if install_issue is not None:
                        results[service_name] = f"broken_install ({install_issue})"
                    else:
                        result = _run_command(
                            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                            capture_output=True,
                            text=True,
                        )
                        active_match = re.search(r"active count = (\d+)", result.stdout or "")
                        active_count = int(active_match.group(1)) if active_match else 0
                        results[service_name] = "running" if result.returncode == 0 and active_count > 0 else "stopped"
                else:
                    results[service_name] = "not_installed"

            # Also check legacy services
            _out("\n  Legacy Services:")
            for name, service in LEGACY_SERVICES.items():
                plist_path = get_launch_agents_dir() / service["plist_name"]
                status = "present (needs migration)" if plist_path.exists() else "cleaned"
                results[f"legacy_{name}"] = status
                _out(f"    {name}: {status}")

    if args.action != "migrate":
        for service, status in results.items():
            if service.startswith("legacy_"):
                continue
            icon = "OK" if status in ("ok", "healthy", "healed", "installed", "running", "already_installed") else "!!"
            _out(f"  [{icon}] {service}: {status}")

    raise SystemExit(1 if _service_results_failed(results) else 0)
