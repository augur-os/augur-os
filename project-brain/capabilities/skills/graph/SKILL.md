---
name: graph
x-augur-type: skill
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags: [knowledge, graph, retrieval]
description: Typed knowledge graph layer — deterministic, zero-LLM typed-edge
  extraction over the vault. Labels every link (cites, mentions, depends_on, ...)
  as data is written by /ingest, /wiki, /save, /ask, /profile. Per-type
  underscore-prefixed frontmatter link lists (Obsidian-graph-visible) over a
  rebuildable JSONL cache. No database, no model calls. Implements ADR-738.
x-augur-callable: project-brain/capabilities/skills/graph/scripts/graph_ops.py
x-augur-mcp-tools:
  - graph-extract
  - graph-query
  - graph-stats
  - entity-tier-recompute
  - graph-rebuild
x-augur-data-dir: graph
x-augur-config:
  commands:
  - id: graph
    type: workflow
    visibility: dev
    description: Typed knowledge graph CLI — extract, query, stats, rebuild,
      tier-recompute.
    callable: scripts/graph_ops.py
    protocol: guide
---

# graph

Augur's typed knowledge graph. Turns the vault's `[[links]]` into a queryable
map by labeling every connection deterministically — no LLM, no token cost — at
the moment `/ingest`, `/wiki`, `/save`, `/ask`, or `/profile` writes data.

## Standard core

Portable workflow guidance for this capability lives in:

- `markdown-knowledge-graph/typed-link-extraction`

This skill remains the Augur adapter. It owns MCP tools, dashboard/Browse/routine
projection, path-helper access, runtime state, and real-data verification for
Augur.

Three non-negotiable principles, inherited from the gbrain borrow slate:

1. **File-first.** Durable edges live in vault frontmatter; the query cache is
   rebuildable JSONL under `get_cache_dir()/graph/`. `cat edges.jsonl` works.
2. **Zero-LLM.** Extraction is a deterministic rule engine over data the write
   paths already produce. No model calls, ever.
3. **Augment, never replace.** Typed edges sit alongside the untyped
   `RelationshipIndex`; both coexist.

See `docs/superpowers/specs/2026-05-14-typed-knowledge-graph-design.md`.
