"""Auto-generated importability test for codex_plugin."""
from __future__ import annotations

import sys
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "sync_agents" / "adapters"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_codex_plugin_importable():
    """Verify that codex_plugin can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.ai.scripts.sync_agents.adapters.codex_plugin")
    assert mod is not None
