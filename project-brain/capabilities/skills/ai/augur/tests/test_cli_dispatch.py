"""Tests for CLI profile auto-injection and airplane mode CLI dispatch."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.ai.config import load_llm_config, resolve_llm_profile, LLMConfig, LLMProfile


class TestCliProfileInjection:
    def _load_with_mock_cli(self, cli_path: str | None, existing_active: str | None = None):
        raw = {
            "active_profile": existing_active,
            "profiles": {
                "local": {"provider": "openai_compatible", "base_url": "http://localhost:11434/v1", "model": "qwen3.5:latest"},
            },
        }
        with patch("src.lib.ai.config._load_from_files", return_value=(raw, Path("/fake/llm.yaml"))):
            with patch("src.lib.ai.cli_detect.detect_cli", return_value=cli_path):
                cmd = f"{cli_path} --print" if cli_path and "claude" in cli_path else None
                with patch("src.lib.ai.cli_detect.cli_command", return_value=cmd):
                    return load_llm_config()

    def test_injects_cli_profile_when_detected(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude")
        assert "cli" in config.profiles
        assert config.profiles["cli"].provider == "command"
        assert config.profiles["cli"].command == "/usr/local/bin/claude --print"

    def test_sets_active_profile_to_cli_when_no_explicit(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude")
        assert config.active_profile == "cli"

    def test_preserves_explicit_active_profile(self):
        config = self._load_with_mock_cli("/usr/local/bin/claude", existing_active="local")
        assert config.active_profile == "local"
        assert "cli" in config.profiles

    def test_no_cli_detected_no_injection(self):
        config = self._load_with_mock_cli(None)
        assert "cli" not in config.profiles

    def test_no_cli_detected_keeps_existing_active(self):
        config = self._load_with_mock_cli(None, existing_active="local")
        assert config.active_profile == "local"


class TestAirplaneModeCliDispatch:
    def _make_config(self) -> LLMConfig:
        return LLMConfig(
            active_profile="cli",
            profiles={
                "cli": LLMProfile(name="cli", provider="command", command="claude --print"),
                "local": LLMProfile(name="local", provider="openai_compatible", base_url="http://localhost:11434/v1", model="qwen3.5:latest"),
            },
        )

    def test_airplane_returns_ollama_cli_when_available(self):
        config = self._make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", side_effect=lambda n: "/usr/local/bin/ollama" if n == "ollama" else None):
                profile = resolve_llm_profile(config)
        assert profile.provider == "command"
        assert "ollama run" in profile.command

    def test_airplane_falls_back_to_http_local_when_no_ollama_cli(self):
        config = self._make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", return_value=None):
                profile = resolve_llm_profile(config)
        assert profile.name == "local"

    def test_airplane_off_uses_cli_profile(self):
        config = self._make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=False):
            profile = resolve_llm_profile(config)
        assert profile.name == "cli"
