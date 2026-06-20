"""Auto-generated importability test for cleanup_processes."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_cleanup_processes_importable():
    """Verify that cleanup_processes can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.cleanup_processes")
    assert mod is not None


def test_is_pid_alive_uses_windows_process_lookup(monkeypatch):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.cleanup_processes")
    monkeypatch.setattr(mod, "IS_WINDOWS", True)
    monkeypatch.setattr(
        mod.os,
        "kill",
        lambda *_args: (_ for _ in ()).throw(AssertionError("os.kill must not be used on Windows")),
    )
    monkeypatch.setattr(mod, "run_command", lambda *_args, **_kwargs: "1234")

    assert mod.is_pid_alive("1234") is True


def test_is_pid_alive_windows_missing_pid_returns_false(monkeypatch):
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.cleanup_processes")
    monkeypatch.setattr(mod, "IS_WINDOWS", True)
    monkeypatch.setattr(mod, "run_command", lambda *_args, **_kwargs: "")

    assert mod.is_pid_alive("1234") is False
