"""Auto-generated importability test for check_repo_health."""
from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_check_repo_health_importable():
    """Verify that check_repo_health can be imported without errors."""
    script = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "check_repo_health.py"
    spec = importlib.util.spec_from_file_location("check_repo_health_under_test", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    assert mod is not None
