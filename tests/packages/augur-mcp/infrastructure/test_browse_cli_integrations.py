"""
Tests for CLI integration features in browse.py (ADR-441).

Covers: frontmatter parsing, CLI status checks, version parsing,
config checks, status derivation, cache invalidation, MCP tool validation.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_browse_cli_integrations.py -v
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp.augur_framework.tools.infrastructure.browse import (
    _check_cli_status,
    cli_install_impl,
    cli_status_impl,
    get_skill_cli_help_impl,
    list_integrations_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear module-level caches before each test."""
    from src.mcp.augur_framework.tools.infrastructure import browse as browse_mod

    browse_mod._cli_status_cache.clear()
    browse_mod._cli_status_ts.clear()
    browse_mod._cli_registry.clear()
    browse_mod._cli_registry_ts = 0.0
    yield
    browse_mod._cli_status_cache.clear()
    browse_mod._cli_status_ts.clear()
    browse_mod._cli_registry.clear()
    browse_mod._cli_registry_ts = 0.0


@pytest.fixture
def skill_dir(tmp_path: Path):
    """Create a skill directory with x-augur-cli-integrations frontmatter."""
    skill = tmp_path / "skills" / "test-skill"
    skill.mkdir(parents=True)
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: test-skill\n"
        "description: Test skill with CLI integrations\n"
        "x-augur-hub: life\n"
        "x-augur-cli-integrations:\n"
        "  - name: testcli\n"
        '    install: "npm install -g testcli"\n'
        '    version_cmd: "testcli --version"\n'
        "  - name: othercli\n"
        '    install: "pip install othercli"\n'
        '    version_cmd: "othercli -V"\n'
        "    requires_config: true\n"
        '    config_check: "othercli auth status"\n'
        '    homepage: "https://example.com"\n'
        "x-augur-mcp-tools:\n"
        "- test-tool-1\n"
        "- test-tool-2\n"
        "---\n"
        "\n"
        "# Test Skill\n"
    )
    return tmp_path


@pytest.fixture
def builtin_skill_dir(tmp_path: Path):
    """Create a skill with built-in CLI tools."""
    skill = tmp_path / "skills" / "builtin-skill"
    skill.mkdir(parents=True)
    skill_md = skill / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: builtin-skill\n"
        "description: Skill with built-in tools\n"
        "x-augur-hub: command\n"
        "x-augur-cli-integrations:\n"
        "  - name: osascript\n"
        '    install: "Built-in macOS utility"\n'
        "---\n"
    )
    return tmp_path


# =============================================================================
# Test 1: Frontmatter parsing
# =============================================================================


class TestFrontmatterParsing:
    """ADR-441 Unit Test #1: Frontmatter with x-augur-cli-integrations parsed correctly."""

    @pytest.mark.asyncio
    async def test_skill_with_cli_integrations_discovered(self, skill_dir):
        """Skills with x-augur-cli-integrations in frontmatter appear in results."""
        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=skill_dir),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[skill_dir / "skills"],
            ),
            patch("shutil.which", return_value=None),
        ):
            result = json.loads(await list_integrations_impl())
            assert result["count"] == 1
            item = result["items"][0]
            assert item["title"] == "Test Skill"
            assert len(item["cli_tools"]) == 2
            assert item["cli_tools"][0]["name"] == "testcli"
            assert item["cli_tools"][1]["name"] == "othercli"

    @pytest.mark.asyncio
    async def test_skill_without_cli_integrations_excluded(self, tmp_path):
        """Skills without x-augur-cli-integrations are not discovered."""
        skill = tmp_path / "skills" / "plain-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: plain-skill\ndescription: No CLI\nx-augur-hub: dev\n---\n")
        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=tmp_path),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[tmp_path / "skills"],
            ),
        ):
            result = json.loads(await list_integrations_impl())
            assert result["count"] == 0


# =============================================================================
# Test 2: which check
# =============================================================================


class TestInstalledStatus:
    """ADR-441 Unit Test #2: which check returns correct installed status."""

    def test_installed_when_which_returns_path(self):
        cli_def = {"install": "npm install -g foo", "version_cmd": "foo --version"}
        with (
            patch("shutil.which", return_value="/usr/local/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="1.2.3\n", stderr="", returncode=0)
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["installed"] is True

    def test_not_installed_when_which_returns_none(self):
        cli_def = {"install": "npm install -g foo"}
        with patch("shutil.which", return_value=None):
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["installed"] is False
            assert status["version"] is None


# =============================================================================
# Test 3: Version parsing
# =============================================================================


class TestVersionParsing:
    """ADR-441 Unit Test #3: Version parsing extracts semver from multi-line output."""

    def test_extracts_semver_from_single_line(self):
        cli_def = {"version_cmd": "foo --version"}
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="2.5.1\n", stderr="", returncode=0)
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["version"] == "2.5.1"

    def test_extracts_semver_from_multi_line(self):
        cli_def = {"version_cmd": "foo --version"}
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="foo version 3.14.159\nCopyright 2024\n", stderr="", returncode=0)
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["version"] == "3.14.159"

    def test_falls_back_to_first_line_when_no_semver(self):
        cli_def = {"version_cmd": "foo --version"}
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="foo (no version)\n", stderr="", returncode=0)
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["version"] == "foo (no version)"


# =============================================================================
# Test 4: Config check
# =============================================================================


class TestConfigCheck:
    """ADR-441 Unit Test #4: Config check exit 0 → true, non-zero → false, timeout → null."""

    def _make_cli_def(self):
        return {
            "version_cmd": "foo --version",
            "requires_config": True,
            "config_check": "foo auth status",
        }

    def test_configured_on_exit_zero(self):
        cli_def = self._make_cli_def()
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            # First call = version check, second call = config check
            mock_run.side_effect = [
                MagicMock(stdout="1.0.0", stderr="", returncode=0),
                MagicMock(returncode=0),
            ]
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["configured"] is True

    def test_not_configured_on_non_zero_exit(self):
        cli_def = self._make_cli_def()
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(stdout="1.0.0", stderr="", returncode=0),
                MagicMock(returncode=1),
            ]
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["configured"] is False

    def test_configured_null_on_timeout(self):
        import subprocess

        cli_def = self._make_cli_def()
        with (
            patch("shutil.which", return_value="/usr/bin/foo"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(stdout="1.0.0", stderr="", returncode=0),
                subprocess.TimeoutExpired(cmd="foo auth status", timeout=3),
            ]
            status = _check_cli_status("foo", cli_def, bypass_cache=True)
            assert status["configured"] is None


# =============================================================================
# Test 5: Status derivation
# =============================================================================


class TestStatusDerivation:
    """ADR-441 Unit Test #5: Status derivation priority: missing > needs_config > ready."""

    @pytest.mark.asyncio
    async def test_status_missing_when_cli_not_installed(self, skill_dir):
        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=skill_dir),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[skill_dir / "skills"],
            ),
            patch("shutil.which", return_value=None),
        ):
            result = json.loads(await list_integrations_impl())
            assert result["items"][0]["status"] == "missing"

    @pytest.mark.asyncio
    async def test_status_ready_when_all_installed(self, skill_dir):
        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=skill_dir),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[skill_dir / "skills"],
            ),
            patch("shutil.which", return_value="/usr/bin/testcli"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="1.0.0", stderr="", returncode=0)
            result = json.loads(await list_integrations_impl())
            # othercli requires_config but config_check returns 0 → ready
            assert result["items"][0]["status"] == "ready"


# =============================================================================
# Test 6: cli-install rejects unknown CLI name
# =============================================================================


class TestCliInstallValidation:
    """ADR-441 Unit Test #6: cli-install rejects unknown CLI name."""

    @pytest.mark.asyncio
    async def test_rejects_unknown_cli(self):
        with patch("src.mcp.augur_framework.tools.infrastructure.browse.cli._build_cli_registry", return_value={}):
            result = json.loads(await cli_install_impl("nonexistent"))
            assert result["success"] is False
            assert "Unknown CLI tool" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_builtin_cli(self):
        registry = {
            "osascript": {
                "install": "Built-in macOS utility",
                "version_cmd": "osascript -e 'return version of AppleScript'",
                "skill": "apple",
                "skill_md": "/test/SKILL.md",
            }
        }
        with patch(
            "src.mcp.augur_framework.tools.infrastructure.browse.cli._build_cli_registry", return_value=registry
        ):
            result = json.loads(await cli_install_impl("osascript"))
            assert result["success"] is False
            assert "built-in" in result["error"].lower()


# =============================================================================
# Test 7: cli-status bypasses cache
# =============================================================================


class TestCliStatusBypassCache:
    """ADR-441 Unit Test #7: cli-status bypasses cache."""

    @pytest.mark.asyncio
    async def test_cli_status_returns_fresh_data(self):
        from src.mcp.augur_framework.tools.infrastructure import browse as browse_mod

        registry = {
            "testcli": {
                "install": "npm install -g testcli",
                "version_cmd": "testcli --version",
                "requires_config": False,
                "config_check": "",
                "homepage": "",
                "skill": "test",
                "skill_md": "/test/SKILL.md",
            }
        }
        # Seed cache with stale data
        browse_mod._cli_status_cache["testcli"] = {"installed": False, "version": None}
        browse_mod._cli_status_ts["testcli"] = time.time()

        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli._build_cli_registry", return_value=registry),
            patch("shutil.which", return_value="/usr/bin/testcli"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="2.0.0", stderr="", returncode=0)
            result = json.loads(await cli_status_impl("testcli"))
            # Should bypass cache and return fresh data
            assert result["installed"] is True
            assert result["version"] == "2.0.0"


# =============================================================================
# Test 8: Cache invalidated after install
# =============================================================================


class TestCacheInvalidation:
    """ADR-441 Unit Test #8: Cache invalidated after successful install."""

    @pytest.mark.asyncio
    async def test_cache_cleared_after_install(self):
        from src.mcp.augur_framework.tools.infrastructure import browse as browse_mod

        registry = {
            "testcli": {
                "install": "npm install -g testcli",
                "version_cmd": "testcli --version",
                "requires_config": False,
                "config_check": "",
                "homepage": "",
                "skill": "test",
                "skill_md": "/test/SKILL.md",
            }
        }
        # Seed cache
        browse_mod._cli_status_cache["testcli"] = {"installed": False}
        browse_mod._cli_status_ts["testcli"] = time.time()

        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli._build_cli_registry", return_value=registry),
            patch("subprocess.run") as mock_run,
            patch("shutil.which", return_value="/usr/bin/testcli"),
        ):
            mock_run.return_value = MagicMock(stdout="installed!", stderr="", returncode=0)
            result = json.loads(await cli_install_impl("testcli"))
            assert result["success"] is True
            # Cache entry should have been cleared and repopulated
            assert browse_mod._cli_status_cache["testcli"]["installed"] is True


class TestSkillCliHelp:
    """Skill CLI help returns dashboard-ready markdown for IntegrationTab."""

    def test_get_skill_cli_help_reads_command_files(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skill = skills_dir / "knowledge"
        commands_dir = skill / "commands"
        commands_dir.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\n" "name: knowledge\n" "x-augur-tab: Knowledge\n" "---\n" "\n" "# Knowledge\n",
            encoding="utf-8",
        )
        (commands_dir / "refresh.md").write_text(
            "---\n"
            "id: refresh\n"
            "label: Refresh\n"
            "description: Refresh knowledge sources\n"
            "---\n"
            "\n"
            "Refreshes indexed knowledge.\n",
            encoding="utf-8",
        )
        vault_dir = tmp_path / "vault"
        config_dir = vault_dir / "config"
        (config_dir / "ai").mkdir(parents=True)
        (config_dir / "ai" / "cli_agents.yaml").write_text(
            "agents:\n" "  claude:\n" "    cmd: [\"claude\"]\n",
            encoding="utf-8",
        )

        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=tmp_path),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[skills_dir],
            ),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_vault_config_dir", return_value=config_dir
            ),
        ):
            result = json.loads(get_skill_cli_help_impl("knowledge"))

        assert result["success"] is True
        assert result["skill_id"] == "knowledge"
        assert result["default_cli"] == "claude"
        assert result["command_count"] == 1
        assert result["commands"][0]["command"] == "/refresh"
        assert "Refresh knowledge sources" in result["markdown"]

    def test_get_skill_cli_help_reports_unknown_skill(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        vault_dir = tmp_path / "vault"
        config_dir = vault_dir / "config"
        (config_dir / "ai").mkdir(parents=True)
        (config_dir / "ai" / "cli_agents.yaml").write_text(
            "agents:\n" "  codex:\n" "    cmd: [\"codex\"]\n",
            encoding="utf-8",
        )

        with (
            patch("src.mcp.augur_framework.tools.infrastructure.browse.cli.get_project_root", return_value=tmp_path),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_all_client_skill_dirs",
                return_value=[skills_dir],
            ),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.browse.cli.get_vault_config_dir", return_value=config_dir
            ),
        ):
            result = json.loads(get_skill_cli_help_impl("missing"))

        assert result["success"] is False
        assert result["default_cli"] == "codex"
        assert "Skill not found" in result["error"]
