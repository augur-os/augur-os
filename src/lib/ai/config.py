from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

ProviderType = Literal["openai_compatible", "command", "agentic_ide"]


@dataclass(frozen=True)
class LLMProfile:
    name: str
    provider: ProviderType

    # OpenAI-compatible HTTP
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None  # Not recommended; prefer *_env.
    model: str | None = None

    # Command provider (reads prompt from stdin, writes response to stdout)
    command: str | None = None

    # Shared options
    timeout_s: int = 600

    # Optional feature flags
    response_format_json: bool = False
    temperature: float | None = None
    disable_thinking: bool = False


@dataclass(frozen=True)
class LLMConfig:
    active_profile: str | None
    profiles: dict[str, LLMProfile]
    tasks: dict[str, str] | None = None
    overrides: dict[str, Any] | None = None  # keys: layers, components
    source_path: Path | None = None


def _user_data_base() -> Path:
    # Centralized data root resolution.
    from src.config.paths import get_project_root  # type: ignore

    return get_project_root()


def _try_load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except Exception as e:
        logger.warning("Failed to import yaml module: %s", e)
        yaml = None

    if yaml is None:
        return None

    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read YAML file %s: %s", path, e)
        return None

    try:
        parsed = yaml.safe_load(raw)  # noqa: S506
    except Exception as e:
        logger.warning("Failed to parse YAML from %s: %s", path, e)
        return None

    return parsed if isinstance(parsed, dict) else None


def _load_from_files(user_data_base: Path) -> tuple[dict[str, Any], Path | None]:
    """
    Supported locations (checked in order):
    - <data>/llm.yaml (preferred; whole file is the llm config block)
    - <data>/llm.yml
    - <data>/config.yaml (reads `llm:` section only)
    - <data>/config/system/llm.yaml (system-level defaults)
    """
    for candidate in (user_data_base / "llm.yaml", user_data_base / "llm.yml"):
        if not candidate.exists():
            continue
        parsed = _try_load_yaml(candidate)
        if parsed is not None:
            return parsed, candidate

    config_yaml = user_data_base / "config.yaml"
    if config_yaml.exists():
        parsed = _try_load_yaml(config_yaml)
        if isinstance(parsed, dict):
            llm_block = parsed.get("llm")
            if isinstance(llm_block, dict):
                return llm_block, config_yaml

    system_llm = user_data_base / "config" / "system" / "llm.yaml"
    if system_llm.exists():
        try:
            from src.config.system_config import llm_config_raw

            return llm_config_raw(system_llm), system_llm
        except Exception as exc:
            logger.warning("Failed to load validated system llm config from %s: %s", system_llm, exc)

    return {}, None


def _coerce_int(value: Any, default: int) -> int:
    try:
        i = int(value)
    except Exception as e:
        logger.debug("Failed to coerce value to int, using default %d: %s", default, e)
        return default
    return i if i > 0 else default


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception as e:
        logger.debug("Failed to coerce value to float: %s", e)
        return None


def load_llm_config(*, user_data_base: Path | None = None) -> LLMConfig:
    """
    Load LLM configuration from the user data repo.

    Environment overrides:
    - AUGUR_LLM_PROFILE
    - AUGUR_LLM_BASE_URL
    - AUGUR_LLM_MODEL
    - AUGUR_LLM_API_KEY / AUGUR_LLM_API_KEY_ENV
    """
    base = user_data_base or _user_data_base()
    raw, source = _load_from_files(base)

    active_profile = raw.get("active_profile") or raw.get("profile")
    if not isinstance(active_profile, str):
        active_profile = None

    profiles_raw = raw.get("profiles")
    profiles: dict[str, LLMProfile] = {}
    if isinstance(profiles_raw, dict):
        for name, value in profiles_raw.items():
            if not isinstance(name, str) or not name.strip():
                continue
            if not isinstance(value, dict):
                continue
            provider = value.get("provider") or value.get("type") or "openai_compatible"
            if provider not in ("openai_compatible", "command", "agentic_ide"):
                continue

            profiles[name] = LLMProfile(
                name=name,
                provider=provider,  # type: ignore[arg-type]
                base_url=value.get("base_url") if isinstance(value.get("base_url"), str) else None,
                api_key_env=value.get("api_key_env") if isinstance(value.get("api_key_env"), str) else None,
                api_key=value.get("api_key") if isinstance(value.get("api_key"), str) else None,
                model=value.get("model") if isinstance(value.get("model"), str) else None,
                command=value.get("command") if isinstance(value.get("command"), str) else None,
                timeout_s=_coerce_int(value.get("timeout_s"), 60),
                response_format_json=bool(value.get("response_format_json", False)),
                temperature=_coerce_float(value.get("temperature")),
                disable_thinking=bool(value.get("disable_thinking", False)),
            )

    # Env-based "inline profile" (useful for simple setups)
    env_base_url = os.environ.get("AUGUR_LLM_BASE_URL")
    env_model = os.environ.get("AUGUR_LLM_MODEL")
    env_api_key = os.environ.get("AUGUR_LLM_API_KEY")
    env_api_key_env = os.environ.get("AUGUR_LLM_API_KEY_ENV")
    if env_base_url or env_model or env_api_key or env_api_key_env:
        profiles["env"] = LLMProfile(
            name="env",
            provider="openai_compatible",
            base_url=env_base_url.strip() if isinstance(env_base_url, str) and env_base_url.strip() else None,
            api_key_env=(
                env_api_key_env.strip() if isinstance(env_api_key_env, str) and env_api_key_env.strip() else None
            ),
            api_key=env_api_key.strip() if isinstance(env_api_key, str) and env_api_key.strip() else None,
            model=env_model.strip() if isinstance(env_model, str) and env_model.strip() else None,
        )

    # External selection of active profile.
    env_profile = os.environ.get("AUGUR_LLM_PROFILE")
    if isinstance(env_profile, str) and env_profile.strip():
        active_profile = env_profile.strip()

    # Auto-detect CLI and inject synthetic "cli" profile
    try:
        from .cli_detect import detect_cli, cli_command

        cli_path = detect_cli()
        if cli_path:
            local_model = None
            if "local" in profiles:
                local_model = profiles["local"].model
            cmd = cli_command(cli_path, model=local_model)
            profiles["cli"] = LLMProfile(
                name="cli",
                provider="command",
                command=cmd,
                timeout_s=120,
            )
            # Set as active if no explicit active_profile from config file
            file_active = raw.get("active_profile") or raw.get("profile")
            if not isinstance(file_active, str) or not file_active.strip():
                active_profile = "cli"
    except Exception as exc:
        logger.debug("CLI auto-detection failed: %s", exc)

    overrides = raw.get("overrides")

    # Parse tasks mapping
    tasks_raw = raw.get("tasks")
    tasks: dict[str, str] = {}
    if isinstance(tasks_raw, dict):
        for t, p in tasks_raw.items():
            if isinstance(t, str) and isinstance(p, str):
                tasks[t] = p

    return LLMConfig(
        active_profile=active_profile,
        profiles=profiles,
        tasks=tasks or None,
        overrides=overrides if isinstance(overrides, dict) else None,
        source_path=source,
    )


_airplane_cache: tuple[float, bool] | None = None
_AIRPLANE_CACHE_TTL = 30.0


def _is_airplane_mode() -> bool:
    """Check if airplane mode is active.

    Checks (in order):
    1. AUGUR_AIRPLANE_MODE env var ("1", "true", "yes") — no cache, always fresh
    2. preferences.yaml airplane_mode.enabled — cached with 30s TTL
    """
    global _airplane_cache

    env_val = os.environ.get("AUGUR_AIRPLANE_MODE", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        return True

    now = time.monotonic()
    if _airplane_cache is not None and (now - _airplane_cache[0]) < _AIRPLANE_CACHE_TTL:
        return _airplane_cache[1]

    result = _check_airplane_prefs()
    _airplane_cache = (now, result)
    return result


def _check_airplane_prefs() -> bool:
    """Read airplane_mode.enabled from preferences.yaml."""
    try:
        from src.config.preferences import load_preferences

        data = load_preferences()
        airplane = data.get("airplane_mode", {})
        if isinstance(airplane, dict) and airplane.get("enabled"):
            return True
    except Exception:
        pass
    return False


def resolve_llm_profile(
    config: LLMConfig, *, name: str | None = None, context: str | None = None, task: str | None = None
) -> LLMProfile:
    """
    Resolve an LLM profile from config.

    Context format: "layer/component" (e.g. "factory/planner") or just "layer".

    Resolution Order:
      1) Explicit name (if provided)
      2) Task mapping (if task provided and matches)
      3) Component override (if context matches component)
      4) Layer override (if context matches layer)
      5) Global config.active_profile
      6) "env" (if present)
      7) "default" (if present)
      8) First available profile
    """
    # 1. Explicit name takes precedence
    if name and name in config.profiles:
        return config.profiles[name]

    # 1.5 Airplane mode override — prefer Ollama CLI, fall back to HTTP local
    if _is_airplane_mode():
        import shutil as _shutil

        ollama_path = _shutil.which("ollama")
        if ollama_path:
            local_model = None
            local_profile = config.profiles.get("local")
            if local_profile and local_profile.model:
                local_model = local_profile.model
            from .cli_detect import cli_command

            cmd = cli_command(ollama_path, model=local_model)
            return LLMProfile(
                name="cli-offline",
                provider="command",
                command=cmd,
                timeout_s=120,
            )
        local = config.profiles.get("local")
        if local:
            return local

    # Resolve active profile name based on context
    candidate_name = config.active_profile

    # 2. Task Query
    if task and config.tasks and task in config.tasks:
        task_profile = config.tasks[task]
        if task_profile in config.profiles:
            return config.profiles[task_profile]

    if context and config.overrides:
        parts = context.split("/")
        layer = parts[0] if parts else None

        # Layer Check
        if layer:
            layer_ov = config.overrides.get("layers", {}).get(layer)
            if isinstance(layer_ov, dict) and "active_profile" in layer_ov:
                candidate_name = layer_ov["active_profile"]

        # Component Check (Precedes/Overwrites Layer)
        comp_ov = config.overrides.get("components", {}).get(context)
        if isinstance(comp_ov, dict) and "active_profile" in comp_ov:
            candidate_name = comp_ov["active_profile"]

    # 3-5. Use resolved active profile name
    if candidate_name and candidate_name in config.profiles:
        return config.profiles[candidate_name]

    # 5. Env fallback
    if "env" in config.profiles:
        return config.profiles["env"]

    # 6. Default/Remote fallback
    if "default" in config.profiles:
        return config.profiles["default"]
    if "remote" in config.profiles:
        return config.profiles["remote"]

    # 7. Any fallback
    if config.profiles:
        first = sorted(config.profiles.keys(), key=lambda s: s.lower())[0]
        return config.profiles[first]

    raise RuntimeError(
        "No LLM profiles configured. Add `llm.profiles` in your user data `config.yaml` "
        "or set AUGUR_LLM_BASE_URL + AUGUR_LLM_MODEL."
    )
