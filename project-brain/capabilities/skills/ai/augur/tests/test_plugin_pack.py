"""Auto-generated importability test for plugin_pack."""
from __future__ import annotations

import sys
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_plugin_pack_importable():
    """Verify that plugin_pack can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.ai.augur.adapters._plugin_pack")
    assert mod is not None
