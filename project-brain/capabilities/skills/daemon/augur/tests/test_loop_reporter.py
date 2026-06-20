"""Auto-generated importability test for loop_reporter."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_loop_reporter_importable():
    """Verify that loop_reporter can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.adaptive.loop_reporter")
    assert mod is not None


def test_loop_reporter_unknown_owner_without_scheduler_metadata():
    mod = importlib.import_module("skills.daemon.scripts.adaptive.loop_reporter")

    owner, detail = mod._summarize_loop_ownership([])

    assert owner == "unknown"
    assert detail == "no discovered scheduler metadata"


def test_loop_reporter_status_owner_uses_codex_for_nightly_default():
    mod = importlib.import_module("skills.daemon.scripts.adaptive.loop_reporter")

    owner, detail = mod._summarize_loop_ownership(
        [SimpleNamespace(trigger="nightly", scheduler="codex")]
    )

    assert owner == "codex"
    assert detail == "nightly via codex"


def test_loop_reporter_status_owner_preserves_explicit_daemon():
    mod = importlib.import_module("skills.daemon.scripts.adaptive.loop_reporter")

    owner, detail = mod._summarize_loop_ownership(
        [SimpleNamespace(trigger="nightly", scheduler="daemon")]
    )

    assert owner == "daemon"
    assert detail == "nightly via daemon"
