"""Tests for llm_retry resolve_cli reading from llm.yaml profiles."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib import llm_retry
from src.lib.llm_retry import _get_cli_candidates, _resolve_cli_from_llm_config, resolve_cli


class TestResolveCLIFromLLMConfig:
    def test_returns_command_for_command_provider(self):
        mock_profile = MagicMock()
        mock_profile.provider = "command"
        mock_profile.command = "claude --print"

        with (
            patch("src.lib.llm_retry._find_project_root", return_value=Path("/fake")),
            patch("src.lib.ai.load_llm_config"),
            patch("src.lib.ai.resolve_llm_profile", return_value=mock_profile),
        ):
            result = _resolve_cli_from_llm_config()

        assert result == "claude --print"

    def test_returns_none_for_non_command_provider(self):
        mock_profile = MagicMock()
        mock_profile.provider = "openai_compatible"
        mock_profile.command = None

        with (
            patch("src.lib.llm_retry._find_project_root", return_value=Path("/fake")),
            patch("src.lib.ai.load_llm_config"),
            patch("src.lib.ai.resolve_llm_profile", return_value=mock_profile),
        ):
            result = _resolve_cli_from_llm_config()

        assert result is None

    def test_returns_none_on_import_error(self):
        with patch("src.lib.llm_retry._find_project_root", return_value=Path("/fake")):
            # If src.lib.ai can't be imported, returns None
            with patch.dict(sys.modules, {"src.lib.ai": None}):
                result = _resolve_cli_from_llm_config()
        assert result is None

    def test_returns_none_when_no_project_root(self):
        with patch("src.lib.llm_retry._find_project_root", return_value=None):
            result = _resolve_cli_from_llm_config()
        assert result is None


class TestResolveCLIExplicitSetting:
    def test_explicit_cli_setting_still_works(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            result = resolve_cli("claude")
        assert result == "/usr/local/bin/claude"

    def test_explicit_cli_setting_not_found_raises(self):
        import pytest

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="not found on PATH"):
                resolve_cli("nonexistent-cli")


class TestResolveCLICandidates:
    def test_cli_candidates_read_from_vault_config_ai(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        config_dir = tmp_path / "vault" / "config"
        (config_dir / "ai").mkdir(parents=True)
        (config_dir / "ai" / "cli_agents.yaml").write_text(
            "agents:\n"
            "  codex:\n"
            "    cmd: [\"codex\"]\n"
            "  claude:\n"
            "    cmd: [\"claude\"]\n"
            "  shell-only:\n"
            "    shell: true\n",
            encoding="utf-8",
        )

        llm_retry._CLI_CANDIDATES = None
        try:
            with (
                patch("src.lib.llm_retry._find_project_root", return_value=root),
                patch("src.config.paths.get_vault_config_dir", return_value=config_dir),
            ):
                result = _get_cli_candidates()
        finally:
            llm_retry._CLI_CANDIDATES = None

        assert result == ["codex", "claude"]
