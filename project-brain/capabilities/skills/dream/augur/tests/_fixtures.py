"""Shared fixture-builder helpers for the dream skill (ADR-744).

NOT a conftest.py — pytest collapses the name ``tests.conftest`` for every
``tests/`` directory at the project root, so two conftests collide. This
file exposes plain builder functions; each test file declares its own
``@pytest.fixture`` wrapping them.

Per Augur skill-test convention (memory: feedback-skill-test-convention),
test modules under this directory load their target scripts via
`importlib.util.spec_from_file_location`, never via dotted module path. The
builders here are similarly self-contained — they don't import the dream
scripts; they just lay down files the tests will assert against.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc(days_ago: int = 0) -> str:
    """ISO-8601 UTC timestamp `days_ago` days before the test wall-clock."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_fixture_vault(tmp_path: Path) -> Path:
    """Lay down a synthetic vault for dream's aggregator + dead-citation tests.

    Layout produced under ``tmp_path / "vault"``::

        vault/
          wiki/
            wiki-anchor.md          # 5 inbound edges (entity-level), fresh timeline
            wiki-orphan.md          # 0 inbound edges, 1 timeline entry
            wiki-near-duplicate-a.md  # high-similarity twin of -b
            wiki-near-duplicate-b.md
            wiki-stale.md           # timeline fresher than compiled-truth
          source-cards/
            live-card.md            # resolvable source-card://live-card
          notes/
            existing-note.md        # vault://notes/existing-note.md target

    The fixture only writes files; the dream tests load + assert against them.
    """
    vault_root = tmp_path / "vault"
    (vault_root / "wiki").mkdir(parents=True)
    (vault_root / "source-cards").mkdir(parents=True)
    (vault_root / "notes").mkdir(parents=True)
    # The fixture lays wiki/ at the vault root — the "domains" layout. Without
    # this flag brain_layout() defaults to legacy "knowledge" and aggregators
    # look in vault/knowledge/wiki (vault-reorg 2026-06-12 layout trap).
    (vault_root / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")

    # An anchor page with a fresh `## Timeline` and a recently-compiled truth.
    (vault_root / "wiki" / "wiki-anchor.md").write_text(_anchor_page(), encoding="utf-8")

    # An orphan candidate: no inbound edges (recorded in the graph cache below)
    # and a single timeline entry.
    (vault_root / "wiki" / "wiki-orphan.md").write_text(_orphan_page(), encoding="utf-8")

    # Two near-duplicate concept pages — same canonical title under different
    # slugs. The wiki_concept_merge predicate requires ≥3 shared tokens and
    # ≥0.67 Jaccard; sharing the canonical title + alias guarantees both.
    (vault_root / "wiki" / "wiki-near-duplicate-a.md").write_text(
        _near_duplicate_page(
            slug="federated-knowledge-graph",
            title="Federated Knowledge Graph",
            aliases=["federated knowledge graph"],
        ),
        encoding="utf-8",
    )
    (vault_root / "wiki" / "wiki-near-duplicate-b.md").write_text(
        _near_duplicate_page(
            slug="federated-knowledge-graphs",
            title="Federated Knowledge Graph",
            aliases=["federated knowledge graph"],
        ),
        encoding="utf-8",
    )

    # A stale page: compiled-truth older than the newest timeline `_at:`.
    (vault_root / "wiki" / "wiki-stale.md").write_text(_stale_page(), encoding="utf-8")

    # Live source-card target for dead-citation resolution.
    (vault_root / "source-cards" / "live-card.md").write_text(
        "---\nid: live-card\n---\nLive source card body.\n", encoding="utf-8"
    )

    # Live vault://notes/existing-note.md target.
    (vault_root / "notes" / "existing-note.md").write_text(
        "Existing note body.\n", encoding="utf-8"
    )

    return vault_root


def build_fixture_graph_cache(tmp_path: Path) -> Path:
    """Lay down a minimal ADR-738 graph cache for inbound-edge counting.

    Produces ``tmp_path / "cache" / "graph" / "edges.jsonl"`` with edges:

      - 5 inbound edges pointing at `wiki-anchor` (different sources)
      - 0 inbound edges for `wiki-orphan`
      - 1 inbound edge for each near-duplicate (cross-link)

    The cache root is returned so tests can point `get_cache_dir()` at it.
    """
    cache_root = tmp_path / "cache"
    (cache_root / "graph").mkdir(parents=True)
    edges_path = cache_root / "graph" / "edges.jsonl"

    edges = []
    for i in range(5):
        edges.append({"src": f"src-{i}", "dst": "wiki-anchor", "type": "cites"})
    edges.append({"src": "wiki-near-duplicate-b", "dst": "wiki-near-duplicate-a", "type": "mentions"})
    edges.append({"src": "wiki-near-duplicate-a", "dst": "wiki-near-duplicate-b", "type": "mentions"})

    with edges_path.open("w", encoding="utf-8") as fh:
        for edge in edges:
            fh.write(json.dumps(edge) + "\n")

    return cache_root


def _anchor_page() -> str:
    """Wiki page with a fresh timeline + recent compiled truth."""
    return f"""---
slug: wiki-anchor
_last_compiled_at: {_utc(days_ago=1)}
---

# Anchor Concept

## Compiled Truth

A well-anchored concept that other pages cite.

## Timeline

- _at: {_utc(days_ago=2)}  _source: vault://notes/existing-note.md
- _at: {_utc(days_ago=3)}  _source: source-card://live-card
- _at: {_utc(days_ago=5)}  _source: graph://wiki-anchor
"""


def _orphan_page() -> str:
    """Wiki page with 0 inbound edges and 1 timeline entry."""
    return f"""---
slug: wiki-orphan
_last_compiled_at: {_utc(days_ago=10)}
---

# Orphan Concept

## Compiled Truth

A concept nothing else links to.

## Timeline

- _at: {_utc(days_ago=10)}  _source: vault://nonexistent-page.md
"""


def _near_duplicate_page(*, slug: str, title: str, aliases: list[str]) -> str:
    """Near-duplicate concept page (two of these form a merge candidate)."""
    aliases_block = "\naliases:\n" + "\n".join(f"  - {a}" for a in aliases) if aliases else ""
    return f"""---
slug: {slug}
title: {title}{aliases_block}
_last_compiled_at: {_utc(days_ago=2)}
---

# {title}

## Compiled Truth

Concept body for {title}. Highly similar to its twin.

## Timeline

- _at: {_utc(days_ago=2)}  _source: vault://notes/existing-note.md
"""


def _stale_page() -> str:
    """Page whose compiled truth lags the newest timeline `_at:`."""
    return f"""---
slug: wiki-stale
_last_compiled_at: {_utc(days_ago=60)}
---

# Stale Concept

## Compiled Truth

Compiled truth is way out of date relative to the timeline below.

## Timeline

- _at: {_utc(days_ago=1)}  _source: vault://notes/existing-note.md
- _at: {_utc(days_ago=5)}  _source: source-card://live-card
- _at: {_utc(days_ago=40)}  _source: source-card://missing-card
"""
