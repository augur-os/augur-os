"""Auto-generated importability test for service_healer."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_service_healer_importable():
    """Verify that service_healer can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.service_healer")
    assert mod is not None


def test_resolve_daemon_skill_root_ignores_retired_repo_root(tmp_path):
    """Daemon registration should target project-brain even if stale skills/ remains."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.service_healer")
    shared_root = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon"
    legacy_root = tmp_path / "skills" / "daemon"
    shared_root.mkdir(parents=True)
    legacy_root.mkdir(parents=True)

    assert mod._resolve_daemon_skill_root(tmp_path) == shared_root


def test_resolve_daemon_skill_root_defaults_to_shared_vault_without_legacy_fallback(tmp_path):
    """A missing project-brain directory should not make service healing use repo-root skills."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.service_healer")
    legacy_root = tmp_path / "skills" / "daemon"
    legacy_root.mkdir(parents=True)

    assert mod._resolve_daemon_skill_root(tmp_path) == tmp_path / "project-brain" / "capabilities" / "skills" / "daemon"
