"""Permissive schema for config/system/settings.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SettingsSchemaError(ValueError):
    """Raised when settings.yaml violates the supported schema."""


@dataclass(frozen=True)
class SettingsConfig:
    """Known settings.yaml fields plus forward-compatible extras."""

    mode: str = "production"
    default_cli: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


ALLOWED_MODES: frozenset[str] = frozenset({"production", "prod", "dev", "development"})
KNOWN_KEYS: frozenset[str] = frozenset({"mode", "default_cli"})


def _normalize_mode(value: Any) -> str:
    if value is None:
        return "production"
    if not isinstance(value, str):
        raise SettingsSchemaError("settings.yaml mode must be a string")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_MODES:
        raise SettingsSchemaError(f"settings.yaml mode must be one of {sorted(ALLOWED_MODES)}, got {value!r}")
    return "production" if normalized == "prod" else "dev" if normalized == "development" else normalized


def validate_settings_config(raw: Any) -> SettingsConfig:
    """Validate raw settings data and return known fields plus extras."""

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise SettingsSchemaError("settings.yaml top-level must be a mapping")

    default_cli = raw.get("default_cli")
    if default_cli is not None and not isinstance(default_cli, str):
        raise SettingsSchemaError("settings.yaml default_cli must be a string when present")
    if isinstance(default_cli, str):
        default_cli = default_cli.strip() or None

    return SettingsConfig(
        mode=_normalize_mode(raw.get("mode")),
        default_cli=default_cli,
        extra={key: value for key, value in raw.items() if key not in KNOWN_KEYS},
    )
