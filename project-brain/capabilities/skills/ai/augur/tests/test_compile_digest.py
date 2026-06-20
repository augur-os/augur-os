"""Auto-generated importability test for compile_digest."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "agent_digest"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_compile_digest_importable():
    """Verify that compile_digest can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.ai.scripts.ops.agent_digest.compile_digest")
    assert mod is not None
