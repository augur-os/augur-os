"""Auto-generated importability test for locks."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_locks_importable():
    """Verify that locks can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.monitor.locks")
    assert mod is not None


def test_build_lock_probe_returns_false_when_lock_missing(tmp_path, monkeypatch):
    mod = importlib.import_module("skills.daemon.scripts.monitor.locks")
    monkeypatch.setattr(mod, "get_runtime_dir", lambda: tmp_path)

    assert mod.is_build_lock_held() is False
