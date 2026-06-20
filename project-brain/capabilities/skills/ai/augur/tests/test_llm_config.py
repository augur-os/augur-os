"""Tests for augur/lib/config.py — LLM configuration loading and resolution.

Validates profile loading from YAML files and environment variables,
profile resolution by name/context/task, and edge cases like missing config.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
AI_BRIDGE_AUGUR = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AI_BRIDGE_AUGUR) not in sys.path:
    sys.path.insert(0, str(AI_BRIDGE_AUGUR))

from src.lib.ai.config import (
    LLMConfig,
    LLMProfile,
    load_llm_config,
    resolve_llm_profile,
    _coerce_int,
    _coerce_float,
)


# ---------------------------------------------------------------------------
# _coerce_int / _coerce_float
# ---------------------------------------------------------------------------


class TestCoerce:
    def test_coerce_int_valid(self):
        assert _coerce_int("42", 10) == 42

    def test_coerce_int_invalid(self):
        assert _coerce_int("abc", 10) == 10

    def test_coerce_int_zero_returns_default(self):
        assert _coerce_int(0, 10) == 10

    def test_coerce_int_negative_returns_default(self):
        assert _coerce_int(-5, 10) == 10

    def test_coerce_float_valid(self):
        assert _coerce_float("0.5") == 0.5

    def test_coerce_float_none(self):
        assert _coerce_float(None) is None

    def test_coerce_float_invalid(self):
        assert _coerce_float("abc") is None


# ---------------------------------------------------------------------------
# load_llm_config
# ---------------------------------------------------------------------------


class TestLoadLLMConfig:
    def test_empty_dir_returns_empty_config(self, tmp_path: Path):
        with patch("src.lib.ai.cli_detect.detect_cli", return_value=None):
            config = load_llm_config(user_data_base=tmp_path)
        assert config.active_profile is None
        assert config.profiles == {}

    def test_loads_from_llm_yaml(self, tmp_path: Path):
        yaml_content = """
active_profile: local
profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llama3
    timeout_s: 30
"""
        (tmp_path / "llm.yaml").write_text(yaml_content, encoding="utf-8")
        config = load_llm_config(user_data_base=tmp_path)
        assert config.active_profile == "local"
        assert "local" in config.profiles
        assert config.profiles["local"].base_url == "http://localhost:11434/v1"
        assert config.profiles["local"].timeout_s == 30

    def test_loads_from_config_yaml_llm_section(self, tmp_path: Path):
        yaml_content = """
llm:
  active_profile: remote
  profiles:
    remote:
      provider: openai_compatible
      base_url: https://api.openai.com/v1
      model: gpt-4
"""
        (tmp_path / "config.yaml").write_text(yaml_content, encoding="utf-8")
        config = load_llm_config(user_data_base=tmp_path)
        assert config.active_profile == "remote"
        assert "remote" in config.profiles

    def test_env_creates_inline_profile(self, tmp_path: Path):
        env = {
            "AUGUR_LLM_BASE_URL": "http://localhost:8080",
            "AUGUR_LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_llm_config(user_data_base=tmp_path)
            assert "env" in config.profiles
            assert config.profiles["env"].base_url == "http://localhost:8080"
            assert config.profiles["env"].model == "test-model"

    def test_env_profile_overrides_yaml(self, tmp_path: Path):
        yaml_content = """
active_profile: local
profiles:
  local:
    provider: openai_compatible
    model: local-model
  remote:
    provider: openai_compatible
    model: remote-model
"""
        (tmp_path / "llm.yaml").write_text(yaml_content, encoding="utf-8")
        with patch.dict(os.environ, {"AUGUR_LLM_PROFILE": "remote"}, clear=False):
            config = load_llm_config(user_data_base=tmp_path)
            assert config.active_profile == "remote"

    def test_invalid_provider_skipped(self, tmp_path: Path):
        yaml_content = """
profiles:
  bad:
    provider: invalid_provider
    model: test
"""
        (tmp_path / "llm.yaml").write_text(yaml_content, encoding="utf-8")
        config = load_llm_config(user_data_base=tmp_path)
        assert "bad" not in config.profiles

    def test_reads_system_llm_from_active_worktree_root(self, tmp_path: Path):
        main_root = tmp_path / "main"
        (main_root / "config" / "system").mkdir(parents=True)
        (main_root / "project.yaml").write_text("name: Main\n", encoding="utf-8")
        (main_root / ".git").mkdir()
        (main_root / "config" / "system" / "llm.yaml").write_text(
            """
active_profile: main
profiles:
  main:
    provider: openai_compatible
    model: main-model
""",
            encoding="utf-8",
        )

        worktree_root = tmp_path / "worktrees" / "feature"
        (worktree_root / "config" / "system").mkdir(parents=True)
        (worktree_root / "project.yaml").write_text("name: Worktree\n", encoding="utf-8")
        (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")
        (worktree_root / "config" / "system" / "llm.yaml").write_text(
            """
active_profile: local
profiles:
  local:
    provider: openai_compatible
    model: worktree-model
""",
            encoding="utf-8",
        )

        nested_cwd = worktree_root / "project-brain" / "capabilities" / "skills" / "rag"
        nested_cwd.mkdir(parents=True)

        with patch("src.config.paths._project_root_from_file", return_value=main_root), \
             patch("pathlib.Path.cwd", return_value=nested_cwd), \
             patch("src.lib.ai.cli_detect.detect_cli", return_value=None), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUGUR_ROOT", None)
            os.environ.pop("AUGUR_CORE", None)
            os.environ.pop("AUGUR_REPO", None)
            config = load_llm_config()

        assert config.active_profile == "local"
        assert config.profiles["local"].model == "worktree-model"
        assert config.source_path == worktree_root / "config" / "system" / "llm.yaml"

    def test_stale_augur_root_env_does_not_beat_current_worktree(self, tmp_path: Path):
        main_root = tmp_path / "main"
        (main_root / "config" / "system").mkdir(parents=True)
        (main_root / "project.yaml").write_text("name: Main\n", encoding="utf-8")
        (main_root / ".git").mkdir()
        (main_root / "config" / "system" / "llm.yaml").write_text(
            """
active_profile: main
profiles:
  main:
    provider: openai_compatible
    model: main-model
""",
            encoding="utf-8",
        )

        worktree_root = tmp_path / "worktrees" / "feature"
        (worktree_root / "config" / "system").mkdir(parents=True)
        (worktree_root / "project.yaml").write_text("name: Worktree\n", encoding="utf-8")
        (worktree_root / ".git").write_text("gitdir: /tmp/fake\n", encoding="utf-8")
        (worktree_root / "config" / "system" / "llm.yaml").write_text(
            """
active_profile: local
profiles:
  local:
    provider: openai_compatible
    model: worktree-model
""",
            encoding="utf-8",
        )

        nested_cwd = worktree_root / "project-brain" / "capabilities" / "skills" / "rag"
        nested_cwd.mkdir(parents=True)

        with patch("src.config.paths._project_root_from_file", return_value=main_root), \
             patch("pathlib.Path.cwd", return_value=nested_cwd), \
             patch("src.lib.ai.cli_detect.detect_cli", return_value=None), \
             patch.dict(os.environ, {"AUGUR_ROOT": str(main_root)}, clear=False):
            config = load_llm_config()

        assert config.active_profile == "local"
        assert config.source_path == worktree_root / "config" / "system" / "llm.yaml"


# ---------------------------------------------------------------------------
# resolve_llm_profile
# ---------------------------------------------------------------------------


class TestResolveLLMProfile:
    def _config_with_profiles(self, **kwargs) -> LLMConfig:
        profiles = {
            name: LLMProfile(name=name, provider="openai_compatible", model=name)
            for name in kwargs
        }
        return LLMConfig(
            active_profile=kwargs.get("active"),
            profiles=profiles,
        )

    def test_explicit_name(self):
        config = LLMConfig(
            active_profile="default",
            profiles={
                "default": LLMProfile(name="default", provider="openai_compatible"),
                "fast": LLMProfile(name="fast", provider="openai_compatible"),
            },
        )
        result = resolve_llm_profile(config, name="fast")
        assert result.name == "fast"

    def test_active_profile(self):
        config = LLMConfig(
            active_profile="primary",
            profiles={
                "primary": LLMProfile(name="primary", provider="openai_compatible"),
            },
        )
        result = resolve_llm_profile(config)
        assert result.name == "primary"

    def test_env_fallback(self):
        config = LLMConfig(
            active_profile=None,
            profiles={
                "env": LLMProfile(name="env", provider="openai_compatible"),
            },
        )
        result = resolve_llm_profile(config)
        assert result.name == "env"

    def test_default_fallback(self):
        config = LLMConfig(
            active_profile=None,
            profiles={
                "default": LLMProfile(name="default", provider="openai_compatible"),
            },
        )
        result = resolve_llm_profile(config)
        assert result.name == "default"

    def test_no_profiles_raises(self):
        config = LLMConfig(active_profile=None, profiles={})
        with pytest.raises(RuntimeError):
            resolve_llm_profile(config)

    def test_task_mapping(self):
        config = LLMConfig(
            active_profile="default",
            profiles={
                "default": LLMProfile(name="default", provider="openai_compatible"),
                "fast": LLMProfile(name="fast", provider="openai_compatible"),
            },
            tasks={"summarize": "fast"},
        )
        result = resolve_llm_profile(config, task="summarize")
        assert result.name == "fast"

    def test_context_layer_override(self):
        config = LLMConfig(
            active_profile="default",
            profiles={
                "default": LLMProfile(name="default", provider="openai_compatible"),
                "factory_profile": LLMProfile(name="factory_profile", provider="openai_compatible"),
            },
            overrides={
                "layers": {"factory": {"active_profile": "factory_profile"}},
                "components": {},
            },
        )
        result = resolve_llm_profile(config, context="factory/planner")
        assert result.name == "factory_profile"

    def test_context_component_override_beats_layer(self):
        config = LLMConfig(
            active_profile="default",
            profiles={
                "default": LLMProfile(name="default", provider="openai_compatible"),
                "layer_p": LLMProfile(name="layer_p", provider="openai_compatible"),
                "comp_p": LLMProfile(name="comp_p", provider="openai_compatible"),
            },
            overrides={
                "layers": {"factory": {"active_profile": "layer_p"}},
                "components": {"factory/planner": {"active_profile": "comp_p"}},
            },
        )
        result = resolve_llm_profile(config, context="factory/planner")
        assert result.name == "comp_p"
