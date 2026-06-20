"""Auto-generated importability test for log_monitor."""
from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_log_monitor_importable():
    """Verify that log_monitor can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.log_monitor")
    assert mod is not None


def test_out_replaces_unencodable_characters_for_cp1252_stream():
    """Windows scheduled-task stdout may use cp1252; status output must not crash."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.log_monitor")
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")

    mod._out("\U0001f440 Log Monitor started", file=stream)
    stream.flush()

    assert buffer.getvalue().replace(b"\r\n", b"\n") == b"? Log Monitor started\n"
