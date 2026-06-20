"""Additive per-type frontmatter writer for typed edges (ADR-738).

Each edge type is its own underscore-prefixed key holding a list of [[wikilinks]]
(system-managed per ADR-571, but MERGED not overwritten — a user-added edge is
never clobbered). Only merge(..., prune=True) removes entries, and it diffs first.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.lib.frontmatter_utils import (
    VAULT_SYSTEM_FIELD_MAP,
    parse_frontmatter,
    write_frontmatter,
)
from edge_rules import load_rules


def _key(edge_type: str) -> str:
    return f"_{edge_type}"


def _wikilink(dst: str) -> str:
    return dst if dst.startswith("[[") else f"[[{dst}]]"


def _managed_edge_keys() -> set[str]:
    return {_key(edge_type) for edge_type in load_rules().edge_types}


def _drop_system_read_aliases(meta: dict[str, Any]) -> None:
    for legacy_key, system_key in VAULT_SYSTEM_FIELD_MAP.items():
        if system_key in meta:
            meta.pop(legacy_key, None)


def merge(path: str | Path, edges: Iterable[Any], *, prune: bool = False) -> dict[str, list[str]]:
    """Additively merge typed edges into a page's per-type frontmatter keys.

    Returns a diff: {"added": [...], "removed": [...], "unchanged": [...]}.
    `prune=True` removes managed-key entries not present in `edges`.
    """
    path = Path(path)
    meta, body = parse_frontmatter(path)

    extracted: dict[str, set[str]] = {}
    for edge in edges:
        extracted.setdefault(_key(edge.type), set()).add(_wikilink(edge.dst))

    added: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []

    edge_keys = _managed_edge_keys()
    managed_keys = set(extracted) | {k for k in meta if k in edge_keys}
    for key in sorted(managed_keys):
        if not key.startswith("_") or key == "_entity_tier":
            continue
        existing = {str(v) for v in (meta.get(key) or [])}
        incoming = extracted.get(key, set())
        if prune:
            final = incoming  # rebuild from scratch — only matched edges survive
        else:
            final = existing | incoming  # additive: user edges + extracted edges
        for v in sorted(final - existing):
            added.append(f"{key}:{v}")
        for v in sorted(existing - final):
            removed.append(f"{key}:{v}")
        for v in sorted(existing & final):
            unchanged.append(f"{key}:{v}")
        if final:
            meta[key] = sorted(final)
        elif key in meta:
            del meta[key]

    if added or removed:
        _drop_system_read_aliases(meta)
        write_frontmatter(path, meta, body)
    return {"added": added, "removed": removed, "unchanged": unchanged}
