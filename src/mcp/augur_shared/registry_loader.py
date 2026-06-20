"""
Registry loader for the Context Injector.

Handles loading, validation, caching, and health checking of the unified
IDE integration registry (registry.yaml).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from src.mcp.augur_shared.config import get_config, get_ide_registry_path
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.context.registry")

# Cache for unified registry (mode-aware filtering)
_registry_cache: dict[str, Any] | None = None
_registry_cache_time: float = 0
_registry_source_path: Path | None = None
_registry_last_error: str | None = None

_REGISTRY_REQUIRED_SECTIONS = ("skills",)
_REGISTRY_OPTIONAL_SECTIONS = ("chains", "workflows", "page_contexts")
_REGISTRY_ALL_SECTIONS = _REGISTRY_REQUIRED_SECTIONS + _REGISTRY_OPTIONAL_SECTIONS


def _registry_candidate_paths() -> list[Path]:
    cfg = get_config()
    if cfg.plugins_dir:
        return [get_ide_registry_path().resolve()]
    return []


def _validate_registry_payload(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Registry payload is not a mapping"

    for section in _REGISTRY_REQUIRED_SECTIONS:
        value = data.get(section)
        if value is None:
            return False, f"Missing required section '{section}'"
        if not isinstance(value, dict):
            return False, f"Section '{section}' must be a mapping"

    for section in _REGISTRY_OPTIONAL_SECTIONS:
        value = data.get(section)
        if value is not None and not isinstance(value, dict):
            return False, f"Section '{section}' must be a mapping"

    return True, ""


def _try_load_registry_once(candidates: list[Path]) -> tuple[dict[str, Any] | None, list[str]]:
    """Attempt to load and validate the registry from candidate paths.

    Returns:
        (registry_dict, errors) -- registry_dict is None on failure.
    """
    errors: list[str] = []
    for registry_path in candidates:
        if not registry_path.exists():
            continue

        try:
            with open(registry_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            errors.append(f"{registry_path}: parse failure ({e})")
            continue

        is_valid, validation_error = _validate_registry_payload(data)
        if not is_valid:
            errors.append(f"{registry_path}: {validation_error}")
            continue

        return {
            "skills": data.get("skills", {}),
            "chains": data.get("chains", {}),
            "workflows": data.get("workflows", {}),
            "page_contexts": data.get("page_contexts", {}),
            "_source_path": registry_path,
        }, []

    return None, errors


# Maximum retries when the file exists but fails validation (race with regeneration).
_REGISTRY_LOAD_RETRIES = 2
_REGISTRY_RETRY_DELAY_S = 0.5


def load_registry() -> dict[str, Any]:
    """
    Load the unified registry from runtime ide-integration/registry.yaml.

    The registry contains mode-tagged skills, chains, workflows, and page contexts.
    Used for mode-aware filtering.

    Retries briefly when the file exists but fails validation, to handle
    the race condition where generate_registry.py is writing the file at
    the same time the MCP server starts up.

    Returns:
        Registry dict with skills, chains, workflows, page_contexts
    """
    global _registry_cache, _registry_cache_time, _registry_source_path, _registry_last_error
    import time

    # Cache for 60 seconds to avoid constant file reads
    if _registry_cache is not None and (time.time() - _registry_cache_time) < 60:
        return _registry_cache

    empty_registry: dict[str, Any] = {
        "skills": {},
        "chains": {},
        "workflows": {},
        "page_contexts": {},
    }

    _registry_source_path = None
    _registry_last_error = None
    candidates = _registry_candidate_paths()

    last_errors: list[str] = []
    for attempt in range(_REGISTRY_LOAD_RETRIES + 1):
        if attempt > 0:
            time.sleep(_REGISTRY_RETRY_DELAY_S)
            logger.debug("Retrying registry load (attempt %d/%d)", attempt + 1, _REGISTRY_LOAD_RETRIES + 1)

        result, errors = _try_load_registry_once(candidates)
        if result is not None:
            source_path = result.pop("_source_path")
            _registry_cache = result
            _registry_cache_time = time.time()
            _registry_source_path = source_path
            _registry_last_error = None

            if attempt > 0:
                logger.info("Registry loaded after %d retries from %s", attempt, source_path)
            else:
                logger.debug(
                    "Loaded registry from %s with %d skills, %d chains, %d workflows",
                    source_path,
                    len(result["skills"]),
                    len(result["chains"]),
                    len(result["workflows"]),
                )
            return result

        last_errors = errors

    if last_errors:
        _registry_last_error = "; ".join(last_errors)
        logger.error("Failed to load valid registry: %s", _registry_last_error)
    else:
        searched = ", ".join(str(path) for path in candidates)
        _registry_last_error = f"Registry not found. Checked: {searched}"
        logger.warning("%s", _registry_last_error)

    return empty_registry


def get_registry_health() -> dict[str, Any]:
    """
    Validate registry availability and shape for startup health checks.

    Returns:
        Dict with keys: ok, source, error, counts
    """
    registry = load_registry()
    counts = {
        "skills": len(registry.get("skills", {})),
        "chains": len(registry.get("chains", {})),
        "workflows": len(registry.get("workflows", {})),
        "page_contexts": len(registry.get("page_contexts", {})),
    }

    source = str(_registry_source_path) if _registry_source_path else None
    ok = _registry_source_path is not None and counts["skills"] > 0

    error = _registry_last_error
    if not ok and not error:
        error = "Registry loaded but contains no skills"

    return {
        "ok": ok,
        "source": source,
        "error": error,
        "counts": counts,
    }
