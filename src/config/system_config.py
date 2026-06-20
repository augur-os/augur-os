"""Validated readers for protected config/system files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_config_dir
from src.config.schemas.llm_schema import LlmConfig, LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import (
    SettingsConfig,
    SettingsSchemaError,
    validate_settings_config,
)


def _system_path(filename: str) -> Path:
    return get_config_dir() / "system" / filename


def _read_yaml_mapping(path: Path, *, missing_ok: bool) -> dict[str, Any]:
    if not path.exists():
        if missing_ok:
            return {}
        raise FileNotFoundError(f"Required system config file is missing: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML from {path}: {exc}") from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"System config file must contain a mapping: {path}")
    return raw


def llm_config_raw(path: Path | None = None) -> dict[str, Any]:
    """Return raw llm.yaml data for read-modify-write paths."""

    return _read_yaml_mapping(path or _system_path("llm.yaml"), missing_ok=False)


def settings_config_raw(path: Path | None = None) -> dict[str, Any]:
    """Return raw settings.yaml data; missing settings file is an empty mapping."""

    return _read_yaml_mapping(path or _system_path("settings.yaml"), missing_ok=True)


@lru_cache(maxsize=1)
def load_llm_config() -> LlmConfig:
    """Load and validate config/system/llm.yaml."""

    path = _system_path("llm.yaml")
    try:
        return validate_llm_config(llm_config_raw(path))
    except LlmSchemaError as exc:
        raise LlmSchemaError(
            f"{path}: {exc}. Run scripts/restore_system_config.py --apply "
            "or update src/config/schemas/llm_schema.py before changing the file shape."
        ) from exc


@lru_cache(maxsize=1)
def load_settings_config() -> SettingsConfig:
    """Load and validate config/system/settings.yaml."""

    path = _system_path("settings.yaml")
    try:
        return validate_settings_config(settings_config_raw(path))
    except SettingsSchemaError as exc:
        raise SettingsSchemaError(f"{path}: {exc}") from exc


def invalidate_caches() -> None:
    """Clear cached protected config reads."""

    load_llm_config.cache_clear()
    load_settings_config.cache_clear()
