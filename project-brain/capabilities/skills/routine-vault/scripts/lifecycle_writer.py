"""Atomic writer for .augur-lifecycle.yaml known_groups entries."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class LifecycleWriterError(ValueError):
    """Raised on malformed input or write-side lifecycle errors."""


class LifecycleWriterCollision(LifecycleWriterError):
    """Raised when a known_groups entry name already exists."""


def append_known_group(folder: Path, entry: dict[str, Any]) -> Path:
    """Append one known_group entry to folder/.augur-lifecycle.yaml atomically."""
    if not entry.get("name"):
        raise LifecycleWriterError("entry must include non-empty 'name'")

    target = folder / ".augur-lifecycle.yaml"
    if target.exists():
        try:
            existing = yaml.safe_load(target.read_text()) or {}
        except yaml.YAMLError as exc:
            raise LifecycleWriterError(f"existing yaml malformed: {exc}") from exc
        if not isinstance(existing, dict):
            raise LifecycleWriterError("existing yaml top-level is not a mapping")
    else:
        existing = {}

    groups = existing.get("known_groups", [])
    if not isinstance(groups, list):
        raise LifecycleWriterError("existing known_groups is not a list")

    for group in groups:
        if isinstance(group, dict) and group.get("name") == entry["name"]:
            raise LifecycleWriterCollision(
                f"known_groups entry with name={entry['name']!r} already exists"
            )

    groups.append(entry)
    existing["known_groups"] = groups

    tmp = target.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(existing, sort_keys=False))
    os.replace(tmp, target)
    return target
