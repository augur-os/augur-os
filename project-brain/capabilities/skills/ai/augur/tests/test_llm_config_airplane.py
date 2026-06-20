"""Tests for airplane mode override in resolve_llm_profile."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.lib.ai.config import LLMConfig, LLMProfile, resolve_llm_profile


def _make_config() -> LLMConfig:
    return LLMConfig(
        active_profile="remote",
        profiles={
            "local": LLMProfile(name="local", provider="openai_compatible", base_url="http://localhost:11434/v1", model="qwen3.5:9b"),
            "remote": LLMProfile(name="remote", provider="openai_compatible", base_url="https://api.groq.com/openai/v1", model="llama-3.3-70b"),
        },
        tasks={"contextualizer": "remote"},
    )


class TestAirplaneModeOverride:
    def test_airplane_off_uses_normal_resolution(self):
        config = _make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=False):
            profile = resolve_llm_profile(config, task="contextualizer")
        assert profile.name == "remote"

    def test_airplane_on_forces_local_profile(self):
        config = _make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", return_value=None):
                profile = resolve_llm_profile(config)
        assert profile.name == "local"

    def test_airplane_on_overrides_task_routing(self):
        config = _make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", return_value=None):
                profile = resolve_llm_profile(config, task="contextualizer")
        assert profile.name == "local"

    def test_explicit_name_overrides_airplane(self):
        config = _make_config()
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            profile = resolve_llm_profile(config, name="remote")
        assert profile.name == "remote"

    def test_airplane_on_no_local_profile_falls_through(self):
        config = LLMConfig(
            active_profile="remote",
            profiles={
                "remote": LLMProfile(name="remote", provider="openai_compatible", base_url="https://api.groq.com", model="m"),
            },
        )
        with patch("src.lib.ai.config._is_airplane_mode", return_value=True):
            with patch("shutil.which", return_value=None):
                profile = resolve_llm_profile(config)
        assert profile.name == "remote"

    def test_airplane_env_var(self):
        import src.lib.ai.config as _cfg
        _cfg._airplane_cache = None  # clear TTL cache
        from src.lib.ai.config import _is_airplane_mode
        with patch.dict(os.environ, {"AUGUR_AIRPLANE_MODE": "1"}):
            assert _is_airplane_mode() is True

    def test_airplane_env_var_off(self):
        import src.lib.ai.config as _cfg
        _cfg._airplane_cache = None  # clear TTL cache
        from src.lib.ai.config import _is_airplane_mode
        env = {k: v for k, v in os.environ.items() if k != "AUGUR_AIRPLANE_MODE"}
        with patch.dict(os.environ, env, clear=True):
            with patch("src.config.paths.get_config_dir", side_effect=RuntimeError("no config")):
                assert _is_airplane_mode() is False
