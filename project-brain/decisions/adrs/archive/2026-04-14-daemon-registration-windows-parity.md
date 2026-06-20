# Daemon Registration Windows Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Augur daemon registration truly cross-platform by keeping the current macOS LaunchAgent lifecycle and adding a per-user Windows Task Scheduler backend with matching install, heal, status, uninstall, and migration behavior.

**Architecture:** Keep `skills/daemon/scripts/service_healer.py` as the single daemon lifecycle entrypoint, but refactor it around a shared daemon registration spec instead of plist-specific assumptions. Render that spec through two backends: macOS LaunchAgent on Darwin and Task Scheduler on Windows. Update status readers and daemon-facing docs so they stop assuming LaunchAgents are the universal registration model.

**Tech Stack:** Python 3.11, PowerShell 5.1+, Windows Task Scheduler XML / `schtasks`, macOS launchd plist rendering, pytest, GitHub Actions YAML

**Spec:** `docs/superpowers/specs/2026-04-14-daemon-registration-windows-parity-design.md`

---

### Task 1: Extract A Shared Daemon Registration Spec

**Files:**
- Create: `skills/daemon/augur/tests/test_service_healer_registration.py`
- Modify: `skills/daemon/scripts/service_healer.py`
- Reference: `src/config/paths.py`

- [ ] **Step 1: Write the failing registration-spec tests**

```python
# skills/daemon/augur/tests/test_service_healer_registration.py
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def test_service_label_and_task_name_are_project_scoped():
    import service_healer

    with patch.object(service_healer, "get_project_name", return_value="AugurOS"):
        assert service_healer._service_label() == "com.auguros.daemon"
        assert service_healer._task_name() == "com.auguros.daemon"
        assert service_healer._plist_filename() == "com.auguros.daemon.plist"


def test_build_registration_spec_windows_uses_repo_venv_and_unified_daemon(tmp_path):
    import service_healer

    project_root = tmp_path / "repo"
    logs_dir = tmp_path / "logs"
    project_root.mkdir()
    logs_dir.mkdir()

    with patch.object(service_healer, "get_logs_dir", return_value=logs_dir), patch.object(
        service_healer, "_service_label", return_value="com.augur.daemon"
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
    assert spec.daemon_script == project_root / "skills" / "daemon" / "scripts" / "unified_daemon.py"
    assert spec.python_path == project_root / ".venv" / "Scripts" / "python.exe"
    assert spec.stdout_path == logs_dir / "daemon.stdout.log"
    assert spec.stderr_path == logs_dir / "daemon.stderr.log"


def test_render_windows_task_xml_includes_logon_trigger_restart_and_working_directory(tmp_path):
    import service_healer

    spec = service_healer.DaemonRegistrationSpec(
        label="com.augur.daemon",
        plist_name="com.augur.daemon.plist",
        task_name="com.augur.daemon",
        working_dir=tmp_path / "repo",
        daemon_script=tmp_path / "repo" / "skills" / "daemon" / "scripts" / "unified_daemon.py",
        python_path=tmp_path / "repo" / ".venv" / "Scripts" / "python.exe",
        macos_app_executable=tmp_path / "repo" / "skills" / "daemon" / "assets" / "bundle" / "Augur Daemon.app" / "Contents" / "MacOS" / "Augur",
        stdout_path=tmp_path / "logs" / "daemon.stdout.log",
        stderr_path=tmp_path / "logs" / "daemon.stderr.log",
    )

    xml = service_healer._render_windows_task_xml(spec, user_id="tester")

    assert "<LogonTrigger>" in xml
    assert "<Command>" in xml and "python.exe" in xml
    assert "<Arguments>" in xml and "unified_daemon.py" in xml
    assert "<WorkingDirectory>" in xml
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
    assert "<RestartOnFailure>" in xml
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py -q
```

Expected:

```text
FAIL ... _task_name ...
FAIL ... _build_registration_spec ...
FAIL ... _render_windows_task_xml ...
```

- [ ] **Step 3: Implement the shared registration dataclass and helpers**

```python
# skills/daemon/scripts/service_healer.py
from dataclasses import dataclass


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
    platform_name = platform_name or sys.platform
    label = _service_label()
    daemon_script = project_root / "skills" / "daemon" / "scripts" / "unified_daemon.py"
    stdout_path = get_logs_dir() / "daemon.stdout.log"
    stderr_path = get_logs_dir() / "daemon.stderr.log"
    if platform_name == "win32":
        python_path = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        python_path = project_root / ".venv" / "bin" / "python"

    return DaemonRegistrationSpec(
        label=label,
        plist_name=f"{label}.plist",
        task_name=label,
        working_dir=project_root,
        daemon_script=daemon_script,
        python_path=python_path,
        macos_app_executable=project_root / "skills" / "daemon" / "assets" / "bundle" / "Augur Daemon.app" / "Contents" / "MacOS" / "Augur",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
```

- [ ] **Step 4: Rework plist generation to consume the shared spec**

```python
# skills/daemon/scripts/service_healer.py
def _generate_plist_content(service_name: str, project_root: Path) -> Optional[str]:
    service = SERVICES.get(service_name)
    if not service:
        return None

    spec = _build_registration_spec(service_name, project_root, platform_name="darwin")
    spec.stdout_path.parent.mkdir(parents=True, exist_ok=True)
    template_path = _get_plist_templates_dir(project_root) / service.get("template", "daemon.plist.template")
    return _render_template(
        template_path,
        {
            "__LABEL__": spec.label,
            "__EXECUTABLE__": str(spec.macos_app_executable),
            "__WORKING_DIRECTORY__": str(spec.working_dir),
            "__STDOUT__": str(spec.stdout_path),
            "__STDERR__": str(spec.stderr_path),
        },
    )
```

- [ ] **Step 5: Run the focused tests to verify green**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit the shared registration-spec extraction**

```bash
git add skills/daemon/scripts/service_healer.py skills/daemon/augur/tests/test_service_healer_registration.py
git commit -m "refactor(daemon): extract shared registration spec"
```

### Task 2: Implement The Windows Task Scheduler Backend

**Files:**
- Modify: `skills/daemon/scripts/service_healer.py`
- Modify: `skills/daemon/augur/tests/test_service_healer_registration.py`

- [ ] **Step 1: Add failing Windows backend routing tests**

```python
# skills/daemon/augur/tests/test_service_healer_registration.py
@patch("sys.platform", "win32")
def test_install_services_windows_uses_task_scheduler_backend():
    import service_healer

    with patch.object(service_healer, "get_project_root", return_value=Path("/repo")), patch.object(
        service_healer, "_register_windows_task", return_value=True
    ) as register:
        result = service_healer.install_services()

    assert result["daemon"] == "installed"
    register.assert_called_once_with("daemon", Path("/repo"))


@patch("sys.platform", "win32")
def test_heal_service_windows_uses_windows_backend():
    import service_healer

    with patch.object(service_healer, "_heal_windows_service", return_value=True) as heal:
        assert service_healer.heal_service_if_needed("daemon") is True

    heal.assert_called_once_with("daemon")


@patch("sys.platform", "win32")
def test_cleanup_legacy_services_windows_removes_old_nightly_task():
    import service_healer

    with patch.object(service_healer, "_unregister_windows_task", return_value=True) as unregister:
        result = service_healer.cleanup_legacy_services()

    assert result["nightly_windows_task"] == "removed"
    unregister.assert_called_once_with("Augur Nightly Maintenance")
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py -q
```

Expected:

```text
FAIL ... _register_windows_task ...
FAIL ... _heal_windows_service ...
FAIL ... _unregister_windows_task ...
```

- [ ] **Step 3: Implement Task Scheduler XML rendering and registration helpers**

```python
# skills/daemon/scripts/service_healer.py
def _render_windows_task_xml(spec: DaemonRegistrationSpec, user_id: str) -> str:
    arguments = f'"{spec.daemon_script}"'
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user_id}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_id}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{spec.python_path}</Command>
      <Arguments>{arguments}</Arguments>
      <WorkingDirectory>{spec.working_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _register_windows_task(service_name: str, project_root: Path) -> bool:
    spec = _build_registration_spec(service_name, project_root, platform_name="win32")
    user_id = os.environ.get("USERNAME", "")
    xml = _render_windows_task_xml(spec, user_id=user_id)
    xml_path = get_runtime_dir() / "daemon" / f"{spec.task_name}.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml, encoding="utf-16")
    result = _run_command(
        ["schtasks", "/create", "/tn", spec.task_name, "/xml", str(xml_path), "/f"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _unregister_windows_task(task_name: str) -> bool:
    result = _run_command(
        ["schtasks", "/delete", "/tn", task_name, "/f"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
```

- [ ] **Step 4: Route install, heal, uninstall, cleanup, and status through the Windows backend**

```python
# skills/daemon/scripts/service_healer.py
def _heal_windows_service(service_name: str) -> bool:
    project_root = get_project_root()
    spec = _build_registration_spec(service_name, project_root, platform_name="win32")
    current = _read_windows_task_details(spec.task_name)
    expected_command = str(spec.python_path)
    expected_args = f'"{spec.daemon_script}"'
    expected_workdir = str(spec.working_dir)
    if not current:
        return _register_windows_task(service_name, project_root)
    needs_healing = (
        current.get("command") != expected_command
        or current.get("arguments") != expected_args
        or current.get("working_dir") != expected_workdir
    )
    if not needs_healing:
        return False
    _unregister_windows_task(spec.task_name)
    return _register_windows_task(service_name, project_root)


def heal_service_if_needed(service_name: str) -> bool:
    if sys.platform == "darwin":
        return _heal_macos_service(service_name)
    if sys.platform == "win32":
        return _heal_windows_service(service_name)
    return False


def cleanup_legacy_services() -> dict:
    if sys.platform == "win32":
        removed = _unregister_windows_task("Augur Nightly Maintenance")
        return {"nightly_windows_task": "removed" if removed else "not_found"}
    if sys.platform != "darwin":
        return {"error": "Only macOS and Windows are currently supported"}
    ...


def install_services() -> dict:
    project_root = get_project_root()
    results = {}
    if sys.platform == "win32":
        for service_name in SERVICES:
            success = _register_windows_task(service_name, project_root)
            results[service_name] = "installed" if success else "failed"
        return results
    if sys.platform != "darwin":
        return {"error": "Only macOS and Windows are currently supported"}
    ...
```

- [ ] **Step 5: Re-run the Windows backend tests to verify green**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 6: Commit the Windows Task Scheduler backend**

```bash
git add skills/daemon/scripts/service_healer.py skills/daemon/augur/tests/test_service_healer_registration.py
git commit -m "feat(daemon): add windows task scheduler backend"
```

### Task 3: Update Windows Wrapper And Cross-Platform Status Surfaces

**Files:**
- Modify: `skills/daemon/scripts/setup_scheduled_task.ps1`
- Create: `skills/observe/augur/tests/test_daemon_status_runtime.py`
- Modify: `skills/observe/scripts/daemon_status.py`
- Modify: `skills/observe/scripts/mcp/tools_read.py`

- [ ] **Step 1: Add failing tests for the Windows wrapper and daemon status shape**

```python
# skills/observe/augur/tests/test_daemon_status_runtime.py
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_collect_status_windows_reports_task_scheduler_registration():
    from skills.observe.scripts import daemon_status

    with patch.object(
        daemon_status,
        "check_daemon_installed",
        return_value=(True, {"registrationType": "task-scheduler", "registrationPath": "\\\\Augur\\\\com.augur.daemon"}),
    ), patch.object(daemon_status, "check_daemon_running", return_value=(True, 12345)), patch.object(
        daemon_status, "load_self_heal_config", return_value={"enabled": True, "routing": {}}
    ), patch.object(
        daemon_status, "load_registry_summary", return_value={"total": 0, "active": 0, "fixed": 0, "dismissed": 0, "last_scan": None}
    ), patch.object(
        daemon_status, "load_daemon_runtime_status", return_value={}
    ), patch.object(
        daemon_status, "collect_system_info", return_value={}
    ):
        result = daemon_status.collect_status(Path("/repo"))

    assert result["daemon"]["registrationType"] == "task-scheduler"
    assert result["daemon"]["registrationPath"] == "\\\\Augur\\\\com.augur.daemon"


def test_setup_scheduled_task_script_wraps_service_healer():
    script_path = PROJECT_ROOT / "skills" / "daemon" / "scripts" / "setup_scheduled_task.ps1"
    content = script_path.read_text(encoding="utf-8")

    assert "service_healer.py" in content
    assert "Augur Nightly Maintenance" not in content
    assert "Requires administrative privileges" not in content
```

- [ ] **Step 2: Run the status and wrapper tests to verify they fail**

Run:

```bash
uv run pytest skills/observe/augur/tests/test_daemon_status_runtime.py -q
```

Expected:

```text
FAIL ... registrationType ...
FAIL ... Augur Nightly Maintenance ...
```

- [ ] **Step 3: Replace the old nightly-only PowerShell task script with a thin daemon wrapper**

```powershell
# skills/daemon/scripts/setup_scheduled_task.ps1
[CmdletBinding()]
param(
    [ValidateSet("install", "uninstall", "status", "heal")]
    [string]$Action = "install",
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
if (-not $InstallDir) {
    $InstallDir = if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\\augur" }
}

$PythonPath = Join-Path $InstallDir ".venv\\Scripts\\python.exe"
$ServiceHealer = Join-Path $InstallDir "skills\\daemon\\scripts\\service_healer.py"

if (-not (Test-Path $PythonPath)) { throw "Python not found at $PythonPath" }
if (-not (Test-Path $ServiceHealer)) { throw "service_healer.py not found at $ServiceHealer" }

Push-Location $InstallDir
try {
    & $PythonPath $ServiceHealer $Action
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
```

- [ ] **Step 4: Make daemon status output registration-type aware instead of plist-only**

```python
# skills/observe/scripts/daemon_status.py
def check_daemon_installed() -> tuple[bool, dict[str, str]]:
    if platform.system() == "Windows":
        task_name = "com.augur.daemon"
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, {
            "registrationType": "task-scheduler",
            "registrationPath": task_name,
        }

    plist_path = get_launch_agents_dir() / "com.augur.daemon.plist"
    return plist_path.is_file(), {
        "registrationType": "launchd",
        "registrationPath": str(plist_path),
    }


def collect_status(root: Path) -> dict:
    installed, registration = check_daemon_installed()
    ...
    return {
        "daemon": {
            "installed": installed,
            "running": running,
            "pid": runtime_status.get("daemon_pid", pid) if isinstance(runtime_status, dict) else pid,
            "registrationType": registration.get("registrationType"),
            "registrationPath": registration.get("registrationPath"),
            "startedAt": started_at,
        },
        ...
    }
```

```python
# skills/observe/scripts/mcp/tools_read.py
result = {
    "status": "ok" if running else "degraded",
    "skill": "daemon",
    "timestamp": data.get("generatedAt") or datetime.now().isoformat(),
    "daemon": {
        "status": "running" if running else "stopped",
        "pid": daemon_info.get("pid"),
        "uptime_seconds": process_info.get("uptime_seconds"),
        "installed": daemon_info.get("installed", False),
        "registrationType": daemon_info.get("registrationType"),
        "registrationPath": daemon_info.get("registrationPath"),
    },
    ...
}
```

- [ ] **Step 5: Run the focused tests to verify green**

Run:

```bash
uv run pytest skills/observe/augur/tests/test_daemon_status_runtime.py skills/daemon/augur/tests/test_service_healer_registration.py -q
```

Expected:

```text
8 passed
```

- [ ] **Step 6: Commit the wrapper and status-surface updates**

```bash
git add skills/daemon/scripts/setup_scheduled_task.ps1 skills/observe/scripts/daemon_status.py skills/observe/scripts/mcp/tools_read.py skills/observe/augur/tests/test_daemon_status_runtime.py
git commit -m "feat(daemon): expose windows registration status"
```

### Task 4: Refresh Daemon Command Surface And Windows Verification

**Files:**
- Modify: `skills/daemon/commands/ops-daemon.md`
- Modify: `skills/daemon/SKILL.md`
- Modify: `skills/daemon/references/launchd-usage.md`
- Create: `skills/daemon/references/windows-task-usage.md`
- Modify: `.github/workflows/ci-cross-platform.yml`

- [ ] **Step 1: Add a Windows daemon backend smoke test to CI**

```yaml
# .github/workflows/ci-cross-platform.yml
      - name: Smoke test daemon registration spec (Windows)
        if: runner.os == 'Windows'
        run: |
          .\.venv\Scripts\Activate.ps1
          uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py skills/observe/augur/tests/test_daemon_status_runtime.py -q
```

- [ ] **Step 2: Rewrite `/daemon` docs to be platform-neutral at the top**

Update `skills/daemon/commands/ops-daemon.md` so the opening section says:

- Augur manages the unified daemon as an OS-level background service.
- macOS uses `launchd`.
- Windows uses `Task Scheduler`.
- `service_healer.py` is the install / heal / uninstall entrypoint on both platforms.

Include these exact command examples in the doc:

```bash
python3 skills/daemon/scripts/service_healer.py status
python3 skills/daemon/scripts/unified_daemon.py status
python3 skills/daemon/scripts/service_healer.py install
python skills/daemon/scripts/service_healer.py install
```

Add one Windows-specific note in prose:

- On Windows, the same install command runs under the repo venv Python and registers a per-user scheduled task rather than a LaunchAgent.

- [ ] **Step 3: Add a Windows daemon usage reference and link it from the skill**

Create `skills/daemon/references/windows-task-usage.md` with this structure:

- Title: `# Daemon Usage (Task Scheduler)`
- Opening rule: the Augur daemon is a per-user scheduled task on Windows, and `unified_daemon.py start` must not be run as a child of an AI client shell.
- Sections:
  - `Install / Start`
  - `Status`
  - `Stop / Uninstall`

Include these exact command examples in the new reference:

```powershell
python skills/daemon/scripts/service_healer.py install
schtasks /query /tn "com.augur.daemon"
python skills/daemon/scripts/unified_daemon.py status
python skills/daemon/scripts/service_healer.py uninstall
```

Update `skills/daemon/SKILL.md` so it:

- mentions both `launchd` and `Task Scheduler` in the description / usage guidance
- links readers to `references/launchd-usage.md` for macOS
- links readers to `references/windows-task-usage.md` for Windows

- [ ] **Step 4: Verify daemon docs and Windows references no longer claim LaunchAgent-only ownership**

Run:

```bash
rg -n 'via launchd\\.|Always use `launchctl|LaunchAgent plist|Augur Nightly Maintenance' skills/daemon/commands/ops-daemon.md skills/daemon/SKILL.md skills/daemon/references/launchd-usage.md skills/daemon/references/windows-task-usage.md skills/daemon/scripts/setup_scheduled_task.ps1
```

Expected:

```text
skills/daemon/references/launchd-usage.md:... launchd ...
```

Only the macOS-specific reference should still contain raw launchd-only wording.

- [ ] **Step 5: Run the final focused verification**

Run:

```bash
uv run pytest skills/daemon/augur/tests/test_service_healer_registration.py skills/observe/augur/tests/test_daemon_status_runtime.py skills/daemon/augur/tests/test_daemon.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit the docs and CI hardening**

```bash
git add .github/workflows/ci-cross-platform.yml skills/daemon/commands/ops-daemon.md skills/daemon/SKILL.md skills/daemon/references/launchd-usage.md skills/daemon/references/windows-task-usage.md
git commit -m "docs(daemon): add windows task scheduler operations"
```

## Self-Review Checklist

- Spec coverage:
  - shared daemon registration contract: Task 1
  - Windows Task Scheduler backend: Task 2
  - install/heal/status/uninstall lifecycle parity: Tasks 2 and 3
  - retire or absorb stale nightly Windows task path: Task 3
  - daemon command/doc surface parity: Task 4
  - Windows CI-safe verification: Task 4
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” placeholders remain
  - every code-changing step includes concrete code
  - every verification step includes the exact command and expected outcome
- Type consistency:
  - shared `DaemonRegistrationSpec` fields are used consistently across the backend and tests
  - observe status output uses `registrationType` / `registrationPath` consistently instead of mixing new fields with `plistPath`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-14-daemon-registration-windows-parity.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
