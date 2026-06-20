# Windows One-Click Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the online-first Windows setup path where a user starts from an `augur.run` prompt, prerequisites and Codex are bootstrapped, Augur installs from the repo, Codex MCP/plugin surfaces are configured, the daemon is registered, the dashboard is verified, and the user receives an honest readiness state.

**Architecture:** Use a staged flow: a public prompt launches a rerunnable PowerShell bootstrapper, the bootstrapper prepares the machine and hands off to Codex, and a repo-owned Python orchestrator performs Augur-specific setup and verification. Keep Windows-specific Codex launcher behavior in `src.cli_config.codex_runtime` so every Codex config writer shares the same native Windows MCP entry shape.

**Tech Stack:** PowerShell 5.1+, Python 3.11, pytest, Codex CLI, npm, winget, uv, pnpm, Windows Task Scheduler, Playwright, existing Augur `sync_agents`, `configure_mcp.py`, `service_healer.py`, and dashboard scripts.

**Spec:** `docs/superpowers/specs/2026-05-03-windows-one-click-onboarding-design.md`

---

## File Structure

Create or modify these files:

| Path | Action | Responsibility |
| --- | --- | --- |
| `scripts/windows-one-click-bootstrap.ps1` | Create | Public Windows bootstrapper downloaded or invoked from the augur.run prompt. Installs prerequisites, installs Codex CLI, clones/updates Augur, writes checkpoints, and launches the Codex handoff. |
| `scripts/augur-codex-mcp.ps1` | Create | Native Windows Codex MCP launcher. Mirrors `scripts/augur-codex-mcp` without requiring a Unix shell. |
| `src/cli_config/codex_runtime.py` | Modify | Select the correct Codex MCP launcher shape for the current or requested platform. |
| `skills/ai/scripts/sync_agents/adapters/codex.py` | Verify | Existing adapter should inherit the shared platform-aware Codex MCP helper; tests prove no duplicate Windows branch is added here. |
| `skills/ai/augur/adapters/codex_cli.py` | Verify | Existing direct adapter should inherit the shared platform-aware Codex MCP helper; tests prove no duplicate Windows branch is added here. |
| `skills/onboard/scripts/windows_one_click.py` | Create | Repo-owned setup orchestrator and verification engine for the Codex handoff. |
| `tests/scripts/test_windows_one_click_bootstrap.py` | Create | Static and dry-run tests for the PowerShell bootstrapper contract. |
| `skills/onboard/augur/tests/test_windows_one_click.py` | Create | Unit tests for state classification, command orchestration, and readiness report generation. |
| `tests/dashboard/visual/windows-onboarding-smoke.spec.ts` | Create | Browser-capable dashboard readiness smoke used by the orchestrator. |
| `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py` | Modify | Add Windows Codex MCP entry assertions. |
| `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py` | Modify | Add Windows launcher/config regression tests. |
| `skills/ai/augur/tests/test_codex_cli.py` | Modify | Add direct adapter Windows launcher assertions. |
| `skills/onboard/install.md` | Modify | Route Windows users to the new one-click bootstrap flow. |
| `docs/guides/installation-windows.md` | Modify | Document the one-click path as the preferred v1 path and keep manual install as fallback. |
| `.github/workflows/ci-cross-platform.yml` | Modify | Add Windows checks for the bootstrapper, orchestrator, and Codex launcher shape. |

External references used for the Codex install channel:

- OpenAI Codex CLI docs: `https://developers.openai.com/codex/cli`
- OpenAI Codex open-source README: `https://github.com/openai/codex/blob/main/codex-rs/README.md`

---

### Task 1: Add Native Windows Codex MCP Launcher Support

**Files:**
- Create: `scripts/augur-codex-mcp.ps1`
- Modify: `src/cli_config/codex_runtime.py`
- Modify: `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py`
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
- Modify: `skills/ai/augur/tests/test_codex_cli.py`

- [ ] **Step 1: Add failing tests for platform-aware Codex MCP entries**

Append this test to `tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py` inside `TestConfigureMcpRuntimeArgs`:

```python
    def test_codex_cli_config_uses_powershell_launcher_on_windows(self, project_root):
        """Codex on Windows must not depend on the Unix shell launcher."""
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        with patch("src.cli_config.codex_runtime.platform.system", return_value="Windows"):
            entries = _build_augur_server_entries_for_ide("codex_cli", Path("python.exe"), project_root)

        assert set(entries) == {"augur-core", "augur-framework"}
        for server_name, module in (("augur-core", "augur_core"), ("augur-framework", "augur_framework")):
            entry = entries[server_name]
            assert entry["command"] == "powershell.exe"
            assert entry["args"][:4] == [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
            ]
            assert entry["args"][4] == str(project_root / "scripts" / "augur-codex-mcp.ps1")
            assert entry["args"][5:] == ["-m", module, "--client-id", "codex"]
            assert "cwd" not in entry
            assert "env" not in entry
```

Append this test to `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py` near the existing Codex launcher tests:

```python
    def test_codex_mcp_entry_uses_windows_launcher_shape_when_requested(self):
        from src.cli_config.codex_runtime import build_codex_mcp_entry

        repo_root = Path(__file__).resolve().parents[5]
        entry = build_codex_mcp_entry(
            ["-m", "augur_core", "--client-id", "codex"],
            configured_root=repo_root,
            platform_name="Windows",
        )

        assert entry == {
            "command": "powershell.exe",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repo_root / "scripts" / "augur-codex-mcp.ps1"),
                "-m",
                "augur_core",
                "--client-id",
                "codex",
            ],
        }
```

Append this test to `skills/ai/augur/tests/test_codex_cli.py`:

```python
def test_codex_cli_builds_windows_mcp_entry_when_platform_is_windows():
    from skills.ai.augur.adapters import codex_cli

    with patch("src.cli_config.codex_runtime.platform.system", return_value="Windows"):
        entry = codex_cli._build_codex_mcp_entry()

    assert entry["command"] == "powershell.exe"
    assert entry["args"][:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    assert entry["args"][4].endswith("\\scripts\\augur-codex-mcp.ps1") or entry["args"][4].endswith(
        "/scripts/augur-codex-mcp.ps1"
    )
    assert entry["args"][5:] == ["-m", "augur_core", "--client-id", "codex"]
    assert "env" not in entry
    assert "cwd" not in entry
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_powershell_launcher_on_windows \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCodexAdapter::test_codex_mcp_entry_uses_windows_launcher_shape_when_requested \
  skills/ai/augur/tests/test_codex_cli.py::test_codex_cli_builds_windows_mcp_entry_when_platform_is_windows \
  -q
```

Expected: failures because `build_codex_mcp_entry()` has no `platform_name` parameter and always points at `scripts/augur-codex-mcp`.

- [ ] **Step 3: Add the Windows PowerShell launcher**

Create `scripts/augur-codex-mcp.ps1`:

```powershell
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

function Resolve-AugurRoot {
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    $configuredRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
    $candidates = @(
        (Get-Location).Path,
        $env:AUGUR_ROOT,
        $env:AUGUR_REPO,
        $configuredRoot
    )

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        $projectFile = Join-Path $candidate "project.yaml"
        if (Test-Path $projectFile) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "[augur] Codex MCP could not locate an Augur checkout. checked cwd=$((Get-Location).Path) AUGUR_ROOT=$env:AUGUR_ROOT AUGUR_REPO=$env:AUGUR_REPO configured=$configuredRoot"
}

$root = Resolve-AugurRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$env:AUGUR_ROOT = $root
$env:PYTHONUNBUFFERED = "1"
$mcpPath = Join-Path $root "src\mcp"
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = "$root;$mcpPath"
} else {
    $env:PYTHONPATH = "$root;$mcpPath;$env:PYTHONPATH"
}

& $python @RemainingArgs
exit $LASTEXITCODE
```

- [ ] **Step 4: Make Codex runtime helper platform-aware**

Replace `src/cli_config/codex_runtime.py` with this shape, preserving the public function name:

```python
"""Codex MCP runtime config helpers."""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

CODEX_MCP_LAUNCHER = "scripts/augur-codex-mcp"
CODEX_MCP_WINDOWS_LAUNCHER = "scripts/augur-codex-mcp.ps1"


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_windows(platform_name: str | None = None) -> bool:
    return (platform_name or platform.system()).lower().startswith("win")


def build_codex_mcp_entry(
    server_args: list[str],
    configured_root: str | Path | None = None,
    platform_name: str | None = None,
) -> dict[str, Any]:
    """Return a compact Codex MCP entry with a cwd-independent launcher path."""
    root = Path(configured_root).expanduser().resolve() if configured_root else _default_project_root()
    if _is_windows(platform_name):
        return {
            "command": "powershell.exe",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(root / CODEX_MCP_WINDOWS_LAUNCHER),
                *server_args,
            ],
        }
    return {
        "command": str(root / CODEX_MCP_LAUNCHER),
        "args": list(server_args),
    }
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_powershell_launcher_on_windows \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_dynamic_worktree_runtime \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCodexAdapter::test_codex_mcp_entry_uses_windows_launcher_shape_when_requested \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCodexAdapter::test_codex_mcp_entry_is_dynamic_and_not_repo_pinned \
  skills/ai/augur/tests/test_codex_cli.py::test_codex_cli_builds_windows_mcp_entry_when_platform_is_windows \
  skills/ai/augur/tests/test_codex_cli.py::test_codex_cli_builds_dynamic_mcp_entry \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the Codex launcher checkpoint**

```bash
git add scripts/augur-codex-mcp.ps1 src/cli_config/codex_runtime.py \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py \
  skills/ai/augur/tests/test_codex_cli.py
git commit -m "fix(codex): add native windows mcp launcher"
```

---

### Task 2: Add Windows One-Click State And Readiness Model

**Files:**
- Create: `skills/onboard/scripts/windows_one_click.py`
- Create: `skills/onboard/augur/tests/test_windows_one_click.py`

- [ ] **Step 1: Write failing state and report tests**

Create `skills/onboard/augur/tests/test_windows_one_click.py`:

```python
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = PROJECT_ROOT / "skills" / "onboard" / "scripts" / "windows_one_click.py"

spec = importlib.util.spec_from_file_location("windows_one_click", SCRIPT_PATH)
windows_one_click = importlib.util.module_from_spec(spec)
sys.modules["windows_one_click"] = windows_one_click
spec.loader.exec_module(windows_one_click)


def test_state_path_prefers_localappdata(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    result = windows_one_click.bootstrap_state_path()

    assert str(result).endswith(r"Augur\setup\bootstrap-state.json")
    assert "AppData" in str(result)


def test_ready_report_requires_all_core_checks():
    checks = {
        "prerequisites_installed": True,
        "codex_installed": True,
        "codex_authenticated": True,
        "repo_ready": True,
        "dependencies_ready": True,
        "mcp_configured": True,
        "daemon_registered": True,
        "dashboard_verified": True,
        "onboard_status_clean": True,
    }

    report = windows_one_click.classify_readiness(checks)

    assert report["state"] == "Ready"
    assert report["summary"] == "Augur is installed, Codex is connected, daemon is running, dashboard verified."


def test_missing_codex_auth_reports_needs_sign_in():
    checks = {
        "prerequisites_installed": True,
        "codex_installed": True,
        "codex_authenticated": False,
        "repo_ready": True,
        "dependencies_ready": False,
        "mcp_configured": False,
        "daemon_registered": False,
        "dashboard_verified": False,
        "onboard_status_clean": False,
    }

    report = windows_one_click.classify_readiness(checks)

    assert report["state"] == "Needs sign-in"
    assert "codex login" in report["next_action"]


def test_state_round_trip_writes_json(tmp_path):
    state_path = tmp_path / "bootstrap-state.json"
    payload = {"codex_installed": True, "repo_ready": False}

    windows_one_click.write_bootstrap_state(payload, state_path=state_path)

    assert json.loads(state_path.read_text(encoding="utf-8")) == payload
    assert windows_one_click.read_bootstrap_state(state_path=state_path) == payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py -q
```

Expected: failure because `skills/onboard/scripts/windows_one_click.py` does not exist.

- [ ] **Step 3: Implement the state and readiness model**

Create `skills/onboard/scripts/windows_one_click.py` with this initial content:

```python
#!/usr/bin/env python3
"""Windows one-click onboarding orchestrator for Augur."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

CORE_CHECKS = (
    "prerequisites_installed",
    "codex_installed",
    "codex_authenticated",
    "repo_ready",
    "dependencies_ready",
    "mcp_configured",
    "daemon_registered",
    "dashboard_verified",
    "onboard_status_clean",
)


def bootstrap_state_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "Augur" / "setup" / "bootstrap-state.json"
    return Path.home() / "AppData" / "Local" / "Augur" / "setup" / "bootstrap-state.json"


def read_bootstrap_state(state_path: Path | None = None) -> dict[str, Any]:
    path = state_path or bootstrap_state_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_bootstrap_state(payload: dict[str, Any], state_path: Path | None = None) -> None:
    path = state_path or bootstrap_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_readiness(checks: dict[str, bool]) -> dict[str, str]:
    complete = {key: bool(checks.get(key)) for key in CORE_CHECKS}
    if complete["codex_installed"] and not complete["codex_authenticated"]:
        return {
            "state": "Needs sign-in",
            "summary": "Codex is installed but not authenticated.",
            "next_action": "Run codex login, complete OpenAI sign-in, then rerun the Windows one-click setup.",
        }
    if all(complete.values()):
        return {
            "state": "Ready",
            "summary": "Augur is installed, Codex is connected, daemon is running, dashboard verified.",
            "next_action": "Open a fresh Codex session in the Augur repo and run /commands.",
        }
    missing = [key for key, value in complete.items() if not value]
    return {
        "state": "Blocked",
        "summary": f"Augur setup is incomplete: {', '.join(missing)}.",
        "next_action": "Open the setup log and fix the first failed check before rerunning setup.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or inspect Windows one-click Augur setup.")
    parser.add_argument("--status", action="store_true", help="Print readiness from the current bootstrap state")
    args = parser.parse_args()

    if args.status:
        state = read_bootstrap_state()
        print(json.dumps(classify_readiness({key: bool(state.get(key)) for key in CORE_CHECKS}), indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the readiness model checkpoint**

```bash
git add skills/onboard/scripts/windows_one_click.py skills/onboard/augur/tests/test_windows_one_click.py
git commit -m "feat(onboard): add windows setup readiness model"
```

---

### Task 3: Implement Repo-Owned Setup Orchestration

**Files:**
- Modify: `skills/onboard/scripts/windows_one_click.py`
- Modify: `skills/onboard/augur/tests/test_windows_one_click.py`

- [ ] **Step 1: Add failing orchestration tests**

Append these tests to `skills/onboard/augur/tests/test_windows_one_click.py`:

```python
from subprocess import CompletedProcess
from unittest.mock import patch


def test_run_dependencies_uses_uv_and_dashboard_pnpm(tmp_path):
    calls = []

    def fake_run(command, cwd, timeout):
        calls.append((command, Path(cwd), timeout))
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with patch.object(windows_one_click, "run_checked", side_effect=fake_run):
        result = windows_one_click.run_dependencies(tmp_path)

    assert result is True
    assert calls[0][0] == ["uv", "sync", "--group", "dev", "--extra", "windows"]
    assert calls[0][1] == tmp_path
    assert calls[1][0] == ["corepack", "enable"]
    assert calls[1][1] == tmp_path / "apps" / "dashboard"
    assert calls[2][0] == ["pnpm", "install"]
    assert calls[2][1] == tmp_path / "apps" / "dashboard"


def test_verify_codex_rejects_runtime_config_issues(tmp_path):
    with patch.object(windows_one_click, "codex_runtime_config_issues", return_value=["missing MCP server augur-core"]):
        result = windows_one_click.verify_codex(tmp_path)

    assert result["ok"] is False
    assert "missing MCP server augur-core" in result["detail"]


def test_verify_daemon_accepts_running_or_installed_daemon(tmp_path):
    with patch.object(windows_one_click, "collect_windows_daemon_status", return_value={"daemon": "running"}):
        result = windows_one_click.verify_daemon(tmp_path)

    assert result == {"ok": True, "detail": "daemon=running"}


def test_run_setup_stops_at_codex_sign_in(tmp_path):
    with patch.object(windows_one_click, "is_codex_installed", return_value=True), patch.object(
        windows_one_click, "is_codex_authenticated", return_value=False
    ):
        report = windows_one_click.run_setup(tmp_path)

    assert report["state"] == "Needs sign-in"
    assert report["checks"]["codex_installed"] is True
    assert report["checks"]["codex_authenticated"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py -q
```

Expected: failures for missing orchestration functions.

- [ ] **Step 3: Add command execution and setup functions**

Extend `skills/onboard/scripts/windows_one_click.py` with these imports and functions:

```python
import shutil
import subprocess
import sys


def run_checked(command: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=True,
    )


def run_dependencies(repo_root: Path) -> bool:
    run_checked(["uv", "sync", "--group", "dev", "--extra", "windows"], cwd=repo_root, timeout=1800)
    dashboard_dir = repo_root / "apps" / "dashboard"
    run_checked(["corepack", "enable"], cwd=dashboard_dir, timeout=300)
    run_checked(["pnpm", "install"], cwd=dashboard_dir, timeout=1200)
    return True


def sync_codex(repo_root: Path) -> bool:
    run_checked([sys.executable, "-m", "skills.ai.scripts.sync_agents", "sync", "all", "codex"], cwd=repo_root, timeout=600)
    return True


def codex_runtime_config_issues(repo_root: Path) -> list[str]:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from skills.ai.scripts.sync_agents.adapters.codex import codex_runtime_config_issues as _issues

    return _issues()


def verify_codex(repo_root: Path) -> dict[str, Any]:
    issues = codex_runtime_config_issues(repo_root)
    if issues:
        return {"ok": False, "detail": "; ".join(issues)}
    return {"ok": True, "detail": "codex runtime config is current"}


def install_or_heal_daemon(repo_root: Path) -> bool:
    run_checked([sys.executable, "skills/daemon/scripts/service_healer.py", "install"], cwd=repo_root, timeout=300)
    run_checked([sys.executable, "skills/daemon/scripts/service_healer.py", "heal"], cwd=repo_root, timeout=300)
    return True


def collect_windows_daemon_status(repo_root: Path) -> dict[str, str]:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    daemon_scripts = repo_root / "skills" / "daemon" / "scripts"
    if str(daemon_scripts) not in sys.path:
        sys.path.insert(0, str(daemon_scripts))
    import service_healer

    return service_healer._collect_windows_status_results(repo_root)


def verify_daemon(repo_root: Path) -> dict[str, Any]:
    status = collect_windows_daemon_status(repo_root)
    daemon = status.get("daemon", "")
    if daemon in {"running", "installed"}:
        return {"ok": True, "detail": f"daemon={daemon}"}
    return {"ok": False, "detail": f"daemon={daemon or 'missing'}"}


def is_codex_installed() -> bool:
    return shutil.which("codex") is not None


def is_codex_authenticated() -> bool:
    try:
        result = subprocess.run(
            ["codex", "exec", "Respond exactly with AUGUR_AUTH_OK."],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def verify_onboard_status(checks: dict[str, bool]) -> dict[str, Any]:
    candidate = dict(checks)
    candidate["onboard_status_clean"] = True
    report = classify_readiness(candidate)
    if report["state"] == "Ready":
        return {"ok": True, "detail": "onboard status ready"}
    return {"ok": False, "detail": report["summary"]}


def run_setup(repo_root: Path) -> dict[str, Any]:
    checks = {key: False for key in CORE_CHECKS}
    checks["prerequisites_installed"] = True
    checks["codex_installed"] = is_codex_installed()
    checks["repo_ready"] = (repo_root / "project.yaml").exists()
    checks["codex_authenticated"] = is_codex_authenticated()
    if not checks["codex_authenticated"]:
        report = classify_readiness(checks)
        report["checks"] = checks
        return report

    checks["dependencies_ready"] = run_dependencies(repo_root)
    sync_codex(repo_root)
    checks["mcp_configured"] = verify_codex(repo_root)["ok"]
    install_or_heal_daemon(repo_root)
    checks["daemon_registered"] = verify_daemon(repo_root)["ok"]
    checks["dashboard_verified"] = False
    checks["onboard_status_clean"] = verify_onboard_status(checks)["ok"]

    write_bootstrap_state(checks)
    report = classify_readiness(checks)
    report["checks"] = checks
    return report
```

This checkpoint deliberately leaves `dashboard_verified` false until Task 4 adds browser verification. The setup report must therefore be `Blocked` after authenticated setup on this checkpoint, which is honest behavior for a partially implemented plan task.

- [ ] **Step 4: Update the CLI entrypoint**

Replace the body of `main()` in `skills/onboard/scripts/windows_one_click.py` with:

```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Run or inspect Windows one-click Augur setup.")
    parser.add_argument("--status", action="store_true", help="Print readiness from the current bootstrap state")
    parser.add_argument("--run", action="store_true", help="Run the repo-owned Windows setup orchestrator")
    parser.add_argument("--repo-root", default=".", help="Augur repo root")
    args = parser.parse_args()

    if args.status:
        state = read_bootstrap_state()
        print(json.dumps(classify_readiness({key: bool(state.get(key)) for key in CORE_CHECKS}), indent=2))
        return 0

    if args.run:
        report = run_setup(Path(args.repo_root).resolve())
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["state"] == "Ready" else 1

    parser.print_help()
    return 2
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py -q
```

Expected: all Task 3 tests pass. Do not add dashboard verification assertions until Task 4 because this checkpoint intentionally records `dashboard_verified = False`.

- [ ] **Step 6: Commit the setup orchestration checkpoint**

```bash
git add skills/onboard/scripts/windows_one_click.py skills/onboard/augur/tests/test_windows_one_click.py
git commit -m "feat(onboard): orchestrate windows one-click setup"
```

---

### Task 4: Add Dashboard Browser Smoke Verification

**Files:**
- Create: `tests/dashboard/visual/windows-onboarding-smoke.spec.ts`
- Modify: `skills/onboard/scripts/windows_one_click.py`
- Modify: `skills/onboard/augur/tests/test_windows_one_click.py`

- [ ] **Step 1: Add the Playwright smoke**

Create `tests/dashboard/visual/windows-onboarding-smoke.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";

test("dashboard reaches interactive state for Windows onboarding", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("augur-welcome-dismissed", "true");
  });

  await page.goto("/", { waitUntil: "networkidle" });

  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByText(/Failed to load chunk/i)).toHaveCount(0);
  await expect(page.getByText(/Application error/i)).toHaveCount(0);
  await expect(page.locator("button, a, [role='button']").first()).toBeVisible({ timeout: 15000 });
});
```

- [ ] **Step 2: Add failing Python tests for dashboard command construction**

Append this test to `skills/onboard/augur/tests/test_windows_one_click.py`:

```python
def test_verify_dashboard_runs_playwright_smoke(tmp_path):
    calls = []
    dashboard_dir = tmp_path / "apps" / "dashboard"
    dashboard_dir.mkdir(parents=True)

    def fake_run(command, cwd, timeout):
        calls.append((command, Path(cwd), timeout))
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with patch.object(windows_one_click, "run_checked", side_effect=fake_run):
        result = windows_one_click.verify_dashboard(tmp_path)

    assert result == {"ok": True, "detail": "dashboard browser smoke passed"}
    assert calls == [
        (
            [
                "pnpm",
                "exec",
                "playwright",
                "test",
                "windows-onboarding-smoke.spec.ts",
                "--project=chromium",
                "--reporter=line",
            ],
            dashboard_dir,
            180,
        )
    ]
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py::test_verify_dashboard_runs_playwright_smoke -q
```

Expected: failure because `verify_dashboard()` does not exist yet.

- [ ] **Step 4: Implement dashboard verification**

Add `verify_dashboard()` to `skills/onboard/scripts/windows_one_click.py`:

```python
def verify_dashboard(repo_root: Path) -> dict[str, Any]:
    dashboard_dir = repo_root / "apps" / "dashboard"
    try:
        run_checked(
            [
                "pnpm",
                "exec",
                "playwright",
                "test",
                "windows-onboarding-smoke.spec.ts",
                "--project=chromium",
                "--reporter=line",
            ],
            cwd=dashboard_dir,
            timeout=180,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return {"ok": False, "detail": detail}
    return {"ok": True, "detail": "dashboard browser smoke passed"}
```

Then replace these lines in `run_setup()`:

```python
    checks["dashboard_verified"] = False
    checks["onboard_status_clean"] = verify_onboard_status(checks)["ok"]
```

with:

```python
    checks["dashboard_verified"] = verify_dashboard(repo_root)["ok"]
    checks["onboard_status_clean"] = verify_onboard_status(checks)["ok"]
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest skills/onboard/augur/tests/test_windows_one_click.py::test_verify_dashboard_runs_playwright_smoke -q
```

Expected: test passes.

- [ ] **Step 6: Run dashboard smoke locally if dependencies are installed**

Run:

```bash
cd apps/dashboard
pnpm exec playwright test windows-onboarding-smoke.spec.ts --project=chromium --reporter=line
```

Expected: passes against a locally started dashboard through the Playwright `webServer` config. If Playwright browsers are not installed, run:

```bash
cd apps/dashboard
pnpm exec playwright install chromium
pnpm exec playwright test windows-onboarding-smoke.spec.ts --project=chromium --reporter=line
```

- [ ] **Step 7: Commit dashboard verification**

```bash
git add tests/dashboard/visual/windows-onboarding-smoke.spec.ts \
  skills/onboard/scripts/windows_one_click.py \
  skills/onboard/augur/tests/test_windows_one_click.py
git commit -m "test(onboard): add dashboard browser smoke for windows setup"
```

---

### Task 5: Add The Rerunnable PowerShell Bootstrapper

**Files:**
- Create: `scripts/windows-one-click-bootstrap.ps1`
- Create: `tests/scripts/test_windows_one_click_bootstrap.py`

- [ ] **Step 1: Add failing static contract tests**

Create `tests/scripts/test_windows_one_click_bootstrap.py`:

```python
from pathlib import Path


SCRIPT = Path("scripts/windows-one-click-bootstrap.ps1")


def test_bootstrap_script_exists_and_has_dry_run_mode():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "param(" in text
    assert "[switch]$DryRun" in text
    assert "[switch]$NoLaunch" in text
    assert "bootstrap-state.json" in text


def test_bootstrap_uses_winget_for_supported_prerequisites():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "Git.Git" in text
    assert "Python.Python.3.11" in text
    assert "OpenJS.NodeJS.LTS" in text
    assert "winget install --id" in text


def test_bootstrap_installs_codex_via_current_npm_channel():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "npm i -g @openai/codex@latest" in text
    assert "codex login" in text


def test_bootstrap_hands_off_to_repo_owned_orchestrator():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "skills\\onboard\\scripts\\windows_one_click.py" in text
    assert "--run" in text
    assert "codex exec" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/scripts/test_windows_one_click_bootstrap.py -q
```

Expected: failure because `scripts/windows-one-click-bootstrap.ps1` does not exist.

- [ ] **Step 3: Create the bootstrapper**

Create `scripts/windows-one-click-bootstrap.ps1`:

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS
    Online-first Windows one-click bootstrap for Augur.
#>

[CmdletBinding()]
param(
    [string]$InstallDir = $(if ($env:AUGUR_DIR) { $env:AUGUR_DIR } else { Join-Path $env:USERPROFILE "Projects\Augur" }),
    [string]$Branch = $(if ($env:AUGUR_BRANCH) { $env:AUGUR_BRANCH } else { "main" }),
    [switch]$DryRun,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/augur-os/augur-os.git"
$StateDir = Join-Path $env:LOCALAPPDATA "Augur\setup"
$StatePath = Join-Path $StateDir "bootstrap-state.json"
$LogPath = Join-Path $StateDir "bootstrap.log"

function Write-Log {
    param([string]$Message)
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -Path $LogPath -Value $line
    Write-Host $Message
}

function Write-State {
    param([hashtable]$Patch)
    if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
    $state = @{}
    if (Test-Path $StatePath) {
        $parsed = Get-Content $StatePath -Raw | ConvertFrom-Json
        if ($null -ne $parsed) {
            $parsed.PSObject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }
        }
    }
    foreach ($key in $Patch.Keys) { $state[$key] = $Patch[$key] }
    $state | ConvertTo-Json -Depth 8 | Set-Content -Path $StatePath -Encoding UTF8
}

function Test-CommandAvailable {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Invoke-Step {
    param([string[]]$Command)
    Write-Log ("> " + ($Command -join " "))
    if ($DryRun) { return }
    & $Command[0] @($Command | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE: $($Command -join ' ')" }
}

function Install-WingetPackage {
    param([string]$PackageId, [string]$Command)
    if (Test-CommandAvailable $Command) {
        Write-Log "$Command already installed"
        return
    }
    if (-not (Test-CommandAvailable "winget")) {
        Write-State @{ setup_state = "Blocked"; blocked_reason = "winget is not available" }
        throw "winget is required for automatic prerequisite installation"
    }
    Invoke-Step @("winget", "install", "--id", $PackageId, "--exact", "--accept-package-agreements", "--accept-source-agreements")
}

function Refresh-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Ensure-Prerequisites {
    Install-WingetPackage -PackageId "Git.Git" -Command "git"
    Install-WingetPackage -PackageId "Python.Python.3.11" -Command "python"
    Install-WingetPackage -PackageId "OpenJS.NodeJS.LTS" -Command "node"
    Refresh-PathFromRegistry
    if (-not (Test-CommandAvailable "npm")) {
        Write-State @{ setup_state = "Needs reopen"; prerequisites_installed = $false }
        throw "npm is not visible yet. Reopen PowerShell and rerun this bootstrapper."
    }
    if (-not (Test-CommandAvailable "uv")) {
        Invoke-Step @("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://astral.sh/uv/install.ps1 | iex")
        Refresh-PathFromRegistry
    }
    Write-State @{ prerequisites_installed = $true }
}

function Ensure-Codex {
    if (-not (Test-CommandAvailable "codex")) {
        Invoke-Step @("npm", "i", "-g", "@openai/codex@latest")
        Refresh-PathFromRegistry
    }
    if (-not (Test-CommandAvailable "codex")) {
        Write-State @{ setup_state = "Needs reopen"; codex_installed = $false }
        throw "codex is installed but not visible in this shell. Reopen PowerShell and rerun this bootstrapper."
    }
    Write-State @{ codex_installed = $true }
    Write-Log "If Codex asks you to sign in, run: codex login"
}

function Ensure-Repo {
    if (Test-Path (Join-Path $InstallDir ".git")) {
        Invoke-Step @("git", "-C", $InstallDir, "fetch", "origin", $Branch)
        Invoke-Step @("git", "-C", $InstallDir, "checkout", $Branch)
        Invoke-Step @("git", "-C", $InstallDir, "pull", "--ff-only", "origin", $Branch)
    } else {
        $parent = Split-Path $InstallDir -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Invoke-Step @("git", "clone", "--branch", $Branch, $RepoUrl, $InstallDir)
    }
    Write-State @{ repo_ready = $true }
}

function Invoke-CodexHandoff {
    $orchestrator = Join-Path $InstallDir "skills\onboard\scripts\windows_one_click.py"
    $prompt = "Run Augur Windows one-click setup from this repo. Execute: python `"$orchestrator`" --run --repo-root `"$InstallDir`". Continue until it reports Ready or a specific blocked state."
    Write-Log "Codex handoff prompt: $prompt"
    if ($NoLaunch -or $DryRun) { return }
    Push-Location $InstallDir
    try {
        codex exec $prompt
    } finally {
        Pop-Location
    }
}

try {
    Write-Log "Starting Augur Windows one-click bootstrap"
    Ensure-Prerequisites
    Ensure-Codex
    Ensure-Repo
    Invoke-CodexHandoff
    Write-Log "Bootstrap handoff complete. State: $StatePath"
} catch {
    Write-Log "Bootstrap failed: $_"
    throw
}
```

- [ ] **Step 4: Run static contract tests**

Run:

```bash
uv run pytest tests/scripts/test_windows_one_click_bootstrap.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run PowerShell parser check on a Windows-capable shell**

Run on Windows or in CI:

```powershell
powershell -NoProfile -Command "$null = [scriptblock]::Create((Get-Content scripts/windows-one-click-bootstrap.ps1 -Raw)); 'parser ok'"
```

Expected:

```text
parser ok
```

- [ ] **Step 6: Commit the bootstrapper checkpoint**

```bash
git add scripts/windows-one-click-bootstrap.ps1 tests/scripts/test_windows_one_click_bootstrap.py
git commit -m "feat(onboard): add windows one-click bootstrapper"
```

---

### Task 6: Publish The Windows Prompt And Docs Surface

**Files:**
- Modify: `skills/onboard/install.md`
- Modify: `docs/guides/installation-windows.md`
- Modify: `tests/scripts/test_build_public_release_tree.py`
- Create: `tests/scripts/test_onboard_install_prompt.py`

- [ ] **Step 1: Add docs tests and release allowlist regression coverage**

Append to `tests/scripts/test_build_public_release_tree.py`:

```python
def test_windows_install_guide_is_in_public_release_allowlist():
    assert "docs/guides/installation-windows.md" in DOCS_ONLY_ALLOWLIST


def test_windows_install_guide_mentions_one_click_bootstrap():
    text = (PROJECT_ROOT / "docs" / "guides" / "installation-windows.md").read_text(encoding="utf-8")

    assert "One-click setup from augur.run" in text
    assert "windows-one-click-bootstrap.ps1" in text
    assert "Codex sign-in" in text
```

Create a new test file `tests/scripts/test_onboard_install_prompt.py`:

```python
from pathlib import Path


def test_onboard_install_prompt_routes_windows_to_one_click_bootstrap():
    text = Path("skills/onboard/install.md").read_text(encoding="utf-8")

    assert "Windows one-click setup" in text
    assert "scripts/windows-one-click-bootstrap.ps1" in text
    assert "powershell" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/scripts/test_build_public_release_tree.py::test_windows_install_guide_mentions_one_click_bootstrap tests/scripts/test_onboard_install_prompt.py -q
```

Expected: failures for the guide and prompt content because the docs do not mention the new bootstrapper yet. The allowlist assertion should already pass if `docs/guides/installation-windows.md` remains in `DOCS_ONLY_ALLOWLIST`.

- [ ] **Step 3: Update `skills/onboard/install.md`**

Add this section near the top, after platform detection:

````markdown
## Windows one-click setup

If the detected machine is Windows, use the staged Windows bootstrap instead of the Unix `curl | bash` installer.

Run this from PowerShell:

```powershell
$script = "$env:TEMP\windows-one-click-bootstrap.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/windows-one-click-bootstrap.ps1" -OutFile $script
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

The bootstrapper installs supported prerequisites with `winget`, installs Codex CLI through the current official npm channel, clones or updates Augur, and hands off to Codex for repo-owned verification.

If Codex asks for authentication, complete Codex sign-in and rerun the same PowerShell command.
````

Then adjust Step 2a so the Unix install command is explicitly for macOS/Linux or non-Windows agent contexts.

- [ ] **Step 4: Update `docs/guides/installation-windows.md`**

Add this section before the existing `Quick Install` section:

```markdown
### One-click setup from augur.run

Preferred v1 path:

1. Open `https://augur.run` on the Windows machine.
2. Copy the Windows onboarding prompt.
3. Paste it into ChatGPT or Codex.
4. If the active ChatGPT surface cannot run local commands, run the PowerShell command it prints.

The command downloads `scripts/windows-one-click-bootstrap.ps1`, installs missing prerequisites with `winget` where supported, installs Codex CLI through the current official npm channel, clones or updates Augur, and hands off to Codex for verification.

Codex sign-in may require a browser interaction. If setup reports `Needs sign-in`, run `codex login`, complete OpenAI authentication, then rerun the bootstrap command.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
uv run pytest tests/scripts/test_build_public_release_tree.py::test_windows_install_guide_mentions_one_click_bootstrap tests/scripts/test_onboard_install_prompt.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit docs checkpoint**

```bash
git add skills/onboard/install.md docs/guides/installation-windows.md \
  tests/scripts/test_build_public_release_tree.py tests/scripts/test_onboard_install_prompt.py
git commit -m "docs(onboard): publish windows one-click setup path"
```

---

### Task 7: Add Windows CI Coverage And Final Verification

**Files:**
- Modify: `.github/workflows/ci-cross-platform.yml`
- Run-only: existing tests from prior tasks

- [ ] **Step 1: Add Windows CI steps**

In `.github/workflows/ci-cross-platform.yml`, add these steps to the `path-handling-tests` job after `Smoke test configure_mcp (Windows)`:

```yaml
      - name: Verify Windows one-click bootstrap contract
        if: runner.os == 'Windows'
        run: |
          .\.venv\Scripts\Activate.ps1
          pytest tests/scripts/test_windows_one_click_bootstrap.py tests/scripts/test_onboard_install_prompt.py -q
          powershell -NoProfile -Command "$null = [scriptblock]::Create((Get-Content scripts/windows-one-click-bootstrap.ps1 -Raw)); 'parser ok'"

      - name: Verify Windows Codex launcher shape
        if: runner.os == 'Windows'
        run: |
          .\.venv\Scripts\Activate.ps1
          pytest tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_powershell_launcher_on_windows -q
```

Add this step to the `service-healer-tests` job after `Smoke test daemon registration spec (Windows)`:

```yaml
      - name: Verify Windows one-click orchestrator unit tests
        if: runner.os == 'Windows'
        run: |
          .\.venv\Scripts\Activate.ps1
          uv run pytest skills/onboard/augur/tests/test_windows_one_click.py -q
```

- [ ] **Step 2: Run local focused Python tests**

Run:

```bash
uv run pytest \
  tests/scripts/test_windows_one_click_bootstrap.py \
  tests/scripts/test_onboard_install_prompt.py \
  tests/scripts/test_build_public_release_tree.py::test_windows_install_guide_mentions_one_click_bootstrap \
  skills/onboard/augur/tests/test_windows_one_click.py \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_powershell_launcher_on_windows \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCodexAdapter::test_codex_mcp_entry_uses_windows_launcher_shape_when_requested \
  skills/ai/augur/tests/test_codex_cli.py::test_codex_cli_builds_windows_mcp_entry_when_platform_is_windows \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run existing adjacent regressions**

Run:

```bash
uv run pytest \
  tests/scripts/test_install_ps1.py \
  skills/daemon/augur/tests/test_service_healer_registration.py \
  skills/ai/scripts/sync_agents/tests/test_codex_runtime_config.py \
  tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py::TestConfigureMcpRuntimeArgs::test_codex_cli_config_uses_dynamic_worktree_runtime \
  skills/ai/augur/tests/test_codex_cli.py::test_codex_cli_ensure_config_writes_dynamic_worktree_entry \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run formatting and diff checks**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Commit CI checkpoint**

```bash
git add .github/workflows/ci-cross-platform.yml
git commit -m "ci(windows): verify one-click onboarding surfaces"
```

- [ ] **Step 6: Manual Windows validation**

Run on a fresh or reset Windows 11 machine:

```powershell
$script = "$env:TEMP\windows-one-click-bootstrap.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/windows-one-click-bootstrap.ps1" -OutFile $script
powershell -NoProfile -ExecutionPolicy Bypass -File $script
```

Expected first-run outcomes:

- If Codex sign-in is needed, setup reports `Needs sign-in` and points to `codex login`.
- After sign-in and rerun, setup reaches `Ready`.
- `%LOCALAPPDATA%\Augur\setup\bootstrap-state.json` contains all core check keys.
- Codex config contains split `augur-*` MCP entries and no legacy `augur_mcp`.
- Windows Task Scheduler contains the Augur daemon task.
- Dashboard smoke reaches interactive state.

Do not claim Windows one-click onboarding is complete until this manual Windows validation is performed.

---

## Plan Self-Review Notes

- Spec coverage: the tasks cover the public prompt, bootstrapper, Codex install/auth handoff, repo-owned setup, Codex MCP/plugin verification, daemon registration, dashboard smoke, readiness state, docs, and CI.
- Scope boundary: local LLM/Ollama, offline bundles, personal integrations, and signed installers stay out of v1.
- Critical implementation risk: Codex on Windows must use `scripts/augur-codex-mcp.ps1`; otherwise the bootstrap could finish while MCP startup still depends on a Unix shell launcher.
