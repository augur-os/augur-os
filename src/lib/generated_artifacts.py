"""
Helpers for generated artifacts that are committed to the repository.

These files often include volatile metadata such as generated_at timestamps.
When the semantic payload is unchanged, rewriting them creates noisy dirty
trees and merge conflicts. The helpers here skip writes in that case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml


def _normalize(value: Any, volatile_keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize(child, volatile_keys) for key, child in sorted(value.items()) if key not in volatile_keys
        }
    if isinstance(value, list):
        return [_normalize(item, volatile_keys) for item in value]
    return value


def _semantic_signature(value: Any, volatile_keys: Iterable[str]) -> str:
    normalized = _normalize(value, set(volatile_keys))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_text(text: str, volatile_line_prefixes: Iterable[str]) -> str:
    prefixes = tuple(volatile_line_prefixes)
    lines = [line for line in text.splitlines() if not any(line.startswith(prefix) for prefix in prefixes)]
    normalized = "\n".join(lines)
    if text.endswith("\n"):
        normalized += "\n"
    return normalized


def write_stable_json(
    path: Path,
    payload: Any,
    *,
    volatile_keys: Iterable[str] = (),
    indent: int = 2,
) -> bool:
    """Write JSON unless the semantic payload already matches on disk."""
    serialized = json.dumps(payload, indent=indent, ensure_ascii=False) + "\n"

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if _semantic_signature(existing, volatile_keys) == _semantic_signature(payload, volatile_keys):
                return False
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return True


def write_stable_yaml(
    path: Path,
    payload: Any,
    *,
    volatile_keys: Iterable[str] = (),
) -> bool:
    """Write YAML unless the semantic payload already matches on disk."""
    serialized = yaml.safe_dump(
        payload,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    if path.exists():
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8"))
            if _semantic_signature(existing, volatile_keys) == _semantic_signature(payload, volatile_keys):
                return False
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    return True


def write_stable_text(
    path: Path,
    content: str,
    *,
    volatile_line_prefixes: Iterable[str] = (),
) -> bool:
    """Write text unless the content only differs in volatile lines."""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
            if _normalize_text(existing, volatile_line_prefixes) == _normalize_text(content, volatile_line_prefixes):
                return False
        except OSError:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True
