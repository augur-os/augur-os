"""Tests for project.yaml path resolution chain."""

import logging
import os
from pathlib import Path
from unittest.mock import patch
import pytest
import yaml
from src.config import paths


@pytest.fixture(autouse=True)
def reset_caches():
    """Clear all path caches between tests."""
    paths.invalidate_project_cache()
    yield
    paths.invalidate_project_cache()


class TestGetProjectPaths:
    """Test get_project_paths() reads from project.yaml."""

    def test_reads_vault_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/test-vault\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["vault"] == Path("/tmp/test-vault").resolve()

    def test_reads_documents_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  documents: /tmp/test-docs\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["documents"] == Path("/tmp/test-docs").resolve()

    def test_expands_tilde(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: ~/my-vault\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result["vault"] == Path.home() / "my-vault"

    def test_missing_paths_block_returns_empty(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result == {}

    def test_paths_not_dict_returns_empty(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths: not-a-dict\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert result == {}

    def test_unknown_keys_ignored(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v\n  bogus: /tmp/x\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            result = paths.get_project_paths()
        assert "vault" in result
        assert "bogus" not in result

    def test_caching(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v1\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            r1 = paths.get_project_paths()
            project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v2\n")
            r2 = paths.get_project_paths()
        assert r1["vault"] == r2["vault"]  # cached, not re-read

    def test_cache_invalidation(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v1\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path):
            r1 = paths.get_project_paths()
            project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/v2\n")
            paths.invalidate_project_cache()
            r2 = paths.get_project_paths()
        assert r1["vault"] != r2["vault"]


class TestResolutionOrder:
    """Test env var > project.yaml > hardcoded default."""

    def test_env_var_overrides_project_yaml(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with (
            patch.object(paths, "get_project_root", return_value=tmp_path),
            patch.object(paths, "_resolve_with_discovery", side_effect=lambda _kind, resolved: resolved),
            patch.dict(os.environ, {"AUGUR_VAULT": "/tmp/from-env"}),
        ):
            result = paths.get_vault_dir()
        assert result == Path("/tmp/from-env").resolve()

    def test_project_yaml_overrides_hardcoded(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with (
            patch.object(paths, "get_project_root", return_value=tmp_path),
            patch.object(paths, "_resolve_with_discovery", side_effect=lambda _kind, resolved: resolved),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert result == Path("/tmp/from-yaml").resolve()

    def test_hardcoded_default_when_nothing_set(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert "Vault" in str(result) or "vault" in str(result)


class TestProjectRootDetection:
    """Test worktree-aware project root detection."""

    def test_current_worktree_root_beats_file_location(self, tmp_path):
        main_root = tmp_path / "main"
        main_root.mkdir()
        (main_root / "project.yaml").write_text("name: Main\n", encoding="utf-8")

        worktree_root = tmp_path / "worktrees" / "feature"
        worktree_root.mkdir(parents=True)
        (worktree_root / "project.yaml").write_text("name: Worktree\n", encoding="utf-8")
        (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")

        nested_cwd = worktree_root / "skills" / "rag"
        nested_cwd.mkdir(parents=True)

        with (
            patch.object(paths, "_project_root_from_file", return_value=main_root),
            patch.object(Path, "cwd", return_value=nested_cwd),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("AUGUR_ROOT", None)
            os.environ.pop("AUGUR_CORE", None)
            os.environ.pop("AUGUR_REPO", None)
            result = paths.get_project_root()

        assert result == worktree_root

    def test_stale_env_root_does_not_override_current_worktree(self, tmp_path):
        main_root = tmp_path / "main"
        main_root.mkdir()
        (main_root / "project.yaml").write_text("name: Main\n", encoding="utf-8")
        (main_root / ".git").mkdir()

        worktree_root = tmp_path / "worktrees" / "feature"
        worktree_root.mkdir(parents=True)
        (worktree_root / "project.yaml").write_text("name: Worktree\n", encoding="utf-8")
        (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")

        nested_cwd = worktree_root / "skills" / "rag"
        nested_cwd.mkdir(parents=True)

        with (
            patch.object(paths, "_project_root_from_file", return_value=main_root),
            patch.object(Path, "cwd", return_value=nested_cwd),
            patch.dict(os.environ, {"AUGUR_ROOT": str(main_root)}, clear=False),
        ):
            result = paths.get_project_root()

        assert result == worktree_root


class TestLegacyRollback:
    """Test AUGUR_PATH_LEGACY=1 skips project.yaml reading."""

    def test_legacy_flag_skips_project_yaml(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/from-yaml\n")
        with (
            patch.object(paths, "get_project_root", return_value=tmp_path),
            patch.dict(os.environ, {"AUGUR_PATH_LEGACY": "1"}),
        ):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert result != Path("/tmp/from-yaml")


class TestDiscoveryIntegration:
    """Test that get_vault_dir() triggers discovery when path is missing."""

    def test_discovery_triggers_on_missing_vault(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/nonexistent-vault\n")
        real_vault = tmp_path / "real-vault"
        real_vault.mkdir()
        (real_vault / ".augur-vault").write_text("project: Test\n")
        with (
            patch.object(paths, "get_project_root", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=False),
            patch("src.config.path_discovery.default_search_roots", return_value=[tmp_path]),
        ):
            os.environ.pop("AUGUR_VAULT", None)
            from src.config import path_discovery

            path_discovery._discovery_cache.clear()
            result = paths.get_vault_dir()
        assert result == real_vault

    def test_discovery_does_not_warn_during_normal_resolution(self, tmp_path, caplog):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /tmp/nonexistent-vault\n")
        real_vault = tmp_path / "real-vault"
        real_vault.mkdir()
        (real_vault / ".augur-vault").write_text("project: Test\n")

        with (
            patch.object(paths, "get_project_root", return_value=tmp_path),
            patch.dict(os.environ, {}, clear=False),
            patch("src.config.path_discovery.default_search_roots", return_value=[tmp_path]),
            caplog.at_level(logging.WARNING),
        ):
            os.environ.pop("AUGUR_VAULT", None)
            from src.config import path_discovery

            path_discovery._discovery_cache.clear()
            result = paths.get_vault_dir()

        assert result == real_vault
        assert "Run 'augur config fix'" not in caplog.text

    def test_no_discovery_when_path_exists(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(f"name: Test\npaths:\n  vault: {vault}\n")
        with patch.object(paths, "get_project_root", return_value=tmp_path), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_VAULT", None)
            result = paths.get_vault_dir()
        assert result == vault

    def test_checked_in_path_config_matches_discovered_local_paths(self):
        """Checked-in path config should not stay stale when discovery finds moved roots."""
        from src.config import path_discovery

        project_root = Path(__file__).resolve().parents[2]
        with (
            patch.object(paths, "get_project_root", return_value=project_root),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("AUGUR_VAULT", None)
            os.environ.pop("AUGUR_DOCUMENTS", None)
            path_discovery._discovery_cache.clear()
            paths.invalidate_project_cache()
            resolved_vault = paths.get_vault_dir()
            resolved_documents = paths.get_documents_dir()

        if not resolved_vault.exists() and not resolved_documents.exists():
            pytest.skip("No local vault/documents roots available for checked-in config drift check")

        project_data = yaml.safe_load((project_root / "project.yaml").read_text(encoding="utf-8"))
        system_vault = yaml.safe_load((project_root / "config" / "system" / "vault.yaml").read_text(encoding="utf-8"))

        if resolved_vault.exists():
            configured_vault = Path(os.path.expanduser(project_data["paths"]["vault"])).resolve()
            configured_system_vault = Path(os.path.expanduser(system_vault["vault"]["path"])).resolve()
            assert configured_vault == resolved_vault
            assert configured_system_vault == resolved_vault

        if resolved_documents.exists():
            configured_documents = Path(os.path.expanduser(project_data["paths"]["documents"])).resolve()
            assert configured_documents == resolved_documents
