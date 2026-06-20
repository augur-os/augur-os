"""Auto-generated importability test for unified_daemon."""
from __future__ import annotations

import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from subprocess import CompletedProcess

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _fail_if_read_pid():
    raise AssertionError("_read_pid should not be used by cmd_status")


def test_unified_daemon_importable():
    """Verify that unified_daemon can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    assert mod is not None


def test_apple_note_services_use_managed_skill_root(monkeypatch, tmp_path):
    """Apple daemon services should run from the resolved local/vault skill root."""
    import importlib

    apple_root = tmp_path / "vault" / "skills" / "apple"
    (apple_root / "scripts").mkdir(parents=True)
    (apple_root / "scripts" / "note_watcher.py").write_text("", encoding="utf-8")
    (apple_root / "scripts" / "note_ingest.py").write_text("", encoding="utf-8")

    def fake_get_skill_root(skill_name: str) -> Path:
        if skill_name == "apple":
            return apple_root
        raise ValueError(skill_name)

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("src.config.paths.get_skill_root", fake_get_skill_root)

    mod = importlib.reload(importlib.import_module("skills.daemon.scripts.unified_daemon"))

    assert mod.CHILD_SERVICES["note_watcher"]["script"] == apple_root / "scripts" / "note_watcher.py"
    assert mod.CHILD_SERVICES["note_ingest"]["script"] == apple_root / "scripts" / "note_ingest.py"


def test_cmd_status_reports_missing_status_file(monkeypatch, tmp_path, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    monkeypatch.setattr(mod, "STATUS_FILE", tmp_path / "missing_status.json")

    result = mod.cmd_status()

    output = capsys.readouterr().out
    assert result == 1
    assert "Status file: MISSING" in output
    assert "Daemon: STOPPED" in output


def test_cmd_status_reports_stale_status_file(monkeypatch, tmp_path, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    daemon_pid = 12345
    status_file = tmp_path / "daemon_status.json"
    status_file.write_text(
        json.dumps(
            {
                "daemon_pid": daemon_pid,
                "started_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "uptime_seconds": 600,
                "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATUS_FILE", status_file)
    monkeypatch.setattr(mod.daemon_diagnostics, "_default_pid_exists", lambda pid: False)
    monkeypatch.setattr(mod, "_read_pid", _fail_if_read_pid)

    result = mod.cmd_status()

    output = capsys.readouterr().out
    assert result == 1
    assert "Status file: STALE" in output
    assert "Daemon: STOPPED" in output


def test_cmd_status_reports_stale_matching_pid_as_stopped(monkeypatch, tmp_path, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    daemon_pid = 12345
    status_file = tmp_path / "daemon_status.json"
    status_file.write_text(
        json.dumps(
            {
                "daemon_pid": daemon_pid,
                "started_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "uptime_seconds": 600,
                "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "services": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATUS_FILE", status_file)
    monkeypatch.setattr(mod.daemon_diagnostics, "_default_pid_exists", lambda pid: pid == daemon_pid)
    monkeypatch.setattr(mod, "_read_pid", _fail_if_read_pid)

    result = mod.cmd_status()

    output = capsys.readouterr().out
    assert result == 1
    assert "Status file: STALE" in output
    assert f"Daemon: STOPPED (PID {daemon_pid})" in output


def test_cmd_status_reports_fresh_running_status(monkeypatch, tmp_path, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    daemon_pid = 12345
    status_file = tmp_path / "daemon_status.json"
    status_file.write_text(
        json.dumps(
            {
                "daemon_pid": daemon_pid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": 12,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "services": {
                    "log_monitor": {
                        "state": "running",
                        "pid": 23456,
                        "total_restarts": 0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATUS_FILE", status_file)
    monkeypatch.setattr(mod.daemon_diagnostics, "_default_pid_exists", lambda pid: pid == daemon_pid)
    monkeypatch.setattr(mod, "_read_pid", _fail_if_read_pid)

    result = mod.cmd_status()

    output = capsys.readouterr().out
    assert result == 0
    assert "Status file: FRESH" in output
    assert f"Daemon: RUNNING (PID {daemon_pid})" in output
    assert "log_monitor: RUNNING" in output


def test_read_pid_uses_diagnostics_liveness_probe(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(mod, "PID_FILE", pid_file)
    monkeypatch.setattr(mod.os, "kill", lambda *_args: (_ for _ in ()).throw(OSError(87, "bad probe")))
    monkeypatch.setattr(mod.daemon_diagnostics, "_default_pid_exists", lambda pid: pid == 12345)

    assert mod._read_pid() == 12345


def test_cmd_stop_waits_with_pid_liveness_wrapper(monkeypatch, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    states = iter([True, False])
    signals = []
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod, "_read_pid", lambda: 12345)
    monkeypatch.setattr(mod, "_pid_exists", lambda _pid: next(states))
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)

    result = mod.cmd_stop()

    output = capsys.readouterr().out
    assert result == 0
    assert "Daemon stopped" in output
    assert signals == [(12345, mod.signal.SIGTERM)]


def test_cmd_stop_uses_taskkill_tree_on_windows(monkeypatch, capsys):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.unified_daemon")
    calls = []
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod, "_read_pid", lambda: 12345)
    monkeypatch.setattr(mod, "_pid_exists", lambda _pid: False)

    def fake_run(command, **_kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, stdout="SUCCESS", stderr="")

    monkeypatch.setattr(mod, "_run_command", fake_run)

    result = mod.cmd_stop()

    output = capsys.readouterr().out
    assert result == 0
    assert "Daemon stopped" in output
    assert calls == [["taskkill", "/PID", "12345", "/T", "/F"]]
