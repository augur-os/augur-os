---
date: 2026-05-14
status: Draft
adr: ADR-738
deciders:
  - gsannikov
related:
  - ADR-571
  - ADR-731
  - ADR-739
  - ADR-740
  - ADR-742
---

# Typed Knowledge Graph Layer and Entity Tiering — Design

> Design spec for **ADR-738**. Companion to the thin index ADR at
> `docs/adrs/ADR-738-typed-knowledge-graph-and-entity-tiering.md`.
> The implementation plan derived from this spec lives at
> `docs/superpowers/plans/2026-05-14-typed-knowledge-graph.md`.

## Goal

Add a deterministic, **zero-LLM** typed-edge layer over the Augur vault. A link
from page A to page B today says nothing about *why* they relate. Typed edges
(`cites`, `mentions`, `depends_on`, `supersedes`, …) make precision queries
possible — "what cites this source?", "what does this skill depend on?" — that
vector search alone cannot answer. Entity tiering (1–3) ranks how
well-connected each entity is, so downstream consumers can prioritize.

This borrows the **pattern** from gbrain (typed, deterministic, write-time edge
extraction with no token cost), not its domain schema.

## Non-Goals

Carried verbatim from ADR-738, reaffirmed:

- **No LLM-based extraction.** Determinism and zero token cost are the point.
- **No graph database.** No Neo4j, no SQLite graph extensions, no embedded store.
- **No replacement of untyped `[[wikilinks]]` discovery.** Typed edges *augment*
  the existing `RelationshipIndex`; both coexist.
- **No cross-vault federation.** Local vault only.
- No new authoring burden — edges derive from data the user's commands already
  produce. Hand-authoring an edge is *possible* (see Storage Model) but never
  *required*.

## How Your Data Creates Edges

The vault is filled by five commands. The graph is wired into each one's write
path, so edges appear as a natural by-product of normal use — not from a
separate scanner the user has to remember to run.

| You run…                  | Augur writes…                              | Typed edges emitted                                                                 |
|----------------------------|--------------------------------------------|-------------------------------------------------------------------------------------|
| `/ingest <url>`            | source card in `vault/sources/urls/`       | `_mentions:` → concepts the page is about · `_authored_by:` → author when captured   |
| `/ingest folder`           | source cards in `vault/sources/files/`     | `_mentions:` → extracted concepts · `_relates_to:` → sources sharing tags            |
| `/wiki`                    | concept pages in `vault/wiki/concepts/`    | `_relates_to:` / `_part_of:` / `_depends_on:` from `[[wikilinks]]` — the graph backbone |
| `/save <note>`             | note / asset in a skill-owned location     | markdown note → edges from its `[[wikilinks]]` & frontmatter · asset → a citable node |
| `/ask … (retain)`          | memory entry in `vault/memory/entries/`    | `_cites:` → the sources the answer drew on · `_relates_to:` → concepts in the question |
| `/profile`                 | voice profile in `vault/profile/<lang>/`   | the "you" hub — the anchor every `_authored_by:` edge resolves to                    |

Memory entries in `vault/memory/entries/` have a **second trigger**: besides
retained `/ask` answers, the automatic daily-log → persistent-memory curation
cycle writes the same file shape. Both go through the same extractor.

**The compounding loop.** `/ingest` brings in raw sources and the graph labels
what they mention; `/wiki` compounds those into a `[[wikilink]]`-rich concept
backbone. `/save`, retained `/ask` answers, and `/profile` add the user's own
synthesis and identity on top, labeled the same way. `/ask` then *reads* the
labeled map for sharper retrieval (ADR-739), and its retained answers feed back
in. Today these commands pile data up; the typed graph makes them compound.

`/save` is the lightest-touch of the five: it places files into skill-owned
locations. When the saved file is a markdown note it goes through the same
extractor as any vault write; when it's a binary asset it simply becomes a node
other notes can `_cites:`.

## Architecture

### Placement — new `graph/` skill

The typed-edge layer is a **substrate** consumed by ADR-739 (search), ADR-740
(timeline citations), and ADR-744 (dream cycle). Burying a shared substrate
inside `ingest` would make `ingest` a hidden dependency hub; putting it in
`knowledge` would force `ingest` to depend on `knowledge` for write-time
extraction. A standalone skill gives it a clean owner and its own MCP namespace.

```
shared-vault/skills/graph/
  SKILL.md
  augur.yaml                 # hub: brain; capabilities; actions
  scripts/
    __init__.py
    edge_rules.py            # loads graph_edges.yaml; the deterministic rule engine
    edge_extractor.py        # extract(path, known=...) -> list[Edge]; no LLM
    edge_writer.py           # merges edges into per-type frontmatter keys (ADR-571)
    graph_cache.py           # read/write edges.jsonl + entities.jsonl + meta.json
    entity_tier.py           # compute_tier(entity) from inbound count + source diversity
    graph_query.py           # query layer over the cache (by type, entity, neighbors)
    graph_rebuild.py         # one-shot full-vault backfill; idempotent
    mcp/
      __init__.py
      graph_tools.py         # graph-extract, graph-query, graph-stats,
                             # entity-tier-recompute, graph-rebuild
  augur/
    tests/                   # per Augur skill-test convention (importlib spec)
      test_edge_rules.py
      test_edge_extractor.py
      test_edge_writer.py
      test_graph_cache.py
      test_entity_tier.py
      test_graph_query.py
      test_graph_rebuild.py
```

New central config: `config/system/graph_edges.yaml` (precedent:
`config/system/wiki_signals.yaml`). Edge types are extensible by **users and
multiple skills**, not owned by the graph skill alone — `config/system/` is the
correct home, consistent with ADR-738's stated choice.

### The rule engine — deterministic typed extraction

Edges derive from data the `/ingest`, `/save`, `/ask` writers **already
produce**. `graph_edges.yaml` declares each edge type plus the deterministic
rule(s) that produce it. Three rule kinds, ordered by how much of the real vault
they cover:

1. **Frontmatter-key rules** *(primary — covers machine-written data)* — map a
   frontmatter key the writers already emit to a typed edge. The vault's source
   cards and memory entries are frontmatter-rich (`source_type`, `tags`,
   `route`, `originSessionId`, `content_hash`, `canonical_url`), so this is
   where most edges come from. Examples: a source card's extracted-concepts
   list → `_mentions:`; a retained `/ask` answer's cited-sources list →
   `_cites:`; URL metadata author → `_authored_by:`.
2. **Concept-extraction hook** *(covers `/ingest`)* — `/ingest` already runs
   `wiki_concept_extraction` to pull concepts out of a source and
   `wiki_concept_links` to resolve them to concept pages. The graph extractor
   **consumes that result directly** (passed in as `known=`) rather than
   re-parsing the body — one extraction path, not two — and emits `_mentions:`
   edges to the resolved concept pages.
3. **Body wikilink rules** *(covers hand-written notes & wiki concept pages)* —
   for content that *does* use `[[wikilinks]]`: links under a `## Depends on`
   heading → `_depends_on:`, under `## Sources` → `_cites:`, bare links →
   `_mentions:` (the typed fallback).

Any `[[wikilink]]` matching no rule still becomes a `_mentions:` edge — so the
typed layer is a strict **superset** of today's untyped `RelationshipIndex`:
nothing the old index surfaced is lost.

### Seed edge schema

`config/system/graph_edges.yaml` ships an Augur-native seed set — edges that
match what the vault actually contains. Each row names the real flow that
produces it:

| Edge type     | Connects                       | Produced by (real flow)                                  |
|---------------|--------------------------------|----------------------------------------------------------|
| `mentions`    | any → concept (typed fallback) | `/ingest` concept extraction; unmatched `[[wikilinks]]`   |
| `cites`       | note/answer → source           | retained `/ask` answers; `## Sources` headings            |
| `authored_by` | source → person                | `/ingest` URL metadata                                    |
| `relates_to`  | concept ↔ concept              | `/wiki` concept pages; shared tags; frontmatter `related:` |
| `depends_on`  | skill/ADR → skill/ADR          | `## Depends on` headings; inline frontmatter keys          |
| `part_of`     | sub-concept → parent           | `/wiki` concept hierarchy; heading scope                  |
| `supersedes`  | ADR/page → ADR/page            | frontmatter `superseded_by:`                              |

Users and skills append domain edges (e.g. `works_at`, `invested_in`) to the
same file; the rule engine has no hard-coded edge names.

## Storage Model — per-type frontmatter link lists

Each edge type is its **own frontmatter key**, underscore-prefixed (so it is
system-managed per ADR-571), with a value that is a **list of `[[wikilinks]]`**.
This shape is what makes the typed graph visible to Obsidian (see next section).

```yaml
# vault/sources/urls/2026-05-14-reciprocal-rank-fusion.md  (a /ingest source card)
---
title: Reciprocal Rank Fusion (paper)
source_type: url
canonical_url: https://example.org/rrf
tags: [inbox, sources-urls]
_cites: ["[[RRF original paper]]"]
_authored_by: ["[[Cormack]]"]
_mentions: ["[[hybrid search]]", "[[BM25]]"]
_entity_tier: 2
---
```

**System-merged, not system-overwritten.** The `_`-prefix means the graph skill
*manages* these keys, but the writer is **additive**: `edge_writer.py` unions
freshly extracted edges with whatever is already in the key and dedupes. A link
the user hand-adds via Obsidian's Properties panel is preserved; the extractor
never deletes a user's edge. Only `graph-rebuild --prune` removes edges whose
rule no longer matches, and it emits a diff first. `_entity_tier` is the one
purely-derived key — fully system-owned, never hand-edited.

## Obsidian Integration

`get_vault_dir()` **is** the Obsidian vault (per ADR-270 / the obsidian vault
adapter). Three honest facts about how these keys land in Obsidian:

- **Properties panel** — Obsidian renders frontmatter as the Properties table at
  the top of every note. Each edge type shows as its own row (`_cites`,
  `_mentions`, …), each a clickable list of links. `_entity_tier` shows as a
  number. The user sees and can navigate the typed edges directly.
- **Native graph view** — Obsidian's graph draws *lines, not labeled lines* (it
  is untyped by design). Because the edge values are link lists, Obsidian's
  "show frontmatter links" *does* render them as graph edges — so the typed
  edges **appear in the native graph**, just drawn the same as `[[wikilinks]]`.
  The per-type-key storage model is what buys this; a single nested `_edges:`
  blob would have been invisible here.
- **Plugins** — to *see the types* (colored, labeled, navigable hierarchies) the
  user adds **Breadcrumbs** or **Juggl**, both of which read typed relationships
  straight from per-type frontmatter keys. **Dataview** queries them natively
  (`FROM "" WHERE _entity_tier = 1`). No plugin is required for the graph to
  *work* — they only make the *types* visible inside Obsidian.

Augur owns no Obsidian plugin config; it only writes frontmatter in a shape that
the native client and the common graph plugins already understand.

## Data Shapes

### Durable — vault frontmatter (ADR-571)

Per-type underscore-prefixed keys, written via `merge_system_user()` so user
keys are never clobbered (see Storage Model for the additive-merge rule):

```yaml
_mentions: ["[[hybrid search]]", "[[BM25]]"]
_cites: ["[[RRF original paper]]"]
_authored_by: ["[[Cormack]]"]
_entity_tier: 2
```

### Derived — rebuildable cache under `get_cache_dir()/graph/`

| File             | One record per line                                                          |
|------------------|------------------------------------------------------------------------------|
| `edges.jsonl`    | `{"src": "...", "dst": "...", "type": "mentions", "source_page": "..."}`      |
| `entities.jsonl` | `{"id": "...", "tier": 2, "inbound_count": 7, "source_types": ["url","memory"]}` |
| `meta.json`      | last rebuild time, cache key (git head + fs mtime), edge/entity counts        |

The cache is fully rebuildable from frontmatter at any time; deleting it loses
nothing. `cat edges.jsonl` shows the whole graph — file-first, transparent.

## Entity Tiering

`_entity_tier` (integer 1–3) is named **distinctly** from the existing
`wiki_tier.py` signal-source tiers (`critical`/`high`/`medium`/`low`/`noise`) —
the two are different concepts and must not collide. Computed deterministically
from the cache:

- **Tier 1** — ≥10 inbound mentions across ≥3 source types
- **Tier 2** — ≥3 inbound mentions
- **Tier 3** — everything else

"Source type" = the kind of page an inbound edge originates from (`url`, `file`,
`memory`, `concept`, `adr`, …), taken from the source page's `source_type` /
`_page_type` frontmatter. Thresholds live in `graph_edges.yaml` under a `tiers:`
block so they are tunable without code changes.

## Write-Path Integration

This is the heart of the design — the graph is **not** a passive scanner bolted
on afterward. The `graph/` skill exposes three library entry points:

- `edge_extractor.extract(path, known=…)` — returns typed edges for one page;
  `known=` lets a caller pass structured data it already has (e.g. `/ingest`'s
  concept-extraction result) so the extractor does not re-derive it.
- `edge_writer.merge(path, edges)` — additively merges edges into the page's
  per-type frontmatter keys.
- `graph_cache.update(path, edges)` — updates the JSONL cache for one page.

The five data-producing commands call them at write time:

- **`/ingest`** — `inbox_consume` / `url_ingest` already run concept extraction.
  After `write_vault_frontmatter` / `write_url_source_card`, they call
  `extract(path, known=<concepts>)` → `merge` → `cache.update`. Edges are emitted
  in the same transaction that creates the source card.
- **`/wiki`** — the rag-skill wiki writers (`wiki_concept_pages` and friends)
  call extract → merge → cache after writing a concept page. Wiki pages are
  `[[wikilink]]`-rich, so this is where rule kind 3 produces the most edges.
- **`/ask` retention** — `ask_sync` writes a memory entry knowing which sources
  the answer cited. It passes those as `known=` so `_cites:` is exact, not
  guessed. The daily-log → persistent-memory curation cycle writes the same
  memory-entry shape and goes through the identical path.
- **`/save`** — for markdown saves, the save flow calls the same extract → merge
  → cache sequence; for asset saves, no edges are emitted (the asset is a node,
  not an edge source).
- **`/profile`** — `profile-write` calls extract → merge → cache so the profile
  note is a first-class node. It rarely emits outbound edges, but it is the
  resolution target for `_authored_by:` across the vault.

A standalone `graph-extract` MCP tool / CLI covers manual and ad-hoc runs; it is
the *repair* path, not the primary one.

## Backfill

`graph-rebuild` performs a one-shot full-vault scan: extract edges for every
page, merge `_<type>:` / `_entity_tier:` frontmatter, build the cache. Because
extraction is zero-LLM and deterministic it is safe to run across the entire
vault. The operation is **idempotent** and emits a diff for review before
frontmatter is written. `--prune` additionally removes edges whose rule no
longer matches. Run once at rollout; the dream cycle (ADR-744) keeps tiers fresh
afterward via `entity-tier-recompute`.

## MCP Tools

CLI-default per the surface-decision-matrix; `graph-stats` and `graph-query` may
opt into MCP-via-dashboard later when a dashboard card justifies it.

| Tool                   | Purpose                                              |
|------------------------|------------------------------------------------------|
| `graph-extract`        | Run the extractor over a path (or the vault)         |
| `graph-query`          | Query edges: by type, by entity, neighbors           |
| `graph-stats`          | Edge/entity counts, tier distribution, dangling edges|
| `entity-tier-recompute`| Recompute `_entity_tier` across all entities         |
| `graph-rebuild`        | One-shot full-vault backfill (see above)             |

`config/system/capability_exposure.yaml` gains `mcp-tool:graph-*` entries.

## Superseding the `knowledge-graph` Stub

The existing `knowledge-graph` MCP tool (in the `knowledge` skill,
`scripts/mcp/rag_search.py`) is a stats-only stub — it reads the RAG manifest
and returns counts, with the body comment *"Relationship index available via
project-index."* Per Rule #14 (prefer canonical cleanup over compatibility
shims): `graph-stats` becomes the real owner of graph statistics, and
`knowledge-graph` is deprecated with its capability entry pointing at
`graph-stats`. No long-lived alias shim.

## Coexistence with `RelationshipIndex`

`src/lib/relationship_index.py` (untyped, core lib) stays unchanged — no caller
changes, no breaking change. The two indexes are deliberately parallel: the
typed extractor parses wikilinks **per page** (the write path indexes one page
that was just written, not the whole vault, so a vault-wide `build()` is the
wrong shape there), while `RelationshipIndex` remains the vault-wide untyped
index. `graph-rebuild` MAY cross-check its edge set against
`RelationshipIndex.as_records()` as a consistency probe, but the live write path
does not depend on it. The typed layer is still a strict superset of the untyped
one — every `[[wikilink]]` becomes at least a `mentions` edge.

## Error Handling

- **Malformed `graph_edges.yaml`** — the rule engine fails closed: log a clear
  error, fall back to `mentions`-only extraction (still a superset of today's
  behavior), never crash an `/ingest` or `/save` write.
- **Unwritable frontmatter** (permissions, locked file) — skip that page, record
  it in the rebuild diff, continue. A partial graph is acceptable; a failed
  write is not silently swallowed.
- **Stale cache** (cache key mismatch on read) — `graph-query` rebuilds the
  affected slice transparently; the cache is never trusted blindly.
- **Dangling edge targets** (`[[link]]` to a non-existent page) — kept as an
  edge, flagged by `graph-stats`; ADR-744's dream cycle dead-citation phase
  surfaces them for review. Not auto-deleted.
- **User-added edge vs. extractor** — the additive merge means the two never
  fight; a user edge with no matching rule simply survives every non-`--prune`
  run.

## Testing Strategy

Tests live in `shared-vault/skills/graph/augur/tests/`, imported via
`importlib.util.spec_from_file_location` per the Augur skill-test convention
(never dotted module path). TDD per the writing-plans skill — one focused test
file per unit:

- `test_edge_rules.py` — YAML parsing, the three rule kinds, malformed-config fallback
- `test_edge_extractor.py` — each rule kind against fixture pages; `known=` pass-through; `mentions` fallback; superset property vs. `RelationshipIndex`
- `test_edge_writer.py` — additive merge, dedupe, user-added edge preservation, `--prune` removal
- `test_graph_cache.py` — JSONL round-trip, rebuild-from-frontmatter, cache-key invalidation
- `test_entity_tier.py` — the three tier thresholds at boundaries; source-type diversity counting
- `test_graph_query.py` — by-type, by-entity, neighbor queries; dangling targets
- `test_graph_rebuild.py` — idempotence, diff output, `--prune`, partial-failure handling

Fixture pages mirror real shapes: a `/ingest` URL source card, a `/ingest` file
source card, a `/wiki` concept page, an `/ask` memory entry, and a `/profile`
note.

## Implementation Order

A near-linear pipeline; limited parallel fan-out.

1. **Config + rule engine** — `config/system/graph_edges.yaml` (seed schema +
   `tiers:` block) and `edge_rules.py`.
2. **Extractor + writer + cache** — `edge_extractor.py`, `edge_writer.py`
   (additive per-type-key merge), `graph_cache.py`.
3. **Entity tiering** — `entity_tier.py`; `_entity_tier:` frontmatter write.
4. **Query layer + MCP tools** — `graph_query.py`, `mcp/graph_tools.py`;
   `capability_exposure.yaml` entries.
5. **Write-path integration** — wire the five data-producing write paths to call
   extract → merge → cache, passing `known=` where the caller already has it:
   `/ingest` (`inbox_consume`, `url_ingest`), `/wiki` (rag-skill concept-page
   writers), `/ask` retention + daily-log curation (`ask_sync` and the curation
   cycle), `/save` markdown writes, and `/profile` (`profile-write`).
6. **Backfill** — `graph_rebuild.py`; one-shot vault backfill, idempotent,
   `--prune`, diff.
7. **Supersede the stub + docs** — deprecate `knowledge-graph`, update
   `docs/agent-topics/SKILLS.md` with the typed-edge + per-type-key convention,
   regenerate agent instructions via `sync_agents`.

Phases 1–4 are a sequential pipeline (rules → extractor/writer → tiering →
query). Phases 5–7 each touch shared files (the `/ingest`+`/ask`+`/save` write
paths, central config, docs) and stay sequential — do not force parallelism
where it costs correctness.

## Consequences

- New skill `shared-vault/skills/graph/` with rule engine, extractor, writer,
  cache, tiering, query, MCP tools, and tests.
- Source cards and memory entries gain per-type `_<edge>:` keys and
  `_entity_tier:` — visible in Obsidian's Properties panel and native graph
  view, queryable by Dataview, typed-navigable via Breadcrumbs/Juggl.
- New central config `config/system/graph_edges.yaml`.
- The five write paths (`/ingest`, `/wiki`, `/save`, `/ask` retention +
  daily-log curation, `/profile`) gain an extract → merge → cache step
  (deterministic, in-process, zero token cost).
- `unified-search` (ADR-739) can boost Tier-1 entities and add the graph as a
  third RRF retrieval source; the dream cycle (ADR-744) can prioritize Tier-1
  refresh; the timeline (ADR-740) can cite typed edges.
- The retrieval eval harness (ADR-742) gains a graph-query benchmark axis.
- `knowledge-graph` MCP stub deprecated in favor of `graph-stats`.
