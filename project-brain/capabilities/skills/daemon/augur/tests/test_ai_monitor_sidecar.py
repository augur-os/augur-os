"""Tests for AISidecarManager — AI client spawn, restart, context pressure."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_sidecar_manager_skips_when_cli_unavailable():
    """If resolve_cli() raises, sidecar should not start."""
    from ai_monitor_sidecar import AISidecarManager

    with patch("ai_monitor_sidecar.resolve_cli", side_effect=RuntimeError("No CLI")):
        mgr = AISidecarManager(config={"enabled": True})
        result = mgr.start()
        assert result is False
        assert mgr.state == "unavailable"


def test_sidecar_resolves_cli_with_augmented_env_path(monkeypatch):
    """Launchd-safe PATH must be used when resolving the sidecar CLI."""
    from ai_monitor_sidecar import AISidecarManager

    mgr = AISidecarManager(config={"enabled": True, "use_pty": False})
    mgr._env = {"PATH": "/augur/bin"}
    captured = {}

    def fake_resolve_cli(*, search_path=None):
        captured["search_path"] = search_path
        return "/augur/bin/claude"

    monkeypatch.setattr("ai_monitor_sidecar.resolve_cli", fake_resolve_cli)
    monkeypatch.setattr(
        "ai_monitor_sidecar.build_sidecar_cmd",
        lambda *_args, **_kwargs: ["/bin/echo", "ok"],
    )

    class DummyProcess:
        pid = 123

        def poll(self):
            return None

    monkeypatch.setattr(
        "ai_monitor_sidecar.Popen", lambda *_args, **_kwargs: DummyProcess()
    )

    assert mgr.start() is True
    assert captured["search_path"] == "/augur/bin"
    assert mgr.state == "running"


def test_sidecar_uses_explicit_monitor_prompt(monkeypatch):
    """Daemon sidecar must not depend on a generated slash command surface."""
    from ai_monitor_sidecar import AISidecarManager, MONITOR_PROMPT

    captured = {}
    mgr = AISidecarManager(config={"enabled": True, "use_pty": False})

    monkeypatch.setattr(
        "ai_monitor_sidecar.resolve_cli",
        lambda *, search_path=None: "/augur/bin/claude",
    )

    def fake_build_sidecar_cmd(_cli_path, prompt, **_kwargs):
        captured["prompt"] = prompt
        return ["/bin/echo", "ok"]

    monkeypatch.setattr("ai_monitor_sidecar.build_sidecar_cmd", fake_build_sidecar_cmd)

    class DummyProcess:
        pid = 123

        def poll(self):
            return None

    monkeypatch.setattr(
        "ai_monitor_sidecar.Popen", lambda *_args, **_kwargs: DummyProcess()
    )

    assert mgr.start() is True
    assert captured["prompt"] == MONITOR_PROMPT
    assert "/daemon --monitor" not in captured["prompt"]
    assert "ai_monitor_watcher.py --wait-for-event" in captured["prompt"]


def test_sidecar_status_does_not_report_running_without_live_pid():
    """Status should not claim running after the sidecar process exits."""
    from ai_monitor_sidecar import AISidecarManager

    class ExitedProcess:
        pid = 123

        def poll(self):
            return 0

    mgr = AISidecarManager(config={"enabled": True})
    mgr.state = "running"
    mgr.process = ExitedProcess()

    status = mgr._status_dict()
    assert status["state"] == "exited"
    assert status["pid"] is None


def test_sidecar_manager_disabled_by_config():
    """If enabled=false in config, sidecar should not start."""
    from ai_monitor_sidecar import AISidecarManager

    mgr = AISidecarManager(config={"enabled": False})
    result = mgr.start()
    assert result is False
    assert mgr.state == "disabled"


def test_context_pressure_detected():
    """Sidecar detects context pressure from bytes counter file."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "ai_monitor_bytes.json"
        state_file.write_text(json.dumps({"bytes_outputted": 600000}))

        mgr = AISidecarManager(
            config={
                "enabled": True,
                "context_pressure_bytes": 500000,
            }
        )
        mgr._state_dir = Path(tmpdir)
        assert mgr._check_context_pressure() is True


def test_context_pressure_not_triggered_below_threshold():
    """No pressure when bytes are below threshold."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "ai_monitor_bytes.json"
        state_file.write_text(json.dumps({"bytes_outputted": 100000}))

        mgr = AISidecarManager(
            config={
                "enabled": True,
                "context_pressure_bytes": 500000,
            }
        )
        mgr._state_dir = Path(tmpdir)
        assert mgr._check_context_pressure() is False


def test_restart_deferred_when_fix_lock_held():
    """Don't restart sidecar if FIX_LOCK_FILE exists with alive PID."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "fix.lock"
        lock_file.write_text(
            json.dumps(
                {
                    "issue_key": "test",
                    "pid": os.getpid(),  # current process — alive
                    "started": "2026-03-22T00:00:00",
                }
            )
        )

        mgr = AISidecarManager(config={"enabled": True})
        mgr._fix_lock_file = lock_file
        assert mgr._fix_lock_held() is True


def test_fix_lock_not_held_when_pid_dead():
    """Fix lock with dead PID is not considered held."""
    from ai_monitor_sidecar import AISidecarManager

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "fix.lock"
        lock_file.write_text(
            json.dumps(
                {
                    "issue_key": "test",
                    "pid": 99999999,  # non-existent PID
                    "started": "2026-03-22T00:00:00",
                }
            )
        )

        mgr = AISidecarManager(config={"enabled": True})
        mgr._fix_lock_file = lock_file
        assert mgr._fix_lock_held() is False
