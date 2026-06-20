"""
VaultAdapter hierarchy tests (ADR-436).

Run with: pytest skills/ai/augur/tests/test_vault_adapters.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure sync_agents package is importable
# parents: [0]=tests, [1]=augur, [2]=ai, so scripts/sync_agents is under [2]
_scripts_dir = Path(__file__).resolve().parents[2] / "scripts" / "sync_agents"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from vault_adapters import VaultAdapter, LocalFileVaultAdapter, LocalAppVaultAdapter, CloudVaultAdapter
from vault_adapters.obsidian import ObsidianVaultAdapter


@pytest.fixture
def vault_dir(tmp_path):
    """Create a mock vault directory structure."""
    vault = tmp_path / "Vault" / "Augur"
    vault.mkdir(parents=True)
    # Create some test notes
    memory_dir = vault / "memory"
    memory_dir.mkdir()
    (memory_dir / "test.md").write_text("# Test Note\nContent here")
    dev_dir = vault / "dev"
    dev_dir.mkdir()
    (dev_dir / "adr.md").write_text("# ADR\nSome ADR content")
    return vault


class TestVaultAdapterABC:
    """Test VaultAdapter base class and tier hierarchy."""

    def test_import_vault_adapter(self):
        assert VaultAdapter is not None
        assert LocalFileVaultAdapter is not None
        assert LocalAppVaultAdapter is not None
        assert CloudVaultAdapter is not None

    def test_vault_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            VaultAdapter()

    def test_local_file_vault_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            LocalFileVaultAdapter()

    def test_local_app_vault_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            LocalAppVaultAdapter()

    def test_cloud_vault_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            CloudVaultAdapter()


class TestObsidianVaultAdapter:
    """Test ObsidianVaultAdapter implementation."""

    def test_adapter_name(self):
        adapter = ObsidianVaultAdapter()
        assert adapter.adapter_name == "obsidian"

    def test_detect_installed_false_no_obsidian_dir(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            assert adapter.detect_installed() is False

    def test_detect_installed_true_with_obsidian_dir(self, vault_dir):
        (vault_dir / ".obsidian").mkdir()
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            assert adapter.detect_installed() is True

    def test_sync_from_vault(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            result = adapter.sync_from_vault()
        assert "memory" in result
        assert "test.md" in result["memory"]
        assert "# Test Note" in result["memory"]["test.md"]

    def test_sync_from_vault_reads_dev(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            result = adapter.sync_from_vault()
        assert "dev" in result
        assert "adr.md" in result["dev"]

    def test_sync_from_vault_empty_when_no_vault(self, tmp_path):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=tmp_path / "nonexistent"):
            result = adapter.sync_from_vault()
        assert result == {}

    def test_sync_to_vault_writes_files(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        content = {
            "managed_dirs": ["memory"],
            "memory": {"new-note.md": "# New Note\nNew content"},
        }
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            written = adapter.sync_to_vault(content)
        assert written == 1
        assert (vault_dir / "memory" / "new-note.md").read_text() == "# New Note\nNew content"

    def test_sync_to_vault_skips_identical_content(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        content = {
            "managed_dirs": ["memory"],
            "memory": {"test.md": "# Test Note\nContent here"},
        }
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            written = adapter.sync_to_vault(content)
        assert written == 0  # Content unchanged, no write

    def test_sync_to_vault_returns_zero_for_missing_vault(self, tmp_path):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=tmp_path / "nonexistent"):
            written = adapter.sync_to_vault({"memory": {"a.md": "content"}})
        assert written == 0

    def test_scaffold_creates_obsidian_config(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            result = adapter.scaffold()
        assert result["status"] == "created"
        assert (vault_dir / ".obsidian" / "app.json").exists()
        assert (vault_dir / ".obsidian" / "core-plugins.json").exists()

    def test_scaffold_idempotent(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        (vault_dir / ".obsidian").mkdir()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            result = adapter.scaffold()
        assert result["status"] == "already_configured"

    def test_get_managed_dirs(self, vault_dir):
        adapter = ObsidianVaultAdapter()
        with patch.object(adapter, "get_vault_root", return_value=vault_dir):
            dirs = adapter.get_managed_dirs()
        assert len(dirs) == 1
        assert ".obsidian" in dirs[0]
