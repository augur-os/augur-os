"""Shared setup probe helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from ..types import ProbeResult


def done(details: str | None = None) -> ProbeResult:
    return ProbeResult(status="done", details=details)


def pending(details: str | None = None) -> ProbeResult:
    return ProbeResult(status="pending", details=details)


def has_any_file(paths: Iterable[Path]) -> bool:
    return any(path.is_file() and path.stat().st_size > 0 for path in paths)


def count_markdown(path: Path, *, exclude_readme: bool = False) -> int:
    if not path.exists():
        return 0
    count = 0
    for file_path in path.rglob("*.md"):
        if exclude_readme and file_path.name.lower() == "readme.md":
            continue
        count += 1
    return count


def yaml_enabled(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if isinstance(data, dict):
        if data.get("enabled") is True or data.get("active") is True:
            return True
        return any(value is True for value in data.values())
    return False
