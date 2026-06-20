"""Tests for the canonical config/system/llm.yaml schema."""

from __future__ import annotations

import pytest

from src.config.schemas.llm_schema import (
    OPTIONAL_KEYS,
    REQUIRED_KEYS,
    REQUIRED_PROFILE_FIELDS,
    LlmConfig,
    LlmProfile,
    LlmSchemaError,
    validate_llm_config,
)
from src.config.paths import get_project_root
from src.config.system_config import llm_config_raw


def _valid_config() -> dict:
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
                "timeout_s": 120,
            },
            "remote": {
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "model": "remote-model",
                "api_key_env": "REMOTE_API_KEY",
            },
        },
        "tasks": {"document_ocr": "local"},
    }


def test_valid_config_returns_dataclass() -> None:
    cfg = validate_llm_config(_valid_config())

    assert isinstance(cfg, LlmConfig)
    assert cfg.active_profile == "local"
    assert isinstance(cfg.profiles["local"], LlmProfile)
    assert cfg.profiles["remote"].api_key_env == "REMOTE_API_KEY"
    assert cfg.tasks == {"document_ocr": "local"}


def test_top_level_must_be_mapping() -> None:
    with pytest.raises(LlmSchemaError, match="top-level"):
        validate_llm_config("not-a-dict")


def test_flat_single_vendor_shape_is_rejected() -> None:
    with pytest.raises(LlmSchemaError, match="unknown top-level"):
        validate_llm_config({"model": "claude-opus-4", "provider": "anthropic"})


def test_missing_required_keys_are_rejected() -> None:
    raw = _valid_config()
    del raw["profiles"]

    with pytest.raises(LlmSchemaError, match="profiles"):
        validate_llm_config(raw)


def test_empty_profiles_are_rejected() -> None:
    raw = _valid_config()
    raw["profiles"] = {}

    with pytest.raises(LlmSchemaError, match="non-empty mapping"):
        validate_llm_config(raw)


def test_profile_missing_required_field_is_rejected() -> None:
    raw = _valid_config()
    del raw["profiles"]["local"]["model"]

    with pytest.raises(LlmSchemaError, match="model"):
        validate_llm_config(raw)


def test_active_profile_must_reference_profile() -> None:
    raw = _valid_config()
    raw["active_profile"] = "ghost"

    with pytest.raises(LlmSchemaError, match="active_profile.*ghost"):
        validate_llm_config(raw)


def test_task_routing_must_reference_profile() -> None:
    raw = _valid_config()
    raw["tasks"]["document_ocr"] = "ghost"

    with pytest.raises(LlmSchemaError, match="document_ocr"):
        validate_llm_config(raw)


def test_unknown_profile_fields_are_preserved_in_extra() -> None:
    raw = _valid_config()
    raw["profiles"]["local"]["command"] = "codex exec"
    raw["profiles"]["local"]["custom_flag"] = True

    cfg = validate_llm_config(raw)

    assert cfg.profiles["local"].command == "codex exec"
    assert cfg.profiles["local"].extra == {"custom_flag": True}


def test_repo_llm_config_defines_offline_extraction_profiles() -> None:
    raw = llm_config_raw(get_project_root() / "config" / "system" / "llm.yaml")
    cfg = validate_llm_config(raw)

    assert cfg.profiles["local_ocr"].model == "glm-ocr"
    assert cfg.profiles["local_asr"].model == "whisper-large-v3-int8-ov"
    assert cfg.tasks["document_ocr"] == "local_ocr"
    assert cfg.tasks["document_asr"] == "local_asr"


def test_timeout_must_be_integer() -> None:
    raw = _valid_config()
    raw["profiles"]["local"]["timeout_s"] = "not-an-int"

    with pytest.raises(LlmSchemaError, match="timeout_s"):
        validate_llm_config(raw)


def test_schema_constants_are_frozensets() -> None:
    assert REQUIRED_KEYS == frozenset({"active_profile", "profiles"})
    assert "tasks" in OPTIONAL_KEYS
    assert REQUIRED_PROFILE_FIELDS == frozenset({"provider", "base_url", "model"})
