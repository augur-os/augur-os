"""Conftest for sync_agents tests.

Patches get_skill_vault_dir before the sync_agents constants module
is imported, since it resolves paths at module-load time.

After the project-brain migration, sync_agents lives at
project-brain/capabilities/skills/ai/scripts/
so we add that directory to sys.path for direct package imports.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch
import pytest

# Add the scripts directory to sys.path so `sync_agents` is importable.
_project_root = Path(__file__).resolve().parents[2]
_skill_root = _project_root / "project-brain" / "capabilities" / "skills" / "ai"
_scripts_dir = str(_skill_root / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Add the skill's lib directory so `discovery` and other lib modules are importable.
_lib_dir = str(_skill_root / "augur" / "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)


def _mock_get_skill_vault_dir(skill_name):
    """Mock that returns a test vault path. Validation is handled by dir_alignment."""
    return Path("/tmp/augur-test-vault") / skill_name


@pytest.fixture(autouse=True, scope="package")
def _patch_skill_vault_dir_for_sync_agents():
    """Keep sync_agents path shims local to this test package."""
    with patch(
        "src.config.paths.get_skill_vault_dir",
        side_effect=_mock_get_skill_vault_dir,
    ):
        yield
