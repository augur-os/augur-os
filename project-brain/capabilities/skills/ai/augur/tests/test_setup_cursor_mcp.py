"""Tests for setup_cursor_mcp wrapper behavior."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_setup_cursor_mcp_delegates_to_configure_mcp(monkeypatch):
    """setup_cursor_mcp should delegate to configure_mcp with cursor auto mode."""
    import importlib

    module = importlib.import_module("skills.ai.scripts.setup_cursor_mcp")
    project_root = Path("/tmp/augur")
    python_path = Path("/tmp/augur/.venv/bin/python")
    expected_script = project_root / "scripts" / "configure_mcp.py"
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command, check=False):
        calls.append((command, check))
        return subprocess.CompletedProcess(command, 17)

    monkeypatch.setattr(module, "get_project_root", lambda: project_root)
    monkeypatch.setattr(module, "get_python_executable", lambda: python_path)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.setup_cursor_mcp() == 17
    assert calls == [([str(python_path), str(expected_script), "--client", "cursor", "--auto"], False)]
