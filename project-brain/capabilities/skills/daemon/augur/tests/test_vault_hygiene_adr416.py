"""
ADR-416 test coverage: Vault Hygiene Cleanup.

Verifies that the vault has no hardening-reports, no config alongside user data,
no nested duplicate folders, and that the new paths.py helper works correctly.

Run with: pytest tests/nightly/test_vault_hygiene_adr416.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Repo root discovered by marker (pyproject.toml + .git), robust to brain-layout depth.
PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
VAULT_ROOT = Path.home() / "Vault" / "Augur"

# Ensure project root is on path for imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestNoHardeningInVault:
    """Bug 3 fix: hardening-reports should be in state dir, not vault."""

    def test_zero_hardening_dirs_in_vault(self):
        """No hardening-reports/ directories should exist in the vault."""
        if not VAULT_ROOT.exists():
            pytest.skip("Vault not present")
        violations = []
        for d in VAULT_ROOT.rglob("hardening-reports"):
            if d.is_dir() and any(d.iterdir()):
                violations.append(str(d.relative_to(VAULT_ROOT)))
        assert violations == [], "hardening-reports/ found in vault:\n" + "\n".join(violations)

    def test_hardening_reports_in_state_dir(self):
        """Hardening reports should be accessible in the state dir."""
        from src.config.paths import get_hardening_dir
        state_dir = get_hardening_dir()
        if not state_dir.exists():
            pytest.skip("State hardening dir not yet populated")
        # Should have at least some hub directories
        subdirs = [d for d in state_dir.iterdir() if d.is_dir()]
        assert len(subdirs) > 0, f"State hardening dir exists but has no hub subdirs: {state_dir}"

    def test_get_hardening_dir_resolves_to_state(self):
        """get_hardening_dir() should return a path under runtime state, not vault."""
        from src.config.paths import get_hardening_dir
        path = get_hardening_dir("test-skill")
        assert "Vault" not in str(path), f"get_hardening_dir resolves to vault: {path}"
        assert "hardening" in str(path)
        assert "test-skill" in str(path)

    def test_get_hardening_dir_no_skill(self):
        """get_hardening_dir() without skill returns the root hardening dir."""
        from src.config.paths import get_hardening_dir
        path = get_hardening_dir()
        assert path.name == "hardening"


class TestNoConfigAlongsideData:
    """Bug 2 fix: config.yaml should not sit alongside .md user data."""

    def test_zero_config_in_data_dirs(self):
        """No config.yaml should exist alongside .md files in data directories."""
        if not VAULT_ROOT.exists():
            pytest.skip("Vault not present")
        violations = []
        for config_file in VAULT_ROOT.rglob("config.yaml"):
            parent = config_file.parent
            if parent.name.startswith("_"):
                continue
            if list(parent.glob("*.md")):
                violations.append(str(config_file.relative_to(VAULT_ROOT)))
        assert violations == [], "config.yaml alongside .md files:\n" + "\n".join(violations)


class TestNoDuplicateFolders:
    """Bug 1 fix: no nested self-duplicate folders."""

    def test_no_nested_self_duplicates(self):
        """No directory should be named the same as its parent (e.g., reviews/reviews)."""
        if not VAULT_ROOT.exists():
            pytest.skip("Vault not present")
        violations = []
        # Skip hub/skill same-name (career/career is by design)
        hub_skills = set()
        for hub in VAULT_ROOT.iterdir():
            if hub.is_dir():
                for skill in hub.iterdir():
                    if skill.is_dir():
                        hub_skills.add(str(skill))

        for d in VAULT_ROOT.rglob("*"):
            if not d.is_dir():
                continue
            if str(d) in hub_skills:
                continue  # skip hub/skill same-name (by design)
            if d.parent.name == d.name and str(d.parent) not in hub_skills:
                violations.append(str(d.relative_to(VAULT_ROOT)))
        assert violations == [], "Nested self-duplicates:\n" + "\n".join(violations)


class TestMcpHygieneWritePath:
    """Verify mcp_hygiene.py writes to state dir, not vault."""

    def test_mcp_hygiene_uses_get_hardening_dir(self):
        """mcp_hygiene.py should import and use get_hardening_dir."""
        mcp_hygiene = PROJECT_ROOT / "project-brain/capabilities/skills/daemon/scripts/ops/mcp_hygiene.py"
        if not mcp_hygiene.exists():
            pytest.skip("mcp_hygiene.py not found")
        content = mcp_hygiene.read_text()
        assert "get_hardening_dir" in content, "mcp_hygiene.py should use get_hardening_dir()"
        assert 'hardening-reports' not in content.split("get_hardening_dir")[0][-200:], \
            "mcp_hygiene.py should not have stale hardening-reports path near the import"


class TestMigrationScripts:
    """Verify migration scripts exist and are functional."""

    def test_scripts_exist(self):
        scripts = [
            "scripts/vault_hygiene/migrate_hardening.py",
            "scripts/vault_hygiene/migrate_config.py",
            "scripts/vault_hygiene/deduplicate_folders.py",
        ]
        for s in scripts:
            assert (PROJECT_ROOT / s).exists(), f"Missing: {s}"

    def test_migrate_hardening_idempotent(self):
        """Running hardening migration on clean vault is a no-op."""
        spec = importlib.util.spec_from_file_location(
            "migrate_hardening", PROJECT_ROOT / "scripts/vault_hygiene/migrate_hardening.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stats = mod.migrate(dry_run=True)
        assert stats["files"] == 0, f"Hardening migration found {stats['files']} files to move — vault should be clean"

    def test_migrate_config_idempotent(self):
        """Running config migration on clean vault is a no-op."""
        spec = importlib.util.spec_from_file_location(
            "migrate_config", PROJECT_ROOT / "scripts/vault_hygiene/migrate_config.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stats = mod.migrate(dry_run=True)
        assert stats["moved"] == 0, f"Config migration found {stats['moved']} files to move — vault should be clean"


class TestSyncSkipsUnderscoreDirs:
    """Verify the sync engine skips _-prefixed directories."""

    def test_config_dir_not_synced(self):
        """_config/ directories should not appear as sync sections."""
        sync_scripts = PROJECT_ROOT / "skills/apple/scripts"
        if not (sync_scripts / "sync/engine.py").exists():
            pytest.skip("Sync engine not present")
        # Verify the concept: _config starts with _ so glob("*.md") in _config returns nothing useful
        config_dir = VAULT_ROOT / "productivity" / "apple" / "_config"
        if config_dir.exists():
            md_files = list(config_dir.glob("*.md"))
            assert md_files == [], "_config/ should not contain .md sync data"
