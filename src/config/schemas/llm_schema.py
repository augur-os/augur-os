"""Canonical schema for config/system/llm.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class LlmSchemaError(ValueError):
    """Raised when llm.yaml violates the canonical schema."""


@dataclass(frozen=True)
class LlmProfile:
    """One named internal-task LLM profile."""

    name: str
    provider: str
    base_url: str
    model: str
    timeout_s: int = 60
    api_key_env: str | None = None
    api_key: str | None = None
    command: str | None = None
    disable_thinking: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmConfig:
    """Top-level llm.yaml shape."""

    active_profile: str
    profiles: dict[str, LlmProfile]
    tasks: dict[str, str] = field(default_factory=dict)


REQUIRED_KEYS: frozenset[str] = frozenset({"active_profile", "profiles"})
OPTIONAL_KEYS: frozenset[str] = frozenset({"tasks"})
REQUIRED_PROFILE_FIELDS: frozenset[str] = frozenset({"provider", "base_url", "model"})

_KNOWN_PROFILE_FIELDS: frozenset[str] = frozenset(
    {
        "provider",
        "base_url",
        "model",
        "timeout_s",
        "api_key_env",
        "api_key",
        "command",
        "disable_thinking",
    }
)


def _require_string(value: Any, *, field_name: str, profile_name: str | None = None) -> str:
    if isinstance(value, str) and value.strip():
        return value
    prefix = f"profile {profile_name!r}: " if profile_name is not None else ""
    raise LlmSchemaError(f"{prefix}{field_name} must be a non-empty string")


def _coerce_timeout(value: Any, *, profile_name: str) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise LlmSchemaError(f"profile {profile_name!r}: timeout_s must be an integer, got {value!r}") from exc
    if timeout <= 0:
        raise LlmSchemaError(f"profile {profile_name!r}: timeout_s must be positive")
    return timeout


def validate_llm_config(raw: Any) -> LlmConfig:
    """Validate raw YAML data and return a typed config."""

    if not isinstance(raw, dict):
        raise LlmSchemaError("llm.yaml top-level must be a mapping")

    raw_keys = set(raw)
    unknown = raw_keys - REQUIRED_KEYS - OPTIONAL_KEYS
    if unknown:
        raise LlmSchemaError(
            f"llm.yaml has unknown top-level key(s): {sorted(unknown)}. "
            f"Allowed: {sorted(REQUIRED_KEYS | OPTIONAL_KEYS)}"
        )

    missing = REQUIRED_KEYS - raw_keys
    if missing:
        raise LlmSchemaError(f"llm.yaml missing required key(s): {sorted(missing)}")

    profiles_raw = raw["profiles"]
    if not isinstance(profiles_raw, dict) or not profiles_raw:
        raise LlmSchemaError("llm.yaml 'profiles' must be a non-empty mapping")

    profiles: dict[str, LlmProfile] = {}
    for name, profile_raw in profiles_raw.items():
        if not isinstance(name, str) or not name.strip():
            raise LlmSchemaError("profile names must be non-empty strings")
        if not isinstance(profile_raw, dict):
            raise LlmSchemaError(f"profile {name!r} must be a mapping")

        missing_fields = REQUIRED_PROFILE_FIELDS - set(profile_raw)
        if missing_fields:
            raise LlmSchemaError(f"profile {name!r} missing required field(s): {sorted(missing_fields)}")

        profiles[name] = LlmProfile(
            name=name,
            provider=_require_string(profile_raw.get("provider"), field_name="provider", profile_name=name),
            base_url=_require_string(profile_raw.get("base_url"), field_name="base_url", profile_name=name),
            model=_require_string(profile_raw.get("model"), field_name="model", profile_name=name),
            timeout_s=_coerce_timeout(profile_raw.get("timeout_s", 60), profile_name=name),
            api_key_env=profile_raw.get("api_key_env") if isinstance(profile_raw.get("api_key_env"), str) else None,
            api_key=profile_raw.get("api_key") if isinstance(profile_raw.get("api_key"), str) else None,
            command=profile_raw.get("command") if isinstance(profile_raw.get("command"), str) else None,
            disable_thinking=bool(profile_raw.get("disable_thinking", False)),
            extra={key: value for key, value in profile_raw.items() if key not in _KNOWN_PROFILE_FIELDS},
        )

    active_profile = _require_string(raw.get("active_profile"), field_name="active_profile")
    if active_profile not in profiles:
        raise LlmSchemaError(
            f"active_profile={active_profile!r} must reference one of the defined profiles: " f"{sorted(profiles)}"
        )

    tasks_raw = raw.get("tasks", {})
    if tasks_raw is None:
        tasks_raw = {}
    if not isinstance(tasks_raw, dict):
        raise LlmSchemaError("llm.yaml 'tasks' must be a mapping of task name to profile name")

    tasks: dict[str, str] = {}
    for task_name, profile_name in tasks_raw.items():
        if not isinstance(task_name, str) or not task_name.strip():
            raise LlmSchemaError("task names must be non-empty strings")
        if not isinstance(profile_name, str) or profile_name not in profiles:
            raise LlmSchemaError(f"task {task_name!r}: profile {profile_name!r} not defined in profiles")
        tasks[task_name] = profile_name

    return LlmConfig(active_profile=active_profile, profiles=profiles, tasks=tasks)
