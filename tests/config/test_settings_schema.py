"""Tests for the permissive config/system/settings.yaml schema."""

from __future__ import annotations

import pytest

from src.config.schemas.settings_schema import (
    ALLOWED_MODES,
    KNOWN_KEYS,
    SettingsConfig,
    SettingsSchemaError,
    validate_settings_config,
)


def test_empty_settings_return_defaults() -> None:
    cfg = validate_settings_config({})

    assert isinstance(cfg, SettingsConfig)
    assert cfg.mode == "production"
    assert cfg.default_cli is None


def test_valid_modes_are_accepted() -> None:
    assert validate_settings_config({"mode": "production"}).mode == "production"
    assert validate_settings_config({"mode": "prod"}).mode == "production"
    assert validate_settings_config({"mode": "dev"}).mode == "dev"
    assert validate_settings_config({"mode": "development"}).mode == "dev"


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(SettingsSchemaError, match="mode"):
        validate_settings_config({"mode": "staging"})


def test_default_cli_must_be_string_when_present() -> None:
    assert validate_settings_config({"default_cli": "claude"}).default_cli == "claude"

    with pytest.raises(SettingsSchemaError, match="default_cli"):
        validate_settings_config({"default_cli": 42})


def test_unknown_keys_are_preserved_as_extra() -> None:
    cfg = validate_settings_config({"mode": "dev", "future_flag": True})

    assert cfg.extra == {"future_flag": True}


def test_top_level_must_be_mapping() -> None:
    with pytest.raises(SettingsSchemaError, match="top-level"):
        validate_settings_config([])


def test_schema_constants_are_frozensets() -> None:
    assert isinstance(ALLOWED_MODES, frozenset)
    assert isinstance(KNOWN_KEYS, frozenset)
    assert {"production", "dev"}.issubset(ALLOWED_MODES)
    assert KNOWN_KEYS == frozenset({"mode", "default_cli"})
