"""dream-config — read the skill-local config.yaml (ADR-744 task 8).

The dream skill's config is **skill-local** per Rule #2 — it sits next to
SKILL.md, not in central config. Only the dream routine and its MCP tools
read it. This module is the canonical reader; every other dream script that
needs config should call ``dream_config()`` rather than re-parsing the yaml.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def dream_config(*, config_path: Path | None = None) -> dict[str, Any]:
    """Return the dream skill's parsed config.

    ``config_path`` defaults to ``<dream-skill>/config.yaml``; tests pass an
    explicit override.
    """
    path = config_path or _default_config_path()
    if not path.is_file():
        raise FileNotFoundError(f"dream config not found at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _default_config_path() -> Path:
    # scripts/dream_config.py → scripts/ → dream/ → config.yaml
    return Path(__file__).resolve().parents[1] / "config.yaml"


__all__ = ["dream_config"]
