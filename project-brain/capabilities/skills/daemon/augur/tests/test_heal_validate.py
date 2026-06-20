"""Auto-generated importability test for heal_validate."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_heal_validate_importable():
    """Verify that heal_validate can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.ops.heal_validate")
    assert mod is not None


def _ctx(project_root: Path, *, difficulty: int = 0, dry_run: bool = False):
    from src.lib.ops_protocol import OpsContext

    return OpsContext(project_root=project_root, difficulty=difficulty, dry_run=dry_run)


def _create_health_probe_scripts(project_root: Path) -> None:
    (project_root / "scripts").mkdir(parents=True)
    (project_root / "scripts" / "configure_mcp.py").write_text("# test stub\n")
    service_script = (
        project_root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "daemon"
        / "scripts"
        / "service_healer.py"
    )
    service_script.parent.mkdir(parents=True)
    service_script.write_text("# test stub\n")


def _create_project_python(project_root: Path) -> None:
    python_path = project_root / ".venv" / "bin" / "python3"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/bin/sh\n")


def test_scan_reports_mcp_config_drift_from_configure_mcp_check(monkeypatch, tmp_path):
    """Self-heal validation must catch stale generated MCP client configs."""
    from subprocess import CompletedProcess

    from skills.daemon.scripts.ops import heal_validate

    _create_health_probe_scripts(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command, project_root, timeout=120):
        del project_root, timeout
        calls.append(command)
        if "configure_mcp.py" in command[1]:
            return CompletedProcess(
                command,
                1,
                stdout="MCP configuration needs update.\nClaude Desktop points at old-worktree",
                stderr="",
            )
        if "service_healer.py" in command[1]:
            return CompletedProcess(command, 0, stdout="[OK] daemon: running", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_run_command", fake_run, raising=False)

    result = heal_validate.scan(_ctx(tmp_path))

    assert any("configure_mcp.py" in call[1] and "--check" in call for call in calls)
    assert result.severity == "error"
    assert result.health == "degraded"
    assert any(issue["type"] == "mcp_config_drift" for issue in result.issues)
    assert "MCP configuration drift" in result.summary


def test_scan_reports_global_mcp_path_drift_from_reference_scanner(monkeypatch, tmp_path):
    """Self-heal validation must fail when global MCP config embeds a worktree path."""
    from skills.daemon.scripts.ops import heal_validate

    class FakePathIssue:
        kind = "linked_worktree"
        client_label = "Cursor"
        config_path = tmp_path / "cursor.mcp.json"
        referenced_path = tmp_path / ".worktrees" / "feature"

        def as_dict(self):
            return {
                "kind": self.kind,
                "clientLabel": self.client_label,
                "configPath": str(self.config_path),
                "referencedPath": str(self.referenced_path),
                "detail": "global MCP config references a linked worktree checkout",
            }

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_check_mcp_config", lambda _root: None)
    monkeypatch.setattr(heal_validate, "_check_daemon_install", lambda _root: None)
    monkeypatch.setattr(
        heal_validate,
        "scan_global_mcp_config_references",
        lambda project_root: [FakePathIssue()],
        raising=False,
    )

    result = heal_validate.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert result.health == "degraded"
    assert any(issue["type"] == "mcp_config_path_drift" for issue in result.issues)
    assert "MCP config path drift" in result.summary


def test_scan_reports_daemon_install_drift_from_service_healer_status(monkeypatch, tmp_path):
    """Self-heal validation must catch stale LaunchAgent/Scheduled Task layout."""
    from subprocess import CompletedProcess

    from skills.daemon.scripts.ops import heal_validate

    _create_health_probe_scripts(tmp_path)

    def fake_run(command, project_root, timeout=120):
        del project_root, timeout
        if "configure_mcp.py" in command[1]:
            return CompletedProcess(command, 0, stdout="MCP configuration is up to date.", stderr="")
        if "service_healer.py" in command[1]:
            return CompletedProcess(
                command,
                1,
                stdout="[!!] daemon: broken_install (program_arguments_mismatch)",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_run_command", fake_run, raising=False)

    result = heal_validate.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert result.health == "degraded"
    assert any(issue["type"] == "daemon_install_drift" for issue in result.issues)
    assert "daemon service install drift" in result.summary


def test_scan_reports_missing_project_python_runtime(monkeypatch, tmp_path):
    """Self-heal validation must catch a missing project venv used by MCP clients."""
    from skills.daemon.scripts.ops import heal_validate

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur-test'\n")

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_check_mcp_config", lambda _root: None)
    monkeypatch.setattr(heal_validate, "_check_mcp_config_path_references", lambda _root: [])
    monkeypatch.setattr(heal_validate, "_check_daemon_install", lambda _root: None)

    result = heal_validate.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert result.health == "degraded"
    assert any(issue["type"] == "mcp_runtime_python_missing" for issue in result.issues)
    assert "MCP runtime Python missing" in result.summary


def test_scan_does_not_rewrite_mcp_config_for_missing_project_python(monkeypatch, tmp_path):
    """A missing generated venv should be repaired with uv sync, not configure_mcp."""
    from skills.daemon.scripts.ops import heal_validate

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur-test'\n")

    class FakePathIssue:
        def as_dict(self):
            return {
                "kind": "missing_path",
                "clientLabel": "Claude Desktop",
                "configPath": str(tmp_path / "claude_desktop_config.json"),
                "referencedPath": str(tmp_path / ".venv" / "bin" / "python3"),
                "detail": "global MCP config references a missing local path",
            }

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_check_mcp_config", lambda _root: None)
    monkeypatch.setattr(heal_validate, "_check_daemon_install", lambda _root: None)
    monkeypatch.setattr(
        heal_validate,
        "scan_global_mcp_config_references",
        lambda project_root: [FakePathIssue()],
        raising=False,
    )

    result = heal_validate.scan(_ctx(tmp_path))

    assert any(issue["type"] == "mcp_runtime_python_missing" for issue in result.issues)
    assert not any(issue["type"] == "mcp_config_path_drift" for issue in result.issues)


def test_scan_reports_missing_dashboard_dependency_sentinel(monkeypatch, tmp_path):
    """Self-heal validation must catch missing dashboard dependencies before logs appear."""
    from skills.daemon.scripts.ops import heal_validate

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur-test'\n")
    _create_project_python(tmp_path)
    dashboard = tmp_path / "apps" / "dashboard"
    dashboard.mkdir(parents=True)
    (dashboard / "package.json").write_text('{"name":"dashboard"}\n')

    monkeypatch.setattr(
        heal_validate,
        "_daemon_health",
        lambda _root: {"running": True, "last_heartbeat": 0, "stuck_entries": []},
    )
    monkeypatch.setattr(heal_validate, "_check_mcp_config", lambda _root: None)
    monkeypatch.setattr(heal_validate, "_check_mcp_config_path_references", lambda _root: [])
    monkeypatch.setattr(heal_validate, "_check_daemon_install", lambda _root: None)

    result = heal_validate.scan(_ctx(tmp_path))

    assert result.severity == "error"
    assert result.health == "degraded"
    assert any(issue["type"] == "dashboard_dependency_missing" for issue in result.issues)
    assert "dashboard dependencies missing" in result.summary


def test_fix_repairs_mcp_config_and_daemon_install_drift(monkeypatch, tmp_path):
    """Difficulty 1+ fix should run canonical repair commands for drift issues."""
    from subprocess import CompletedProcess

    from skills.daemon.scripts.ops import heal_validate

    calls: list[list[str]] = []

    def fake_run(command, project_root, timeout=120):
        del project_root, timeout
        calls.append(command)
        return CompletedProcess(command, 0, stdout="repaired", stderr="")

    monkeypatch.setattr(heal_validate, "_run_command", fake_run, raising=False)
    monkeypatch.setattr(heal_validate, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = heal_validate.fix(
        _ctx(tmp_path, difficulty=1),
        [
            {"type": "mcp_config_drift", "detail": "stale generated MCP config"},
            {"type": "daemon_install_drift", "detail": "broken daemon install"},
        ],
    )

    assert result.success is True
    assert any("configure_mcp.py" in call[1] and "--apply" in call for call in calls)
    assert any("service_healer.py" in call[1] and "install" in call for call in calls)
    assert {action["action"] for action in result.actions} >= {
        "configure_mcp_apply",
        "service_healer_install",
    }


def test_fix_repairs_mcp_config_path_drift(monkeypatch, tmp_path):
    """Path drift findings should use the same generated MCP apply repair."""
    from subprocess import CompletedProcess

    from skills.daemon.scripts.ops import heal_validate

    calls: list[list[str]] = []

    def fake_run(command, project_root, timeout=120):
        del project_root, timeout
        calls.append(command)
        return CompletedProcess(command, 0, stdout="repaired", stderr="")

    monkeypatch.setattr(heal_validate, "_run_command", fake_run, raising=False)
    monkeypatch.setattr(heal_validate, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = heal_validate.fix(
        _ctx(tmp_path, difficulty=1),
        [{"type": "mcp_config_path_drift", "detail": "global MCP config references a worktree"}],
    )

    assert result.success is True
    assert any("configure_mcp.py" in call[1] and "--apply" in call for call in calls)
    assert {action["action"] for action in result.actions} == {"configure_mcp_apply"}


def test_fix_repairs_runtime_prerequisites(monkeypatch, tmp_path):
    """Difficulty 1+ fix should restore generated runtime dependencies."""
    from subprocess import CompletedProcess

    from skills.daemon.scripts.ops import heal_validate

    calls: list[list[str]] = []

    def fake_run(command, project_root, timeout=120):
        del project_root, timeout
        calls.append(command)
        return CompletedProcess(command, 0, stdout="repaired", stderr="")

    monkeypatch.setattr(heal_validate, "_run_command", fake_run, raising=False)
    monkeypatch.setattr(heal_validate, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = heal_validate.fix(
        _ctx(tmp_path, difficulty=1),
        [
            {"type": "mcp_runtime_python_missing", "detail": "missing .venv/bin/python3"},
            {"type": "dashboard_dependency_missing", "detail": "missing node_modules/esbuild"},
        ],
    )

    assert result.success is True
    assert any(call[:2] == ["uv", "sync"] for call in calls)
    assert any(call[:2] == ["corepack", "pnpm"] and "apps/dashboard" in " ".join(call) for call in calls)
    assert {action["action"] for action in result.actions} == {
        "uv_sync",
        "dashboard_pnpm_install",
    }
