"""Auto-generated importability test for precommit_hooks."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_precommit_hooks_importable():
    """Verify that precommit_hooks can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.platform-admin.scripts.precommit_hooks")
    assert mod is not None


def test_generated_hook_runs_pre_commit_suite():
    """Installed hook must invoke the repo's pre-commit config."""
    import importlib

    mod = importlib.import_module("skills.platform-admin.scripts.precommit_hooks")

    assert "validate-file-placement" in mod.PRE_COMMIT_HOOK
    assert "cleanup-temp-files" in mod.PRE_COMMIT_HOOK
    assert "uvx pre-commit" in mod.PRE_COMMIT_HOOK
