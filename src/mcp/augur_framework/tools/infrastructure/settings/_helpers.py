"""Shared path resolution and atomic file I/O helpers for settings handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _get_config_dir() -> Path:
    from src.mcp.augur_shared.config import get_config_dir

    return get_config_dir()


def _get_state_dir() -> Path:
    from src.mcp.augur_shared.config import get_state_dir

    return get_state_dir()


def _get_project_root() -> Path:
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


# ---------------------------------------------------------------------------
# Atomic file I/O helpers
# ---------------------------------------------------------------------------


def _write_atomic_text(path: Path, content: str) -> None:
    """Atomically write *content* to *path* with a unique sibling temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _write_json(path: Path, data: Any) -> None:
    """Atomically write JSON data to *path*, creating parent dirs."""
    _write_atomic_text(path, json.dumps(data, indent=2, default=str))


def _read_json(path: Path) -> Any:
    """Read JSON from *path*, returning empty dict on missing/invalid."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_yaml(path: Path, data: Any) -> None:
    """Atomically write YAML data to *path*, creating parent dirs."""
    _write_atomic_text(
        path,
        yaml.safe_dump(
            data,
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
        ),
    )


def _read_yaml(path: Path) -> Any:
    """Read YAML from *path*, returning empty dict on missing/invalid."""
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
