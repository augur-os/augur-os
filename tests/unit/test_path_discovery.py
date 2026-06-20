"""Tests for path self-discovery engine."""

from pathlib import Path
from unittest.mock import patch
import pytest
from src.config import path_discovery


@pytest.fixture(autouse=True)
def reset_discovery_cache():
    """Clear discovery cache between tests."""
    path_discovery._discovery_cache.clear()
    yield
    path_discovery._discovery_cache.clear()


class TestMarkerDiscovery:
    def test_finds_vault_by_marker(self, tmp_path):
        vault = tmp_path / "my-vault"
        vault.mkdir()
        (vault / ".augur-vault").write_text("project: Test\ncreated: 2026-03-23\n")
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result == vault

    def test_finds_docs_by_marker(self, tmp_path):
        docs = tmp_path / "my-docs"
        docs.mkdir()
        (docs / ".augur-docs").write_text("project: Test\ncreated: 2026-03-23\n")
        result = path_discovery.discover_path(
            "documents",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result == docs

    def test_returns_none_when_no_marker(self, tmp_path):
        (tmp_path / "some-dir").mkdir()
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
        )
        assert result is None


class TestFingerprintDiscovery:
    def test_finds_vault_by_structure(self, tmp_path):
        vault = tmp_path / "actual-vault"
        vault.mkdir()
        (vault / "memory").mkdir()
        for name in ["career", "health", "finance"]:
            (vault / name).mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name in ["career", "health", "finance", "other"]:
            (skills_dir / name).mkdir()
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=skills_dir,
        )
        assert result == vault

    def test_no_match_without_memory_dir(self, tmp_path):
        vault = tmp_path / "not-a-vault"
        vault.mkdir()
        for name in ["career", "health", "finance"]:
            (vault / name).mkdir()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        for name in ["career", "health", "finance"]:
            (skills_dir / name).mkdir()
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=skills_dir,
        )
        assert result is None

    def test_fallback_fingerprint_without_skills_dir(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "memory").mkdir()
        (vault / "dev").mkdir()
        (vault / "config").mkdir()
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong-path",
            search_roots=[tmp_path],
            skills_dir=tmp_path / "nonexistent-skills",
        )
        assert result == vault


class TestOneShotCache:
    def test_cached_after_first_run(self, tmp_path):
        result1 = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong",
            search_roots=[tmp_path],
        )
        vault = tmp_path / "late-vault"
        vault.mkdir()
        (vault / ".augur-vault").write_text("project: Test\n")
        result2 = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong",
            search_roots=[tmp_path],
        )
        assert result1 == result2  # both None — cached


class TestScanBudget:
    def test_stops_after_max_candidates(self, tmp_path):
        for i in range(200):
            (tmp_path / f"dir-{i:04d}").mkdir()
        (tmp_path / "dir-0199" / ".augur-vault").write_text("project: Test\n")
        result = path_discovery.discover_path(
            "vault",
            configured=tmp_path / "wrong",
            search_roots=[tmp_path],
            max_candidates=50,
        )
        assert result is None


class TestCreateMarker:
    def test_creates_vault_marker(self, tmp_path):
        path_discovery.create_marker("vault", tmp_path)
        marker = tmp_path / ".augur-vault"
        assert marker.exists()
        content = marker.read_text()
        assert "project:" in content

    def test_creates_docs_marker(self, tmp_path):
        path_discovery.create_marker("documents", tmp_path)
        marker = tmp_path / ".augur-docs"
        assert marker.exists()


class TestUpdateProjectYaml:
    """Test atomic write to project.yaml."""

    def test_updates_vault_path(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\npaths:\n  vault: /old/path\n")
        with (
            patch("src.config.paths.get_project_root", return_value=tmp_path),
            patch("src.config.paths.invalidate_project_cache"),
        ):
            path_discovery.update_project_yaml("vault", Path("/new/path"))
        import yaml

        data = yaml.safe_load(project_yaml.read_text())
        assert data["paths"]["vault"] == "/new/path"

    def test_creates_paths_block_if_missing(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\nport: 3000\n")
        with (
            patch("src.config.paths.get_project_root", return_value=tmp_path),
            patch("src.config.paths.invalidate_project_cache"),
        ):
            path_discovery.update_project_yaml("vault", Path("/new/vault"))
        import yaml

        data = yaml.safe_load(project_yaml.read_text())
        assert data["paths"]["vault"] == "/new/vault"

    def test_atomic_write_no_partial_file_on_error(self, tmp_path):
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("name: Test\n")
        original = project_yaml.read_text()
        with (
            patch("src.config.paths.get_project_root", return_value=tmp_path),
            patch("yaml.safe_dump", side_effect=RuntimeError("write error")),
        ):
            with pytest.raises(RuntimeError):
                path_discovery.update_project_yaml("vault", Path("/fail"))
        assert project_yaml.read_text() == original  # unchanged


class TestPromptUpdate:
    """Test interactive vs non-interactive prompt behavior."""

    def test_non_interactive_returns_false(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is False

    def test_interactive_yes(self):
        with patch("sys.stdin") as mock_stdin, patch("builtins.input", return_value="y"):
            mock_stdin.isatty.return_value = True
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is True

    def test_interactive_no(self):
        with patch("sys.stdin") as mock_stdin, patch("builtins.input", return_value="n"):
            mock_stdin.isatty.return_value = True
            result = path_discovery.prompt_update("vault", Path("/old"), Path("/new"))
        assert result is False


class TestScanTimeout:
    """Test timeout budget."""

    def test_stops_after_timeout(self, tmp_path):
        for i in range(10):
            (tmp_path / f"dir-{i}").mkdir()
        (tmp_path / "dir-9" / ".augur-vault").write_text("project: Test\n")
        call_count = 0

        def mock_monotonic():
            nonlocal call_count
            call_count += 1
            return float(call_count * 10)

        with patch("src.config.path_discovery.time") as mock_time:
            mock_time.monotonic = mock_monotonic
            result = path_discovery.discover_path(
                "vault",
                configured=tmp_path / "wrong",
                search_roots=[tmp_path],
                timeout_secs=5.0,
            )
        assert result is None
