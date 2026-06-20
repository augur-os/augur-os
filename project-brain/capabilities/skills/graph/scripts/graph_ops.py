"""Orchestrator for the typed knowledge graph (ADR-738).

index_page() is the single entry point the /ingest, /wiki, /save, /ask, /profile
write paths call: extract -> merge frontmatter -> update cache. Also hosts the
CLI dispatch (`aug graph <verb>`). Errors NEVER raise into a write path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import edge_extractor
import edge_writer
import graph_cache
import graph_query
from edge_rules import load_rules

logger = logging.getLogger("graph.ops")


def _edge_config_path() -> Path:
    from src.config.paths import get_project_root

    return get_project_root() / "config" / "system" / "graph_edges.yaml"


def _vault_dir() -> Path:
    from src.config.paths import get_vault_dir

    return get_vault_dir()


# In-memory src page-id -> source_type map, persisted alongside the cache so
# tiering can run without re-reading every page. Rebuilt fully by graph-rebuild.
def _src_types_path() -> Path:
    return graph_cache._cache_dir() / "src_types.json"


def _load_src_types() -> dict[str, str]:
    import json

    p = _src_types_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_src_types(src_types: dict[str, str]) -> None:
    import json

    path = _src_types_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(src_types, indent=2), encoding="utf-8")


def page_paths_by_id(pages: list[Path] | None = None) -> dict[str, list[Path]]:
    """Map graph page ids to vault markdown paths."""
    if pages is None:
        pages = sorted(_vault_dir().rglob("*.md"))
    paths_by_id: dict[str, list[Path]] = {}
    for page in pages:
        paths_by_id.setdefault(page.stem, []).append(page)
    return paths_by_id


def write_entity_tiers(
    tiers: dict[str, int],
    *,
    paths_by_id: dict[str, list[Path]] | None = None,
) -> int:
    """Persist computed entity tiers into matching vault page frontmatter."""
    from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

    paths_by_id = paths_by_id or page_paths_by_id()
    written = 0
    for entity_id, tier in sorted(tiers.items()):
        for path in paths_by_id.get(entity_id, []):
            meta, body = parse_frontmatter(path, include_sidecar_config=False)
            if meta.get("_entity_tier") == tier:
                continue
            meta["_entity_tier"] = tier
            write_frontmatter(path, meta, body)
            written += 1
    return written


def index_page(
    path: str | Path,
    *,
    source_type: str = "unknown",
    known: dict[str, Any] | None = None,
    prune: bool = False,
) -> dict[str, Any]:
    """Extract -> merge frontmatter -> update cache for one page. Never raises."""
    path = Path(path)
    try:
        ruleset = load_rules(_edge_config_path())
        edges = edge_extractor.extract(path, known=known, ruleset=ruleset)
        diff = edge_writer.merge(path, edges, prune=prune)

        # incremental cache update: drop this page's old edges, add the new ones
        page_id = path.stem
        kept = [e for e in graph_cache.load_edges() if e.src != page_id]
        graph_cache.write_edges(kept + edges)

        src_types = _load_src_types()
        src_types[page_id] = source_type
        _save_src_types(src_types)

        return {"page": page_id, "edges": len(edges), "diff": diff, "ok": True}
    except Exception as exc:  # noqa: BLE001 — a graph failure must not break a write
        logger.warning("graph.index_page failed for %s: %s", path, exc)
        return {"page": Path(path).stem, "ok": False, "error": str(exc)}


def index_page_from_write_path(
    path: str | Path,
    *,
    source_type: str = "unknown",
    known: dict[str, Any] | None = None,
    prune: bool = False,
) -> dict[str, Any]:
    """Write-path integration entry point — what /ingest, /wiki, /ask, /profile call.

    A no-op under pytest: foreign test suites (ingest, knowledge, ...) exercise
    the wired writer functions, and their fixtures do not patch this skill's
    `_cache_dir()`, so an unguarded call would write test-fixture edges into the
    real `get_cache_dir()/graph/` cache. The graph skill's own tests call
    `index_page()` directly with a patched cache, so they are unaffected. In
    production `PYTEST_CURRENT_TEST` is never set and this just delegates.
    """
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"page": Path(path).stem, "ok": True, "skipped": "pytest"}
    return index_page(path, source_type=source_type, known=known, prune=prune)


def recompute_tiers(
    *,
    write_frontmatter: bool = True,
    paths_by_id: dict[str, list[Path]] | None = None,
) -> dict[str, int]:
    """Recompute _entity_tier for every entity and refresh entities.jsonl."""
    import entity_tier

    ruleset = load_rules(_edge_config_path())
    edges = graph_cache.load_edges()
    src_types = _load_src_types()
    tiers = entity_tier.recompute_all(edges, src_types, ruleset)
    from collections import Counter

    inbound = Counter(e.dst for e in edges)
    graph_cache.write_entities(
        [
            {"id": eid, "tier": tier, "inbound_count": inbound.get(eid, 0)}
            for eid, tier in sorted(tiers.items())
        ]
    )
    if write_frontmatter:
        write_entity_tiers(tiers, paths_by_id=paths_by_id)
    return tiers


def run_cli(verb: str, args: Any) -> int:
    """Dispatch `aug graph <verb>`."""
    import json

    if verb == "extract":
        print(json.dumps(index_page(args.path, source_type=args.source_type or "unknown"), indent=2))
        return 0
    if verb == "query":
        edges = graph_query.query(edge_type=args.type, entity=args.entity)
        print(json.dumps([e.__dict__ for e in edges], indent=2))
        return 0
    if verb == "stats":
        print(json.dumps(graph_query.stats(), indent=2))
        return 0
    if verb == "tier-recompute":
        tiers = recompute_tiers()
        print(json.dumps({"entities": len(tiers)}, indent=2))
        return 0
    if verb == "rebuild":
        import graph_rebuild

        print(json.dumps(graph_rebuild.rebuild(prune=args.prune, dry_run=args.dry_run), indent=2))
        return 0
    print(json.dumps({"error": "unknown verb", "verb": verb}, indent=2))
    return 2
