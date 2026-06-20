"""auto-heal-validate: Validate daemon health and detect stuck/stale state.

Reads state/daemon/health.json and checks:
  - Whether the daemon is running
  - Whether the heartbeat is stale (>600s since last beat)
  - Whether stuck_entries are present

Fix behavior escalates with difficulty:
  - difficulty 0: report only
  - difficulty 1+: write restart signal, append clear-stuck marker to journal

See ADR-200 for the auto-command protocol.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import subprocess
import sys
import time
from pathlib import Path

from src.config.mcp_config_drift import scan_global_mcp_config_references
from src.config.paths import get_runtime_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-heal-validate"

STALE_THRESHOLD_S = 600  # 10 minutes
COMMAND_TIMEOUT_S = 120


# ---------------------------------------------------------------------------
# Helpers (patchable in tests)
# ---------------------------------------------------------------------------

def _daemon_health(project_root: Path) -> dict:
    """Read and return daemon health from the canonical runtime state root."""
    del project_root
    health_path = get_runtime_dir() / "daemon" / "health.json"
    if not health_path.exists():
        return {}
    return json.loads(health_path.read_text())


def _python(project_root: Path) -> str:
    """Return the project Python executable for health repair subprocesses."""
    if sys.platform == "win32":
        candidate = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = project_root / ".venv" / "bin" / "python3"
    if candidate.is_file():
        return str(candidate)
    return sys.executable or "python3"


def _run_command(
    command: list[str],
    project_root: Path,
    timeout: int = COMMAND_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    """Run a bounded subprocess from the active project root."""
    return subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _output_excerpt(result: subprocess.CompletedProcess[str], limit: int = 800) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    output = output.strip()
    if len(output) <= limit:
        return output
    return output[: limit - 3].rstrip() + "..."


def _configure_mcp_command(project_root: Path, mode: str) -> list[str]:
    script = project_root / "scripts" / "configure_mcp.py"
    return [
        _python(project_root),
        str(script),
        "--repo-root",
        str(project_root),
        mode,
        "--verbose",
    ]


def _service_healer_command(project_root: Path, action: str) -> list[str]:
    script = (
        project_root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "daemon"
        / "scripts"
        / "service_healer.py"
    )
    return [_python(project_root), str(script), action]


def _project_python_path(project_root: Path) -> Path:
    if sys.platform == "win32":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python3"


def _dashboard_esbuild_path(project_root: Path) -> Path:
    return project_root / "apps" / "dashboard" / "node_modules" / "esbuild"


def _check_runtime_prerequisites(project_root: Path) -> list[dict]:
    issues: list[dict] = []

    if (project_root / "pyproject.toml").is_file():
        python_path = _project_python_path(project_root)
        if not python_path.is_file():
            issues.append(
                {
                    "type": "mcp_runtime_python_missing",
                    "detail": f"Project MCP Python runtime is missing at {python_path}",
                    "path": str(python_path),
                }
            )

    dashboard_root = project_root / "apps" / "dashboard"
    if (dashboard_root / "package.json").is_file():
        esbuild_path = _dashboard_esbuild_path(project_root)
        if not esbuild_path.exists():
            issues.append(
                {
                    "type": "dashboard_dependency_missing",
                    "detail": f"Dashboard dependency sentinel is missing at {esbuild_path}",
                    "path": str(esbuild_path),
                }
            )

    return issues


def _check_mcp_config(project_root: Path) -> dict | None:
    command = _configure_mcp_command(project_root, "--check")
    if not Path(command[1]).is_file():
        return {
            "type": "mcp_config_drift",
            "detail": f"configure_mcp.py missing at {command[1]}",
            "returncode": 127,
        }
    try:
        result = _run_command(command, project_root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "type": "mcp_config_drift",
            "detail": f"configure_mcp check failed to run: {exc}",
            "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
        }
    if result.returncode == 0:
        return None
    return {
        "type": "mcp_config_drift",
        "detail": _output_excerpt(result) or "configure_mcp reported pending changes",
        "returncode": result.returncode,
    }


def _check_daemon_install(project_root: Path) -> dict | None:
    command = _service_healer_command(project_root, "status")
    if not Path(command[1]).is_file():
        return {
            "type": "daemon_install_drift",
            "detail": f"service_healer.py missing at {command[1]}",
            "returncode": 127,
        }
    try:
        result = _run_command(command, project_root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "type": "daemon_install_drift",
            "detail": f"service_healer status failed to run: {exc}",
            "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
        }
    if result.returncode == 0:
        return None
    return {
        "type": "daemon_install_drift",
        "detail": _output_excerpt(result) or "daemon service status reported drift",
        "returncode": result.returncode,
    }


def _check_mcp_config_path_references(project_root: Path) -> list[dict]:
    issues: list[dict] = []
    for path_issue in scan_global_mcp_config_references(project_root=project_root):
        issue = path_issue.as_dict()
        referenced_path = issue.get("referencedPath", "")
        if issue.get("kind") == "missing_path" and referenced_path:
            try:
                if Path(referenced_path).resolve(strict=False) == _project_python_path(project_root).resolve(strict=False):
                    continue
            except OSError:
                pass
        issues.append(
            {
                "type": "mcp_config_path_drift",
                "detail": issue.get("detail", "global MCP config references an unsafe path"),
                "kind": issue.get("kind", "unknown"),
                "client_label": issue.get("clientLabel", "unknown client"),
                "config_path": issue.get("configPath", ""),
                "referenced_path": issue.get("referencedPath", ""),
                "path_issue": issue,
            }
        )
    return issues


def _summarize_issue_types(issues: list[dict]) -> str:
    labels = {
        "mcp_config_drift": "MCP configuration drift",
        "mcp_config_path_drift": "MCP config path drift",
        "daemon_install_drift": "daemon service install drift",
        "dashboard_dependency_missing": "dashboard dependencies missing",
        "mcp_runtime_python_missing": "MCP runtime Python missing",
        "no_health_data": "missing daemon health data",
        "not_running": "daemon not running",
        "stale_heartbeat": "stale daemon heartbeat",
        "stuck_entries": "stuck daemon entries",
    }
    seen: list[str] = []
    for issue in issues:
        label = labels.get(str(issue.get("type")), str(issue.get("type", "unknown issue")))
        if label not in seen:
            seen.append(label)
    return ", ".join(seen)


# ---------------------------------------------------------------------------
# Protocol implementation
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Check daemon health for issues."""
    health = _daemon_health(ctx.project_root)
    issues: list[dict] = []

    if not health:
        issues.append({
            "type": "no_health_data",
            "detail": "health.json missing or empty",
        })
    elif not (
        not health.get("running", False)
        and not health.get("last_heartbeat", 0)
        and not health.get("stuck_entries", [])
    ):
        # Check running state
        if not health.get("running", False):
            issues.append({
                "type": "not_running",
                "detail": "Daemon reports not running",
            })

        # Check stale heartbeat
        last_heartbeat = health.get("last_heartbeat", 0)
        if last_heartbeat:
            age = time.time() - last_heartbeat
            if age > STALE_THRESHOLD_S:
                issues.append({
                    "type": "stale_heartbeat",
                    "age_seconds": round(age),
                    "threshold_seconds": STALE_THRESHOLD_S,
                    "detail": f"Heartbeat is {round(age)}s old (threshold: {STALE_THRESHOLD_S}s)",
                })

        # Check stuck entries
        stuck = health.get("stuck_entries", [])
        if stuck:
            issues.append({
                "type": "stuck_entries",
                "count": len(stuck),
                "entries": stuck,
                "detail": f"{len(stuck)} stuck journal entries",
            })

    mcp_issue = _check_mcp_config(ctx.project_root)
    if mcp_issue:
        issues.append(mcp_issue)

    issues.extend(_check_mcp_config_path_references(ctx.project_root))

    service_issue = _check_daemon_install(ctx.project_root)
    if service_issue:
        issues.append(service_issue)

    issues.extend(_check_runtime_prerequisites(ctx.project_root))

    error_types = {
        "dashboard_dependency_missing",
        "mcp_runtime_python_missing",
        "not_running",
        "mcp_config_drift",
        "mcp_config_path_drift",
        "daemon_install_drift",
    }
    severity = "error" if any(i["type"] in error_types for i in issues) else (
        "warning" if issues else "info"
    )
    if issues:
        summary = f"Found {len(issues)} self-heal validation issue(s): {_summarize_issue_types(issues)}"
        return ScanResult(
            issues=issues,
            summary=summary,
            severity=severity,
            health="degraded",
        )

    return ScanResult(
        issues=[],
        summary="Daemon health, MCP config, and service install are healthy",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix daemon health issues based on difficulty level."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            actions=[{"action": "dry_run", "description": "Would fix daemon health issues"}],
            summary="Dry run — no changes made",
        )

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            actions=[{"action": "report", "description": "Difficulty 0 — report only"}],
            summary="Report only at difficulty 0",
        )

    actions: list[dict] = []
    changes: list[str] = []
    success = True
    daemon_dir = get_runtime_dir() / "daemon"
    daemon_dir.mkdir(parents=True, exist_ok=True)

    if any(i["type"] in ("mcp_config_drift", "mcp_config_path_drift") for i in issues):
        command = _configure_mcp_command(ctx.project_root, "--apply")
        result = _run_command(command, ctx.project_root)
        action = {
            "action": "configure_mcp_apply",
            "returncode": result.returncode,
            "detail": _output_excerpt(result),
        }
        actions.append(action)
        if result.returncode == 0:
            changes.append("Reapplied generated MCP client configuration")
        else:
            success = False

    if any(i["type"] == "daemon_install_drift" for i in issues):
        command = _service_healer_command(ctx.project_root, "install")
        result = _run_command(command, ctx.project_root)
        action = {
            "action": "service_healer_install",
            "returncode": result.returncode,
            "detail": _output_excerpt(result),
        }
        actions.append(action)
        if result.returncode == 0:
            changes.append("Reinstalled or healed daemon service registration")
        else:
            success = False

    if any(i["type"] == "mcp_runtime_python_missing" for i in issues):
        command = ["uv", "sync"]
        result = _run_command(command, ctx.project_root)
        action = {
            "action": "uv_sync",
            "returncode": result.returncode,
            "detail": _output_excerpt(result),
        }
        actions.append(action)
        if result.returncode == 0:
            changes.append("Recreated project Python runtime with uv sync")
        else:
            success = False

    if any(i["type"] == "dashboard_dependency_missing" for i in issues):
        command = [
            "corepack",
            "pnpm",
            "--dir",
            "apps/dashboard",
            "install",
            "--frozen-lockfile",
        ]
        result = _run_command(command, ctx.project_root)
        action = {
            "action": "dashboard_pnpm_install",
            "returncode": result.returncode,
            "detail": _output_excerpt(result),
        }
        actions.append(action)
        if result.returncode == 0:
            changes.append("Reinstalled dashboard dependencies")
        else:
            success = False

    # Write restart signal for not_running or stale_heartbeat
    needs_restart = any(
        i["type"] in ("not_running", "stale_heartbeat") for i in issues
    )
    if needs_restart:
        restart_path = daemon_dir / "restart_requested"
        restart_path.write_text(f"requested_at={time.time()}\n")
        actions.append({"action": "restart_signal", "path": str(restart_path)})
        changes.append(f"Wrote restart signal to {restart_path}")

    # Clear stuck entries via journal marker
    has_stuck = any(i["type"] == "stuck_entries" for i in issues)
    if has_stuck:
        journal_path = daemon_dir / "journal.log"
        with journal_path.open("a") as f:
            f.write(f"[{time.time()}] CLEAR_STUCK: auto-heal-validate requested stuck entry clearance\n")
        actions.append({"action": "clear_stuck_marker", "path": str(journal_path)})
        changes.append("Appended clear-stuck marker to daemon journal")

    return FixResult(
        success=success,
        actions=actions,
        changes=changes,
        summary=f"Applied {len(changes)} daemon health fix(es)",
    )
