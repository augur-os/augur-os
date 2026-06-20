"""One-shot full-vault backfill for the typed knowledge graph (ADR-738).

Scans every markdown page under the vault, runs extract -> merge -> cache, then
recomputes tiers. Idempotent. `dry_run=True` reports without writing. `prune=True`
removes managed-key entries whose rule no longer matches. Zero LLM cost.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import edge_extractor
import edge_writer
import graph_cache
import graph_ops
from edge_rules import load_rules


def _vault_dir() -> Path:
    from src.config.paths import get_vault_dir

    return get_vault_dir()


# vault subdir -> source_type, matched by longest-prefix
_SOURCE_TYPE_BY_DIR = {
    "sources/urls": "url",
    "sources/files": "file",
    "memory/entries": "memory",
    "wiki/concepts": "concept",
    "wiki": "wiki",
    "profile": "profile",
}


def _source_type_for(rel: Path) -> str:
    s = rel.as_posix()
    for prefix, stype in sorted(_SOURCE_TYPE_BY_DIR.items(), key=lambda kv: -len(kv[0])):
        if s.startswith(prefix + "/") or s == prefix:
            return stype
    return "unknown"


def rebuild(*, prune: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Backfill the whole vault. Returns a summary diff."""
    vault = _vault_dir()
    ruleset = load_rules(graph_ops._edge_config_path())
    pages = sorted(vault.rglob("*.md"))

    all_edges: list[edge_extractor.Edge] = []
    src_types: dict[str, str] = {}
    added = removed = 0
    entity_tiers_written = 0
    failures: list[str] = []

    for page in pages:
        try:
            stype = _source_type_for(page.relative_to(vault))
            edges = edge_extractor.extract(page, ruleset=ruleset)
            all_edges.extend(edges)
            src_types[page.stem] = stype
            if not dry_run:
                diff = edge_writer.merge(page, edges, prune=prune)
                added += len(diff["added"])
                removed += len(diff["removed"])
        except Exception as exc:  # noqa: BLE001 — partial graph is acceptable
            failures.append(f"{page}: {exc}")

    if not dry_run:
        graph_cache.write_edges(all_edges)
        graph_ops._save_src_types(src_types)
        paths_by_id = graph_ops.page_paths_by_id(pages)
        tiers = graph_ops.recompute_tiers(
            write_frontmatter=False,
            paths_by_id=paths_by_id,
        )
        entity_tiers_written = graph_ops.write_entity_tiers(
            tiers,
            paths_by_id=paths_by_id,
        )

    return {
        "pages_scanned": len(pages),
        "edges_total": len(all_edges),
        "frontmatter_added": added,
        "frontmatter_removed": removed,
        "entity_tiers_written": entity_tiers_written,
        "failures": failures,
        "dry_run": dry_run,
        "pruned": prune,
    }
