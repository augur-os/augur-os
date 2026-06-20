"""Loader for config/system/search.yaml -- RRF k + search budgets (ADR-739)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.logging import get_entity_logger

logger = get_entity_logger("lib.index.search_config")

_DEFAULTS: dict[str, Any] = {
    "rrf": {"k": 60, "per_source_limit": 50},
    "search_budgets": {
        "conservative": {"top_k": 5, "token_estimate": 4000},
        "balanced": {"top_k": 10, "token_estimate": 10000},
        "tokenmax": {"top_k": 20, "token_estimate": 20000},
    },
    "default_budget": "balanced",
}


def _clone_defaults() -> dict[str, Any]:
    return {
        "rrf": dict(_DEFAULTS["rrf"]),
        "search_budgets": {name: dict(spec) for name, spec in _DEFAULTS["search_budgets"].items()},
        "default_budget": _DEFAULTS["default_budget"],
    }


def _config_path() -> Path:
    """Path to config/system/search.yaml. Monkeypatchable in tests."""
    from src.config.paths import get_project_root

    return get_project_root() / "config" / "system" / "search.yaml"


def load_search_config() -> dict[str, Any]:
    """Load search.yaml merged over built-in defaults, failing closed."""
    cfg = _clone_defaults()
    try:
        data = yaml.safe_load(_config_path().read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return cfg
        if isinstance(data.get("rrf"), dict):
            cfg["rrf"].update(data["rrf"])
        if isinstance(data.get("search_budgets"), dict):
            for name, spec in data["search_budgets"].items():
                if isinstance(spec, dict):
                    cfg["search_budgets"][str(name)] = {
                        **cfg["search_budgets"].get(str(name), {}),
                        **spec,
                    }
        if data.get("default_budget") in cfg["search_budgets"]:
            cfg["default_budget"] = data["default_budget"]
    except Exception as exc:  # noqa: BLE001 - search should degrade to defaults
        logger.warning("search.yaml unusable (%s); using built-in defaults", exc)
    return cfg


def budget_top_k(cfg: dict[str, Any], budget: str | None) -> int:
    """Resolve a budget name to top_k, falling back to default_budget."""
    budgets = cfg["search_budgets"]
    default_budget = cfg.get("default_budget", _DEFAULTS["default_budget"])
    name = budget if budget in budgets else default_budget
    return int(budgets[name]["top_k"])


def budget_token_estimate(cfg: dict[str, Any], budget: str | None) -> int:
    """Resolve a budget name to its display-only token estimate."""
    budgets = cfg["search_budgets"]
    default_budget = cfg.get("default_budget", _DEFAULTS["default_budget"])
    name = budget if budget in budgets else default_budget
    return int(budgets[name].get("token_estimate", 0))


def resolve_budget_name(cfg: dict[str, Any], budget: str | None) -> str:
    """Return the effective budget name for a caller-supplied budget."""
    budgets = cfg["search_budgets"]
    default_budget = cfg.get("default_budget", _DEFAULTS["default_budget"])
    return str(budget if budget in budgets else default_budget)
