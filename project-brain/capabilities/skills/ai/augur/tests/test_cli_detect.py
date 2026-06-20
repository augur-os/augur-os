"""Tests for CLI auto-detection."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.ai.cli_detect import cli_command, detect_cli, _get_candidate_clis


class TestDetectCli:
    def test_finds_claude_on_path(self):
        with patch("shutil.which", side_effect=lambda name: "/usr/local/bin/claude" if name == "claude" else None):
            with patch("src.lib.ai.cli_detect._get_candidate_clis", return_value=["claude", "codex"]):
                result = detect_cli()
        assert result == "/usr/local/bin/claude"

    def test_cli_agents_order_takes_priority(self):
        with patch("shutil.which", side_effect=lambda name: f"/usr/local/bin/{name}"):
            with patch("src.lib.ai.cli_detect._get_candidate_clis", return_value=["codex", "claude"]):
                result = detect_cli()
        assert result == "/usr/local/bin/codex"

    def test_returns_none_when_no_cli_found(self):
        with patch("shutil.which", return_value=None):
            with patch("src.lib.ai.cli_detect._get_candidate_clis", return_value=["claude", "codex"]):
                result = detect_cli()
        assert result is None

    def test_returns_none_on_exception(self):
        with patch("src.lib.ai.cli_detect._get_candidate_clis", side_effect=RuntimeError("boom")):
            result = detect_cli()
        assert result is None

    def test_candidate_clis_read_from_vault_config_ai(self, tmp_path):
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

        with patch("src.config.paths.get_vault_config_dir", return_value=config_dir):
            result = _get_candidate_clis()

        assert result == ["codex", "claude"]


class TestCliCommand:
    def test_claude_uses_print_flag(self):
        assert cli_command("/usr/local/bin/claude") == "/usr/local/bin/claude --print"

    def test_codex_uses_exec_subcommand(self):
        assert cli_command("/usr/local/bin/codex") == "/usr/local/bin/codex exec"

    def test_ollama_uses_run_with_model(self):
        result = cli_command("/usr/local/bin/ollama", model="qwen3.5:latest")
        assert result == "/usr/local/bin/ollama run qwen3.5:latest"

    def test_ollama_default_model(self):
        result = cli_command("/usr/local/bin/ollama")
        assert "ollama run" in result

    def test_unknown_cli_uses_bare_path(self):
        assert cli_command("/usr/local/bin/newcli") == "/usr/local/bin/newcli"
