---
date: 2026-05-14
status: Draft
adr: ADR-739
deciders:
  - gsannikov
related:
  - ADR-738
  - ADR-742
---

# Hybrid Search with Reciprocal Rank Fusion — Design

> Design spec for **ADR-739**. Companion to the thin index ADR at
> `docs/adrs/ADR-739-hybrid-search-rrf-and-search-mode-tiering.md`.
> The implementation plan derived from this spec lives at
> `docs/superpowers/plans/2026-05-14-hybrid-search-rrf.md`.

## Premise Correction

ADR-739's body states that retrieval "currently performs a mix of **vector** and
keyword retrieval." **This is factually wrong** and the ADR body must be
corrected when `spec_file:` is wired. The verified reality:

- `src/lib/index/` is **ripgrep (full-text) + BM25 (keyword)** — both lexical.
- `get_rag_dir()/_meta/` holds only `bm25_index.json` + `bm25_chunk_map.json`.
- `rag_knowledge.py` sets `"embedding_model": "none"`.
- There is **no vector/embedding retriever** anywhere in `src/` or `shared-vault/`.

Per the design decision on this spec: ADR-739 fuses **the lexical sources Augur
actually has** (ripgrep + BM25, plus the ADR-738 typed graph as a third source).
RRF is provider-agnostic by construction — a vector retriever can be added later
as a fourth source through the same `RetrieverSource` protocol, in its own ADR,
with no refork. ADR-739's "no new retrieval providers" non-goal is *kept honest*:
it adds no retriever, it adds principled fusion over the retrievers that exist.

## Goal

Replace the ad-hoc score-merging in `unified_search.py` (today: a word-overlap
count in `_score_hits` + `_dedup_by_file`) with **Reciprocal Rank Fusion** — the
literature-standard, public, few-dozen-line rank-fusion algorithm. Add three
named **search budgets** so the caller can pick retrieval depth (and downstream
token cost) per situation instead of "always large" or "always small."

## Non-Goals

Corrected from ADR-739 (the "vector provider" references are removed):

- **No new retrieval provider.** RRF fuses the ranked lists Augur's existing
  retrievers already produce. No embedding model, no vector index — that is a
  separate future ADR.
- **No embedded relational/vector database.** RRF is a pure function over ranked
  lists; it needs no index of its own.
- **No replacement of `unified-search` callers.** RRF is internal to the fusion
  step; the tool surface stays backward-compatible (the `budget` param is
  additive and optional).
- **No autonomous budget-switching.** The user (or the active AI client, per Rule
  #11) picks the budget. `search-tune` only *recommends*.

## Architecture

### Placement — `src/lib/index/`, not the `rag` skill

ADR-739's body says "fusion math implemented in `shared-vault/skills/rag/scripts/`."
**This is the wrong home.** The retrieval engine — `unified_search.py`,
`bm25_index.py`, `search_engine.py` — is core shared infrastructure in
`src/lib/index/`, used by the `knowledge`, `rag`, and `ingest` skills alike. If
RRF lived in the `rag` skill, `unified_search.py` (core) would import from a
skill — a dependency inversion. RRF is a core retrieval primitive and lives
beside the engine it serves:

```
src/lib/index/
  unified_search.py     # MODIFIED — fusion step now calls rrf.fuse()
  rrf.py                # NEW — the RRF algorithm + RetrieverSource protocol
  sources.py            # NEW — RipgrepSource, BM25Source (the two core sources)
  bm25_index.py         # unchanged
  search_engine.py      # unchanged
```

### The `RetrieverSource` protocol — the extension seam

```python
class RetrieverSource(Protocol):
    name: str
    def search(self, query: str, *, limit: int) -> list[RankedHit]: ...
```

`RankedHit` is `{doc_id, rank, raw_score, snippet}`. RRF only uses `rank`. Two
core sources ship in `sources.py`: `RipgrepSource` and `BM25Source`. The protocol
*is* the provider-agnosticism — ADR-738's typed graph registers a `GraphSource`,
and a future vector ADR registers a `VectorSource`, both without touching RRF.

### Graph source — coordinated with ADR-738

ADR-739 ships RRF + the protocol + the two core sources. The `GraphSource`
adapter (calling the `graph` skill's `graph-query`) is wired by **whichever of
ADR-738 / ADR-739 lands second** — the protocol is the contract between them. If
ADR-739 lands first, RRF runs over ripgrep + BM25 and `GraphSource` registration
is a no-op until the graph skill exists; the registration is a soft, optional
discovery, so a missing graph skill never breaks search.

## The RRF Algorithm

```
score(doc) = Σ over sources i of  1 / (k + rank_i(doc))
```

- `rank_i(doc)` is the doc's 1-indexed position in source *i*'s ranked list; a
  doc absent from a source contributes nothing for that source.
- `k = 60` — the literature default, configurable in `config/system/search.yaml`.
- Each source returns its top `limit` hits; RRF fuses, sorts by fused score
  descending, returns the top `top_k` for the active budget.
- Deterministic: same query + same source outputs → same fused ranking. This is
  what makes ADR-742's eval harness able to measure RRF as a regression contract.

## Search Budgets

Three named budgets, declared in `config/system/search.yaml`:

| Budget         | top_k | ~token estimate | Use                              |
|----------------|-------|-----------------|----------------------------------|
| `conservative` | 5     | ~4K             | quick lookups, tight context     |
| `balanced`     | 10    | ~10K            | **default**                      |
| `tokenmax`     | 20    | ~20K            | deep questions, wide context     |

**Naming:** these are exposed as a new **`budget`** parameter — *not* `mode`.
`unified-search` already has a `mode` param meaning *retrieval strategy*
(`keyword` / `metadata` / `hybrid` / `iterative`). Budget (depth / token cost)
and mode (strategy) are orthogonal axes; conflating them would repeat the
`_entity_tier`-vs-`wiki_tier` collision ADR-738 had to untangle. So:
`unified-search(query, mode="hybrid", budget="balanced")`.

Budget is selectable via:
- `unified-search` / `memory-search` `budget` argument (default `balanced`)
- `aug unified-search --budget <name>` CLI flag
- the dashboard `/browse` search bar (a budget picker — rides the existing search UI)

## Cost Labels

A display-only affordance. The active profile in `config/system/llm.yaml`
(`active_profile` → `profiles.<name>.provider`) tells whether downstream
reasoning is local (free) or remote (paid). The cost label pairs the budget's
token estimate with that provider class — e.g. `~10K tokens · local` vs
`~20K tokens · remote`. **Display only — never a hard cap.** It informs the
user; it does not gate retrieval.

## `config/system/search.yaml`

New central config (precedent: `config/system/wiki_signals.yaml`,
`config/system/llm.yaml` — system-wide retrieval tuning, not skill-extensible):

```yaml
# Hybrid search — RRF fusion + search budgets (ADR-739)
rrf:
  k: 60                       # RRF constant; literature default
  per_source_limit: 50        # how many hits each source returns before fusion
search_budgets:
  conservative: {top_k: 5,  token_estimate: 4000}
  balanced:     {top_k: 10, token_estimate: 10000}   # default
  tokenmax:     {top_k: 20, token_estimate: 20000}
default_budget: balanced
```

## Surface Integration

RRF is internal to `unified_search.py`'s fusion step — the public surfaces stay
backward-compatible:

- **`unified-search`** (`knowledge` skill MCP tool) — gains the optional `budget`
  param; its existing `mode`/`top_k`/`max_results` params are unchanged. When
  `budget` is given it sets `top_k` from the budget table.
- **`memory-search`** — adopts the same fusion path. The plan verifies whether
  `memory-search` already routes through `unified_search.py` or has its own
  retrieval; either way it ends up fusing via `rrf.fuse()`.
- **`rag` skill** (`search-skill-knowledge`) — same: routes its retrieval through
  the shared `unified_search.py` fusion step.
- **Result shape** — `unified-search` results gain explicit `score` (the fused
  RRF score), `budget`, and `provenance` (which sources ranked the doc) fields.
  ADR-742's eval harness consumes these.

## New MCP Tools

CLI-default per the surface-decision-matrix.

| Tool          | Purpose                                                              |
|---------------|----------------------------------------------------------------------|
| `search-stats`| BM25 index freshness (last rebuild, doc count), per-source hit counts and fusion latency for the last N queries |
| `search-tune` | Recommend a `budget` from simple heuristics (query length, recent result-set sizes) — a recommendation string, never an automatic switch |

`config/system/capability_exposure.yaml` gains `mcp-tool:search-stats` and
`mcp-tool:search-tune` entries.

## Coexistence — what stays unchanged

- `bm25_index.py`, `search_engine.py`, the BM25 index under `get_rag_dir()/_meta/`
  — unchanged. RRF consumes BM25's ranked output; it does not touch how BM25 is
  built.
- Ripgrep full-text search — unchanged; wrapped as `RipgrepSource`.
- `unified-search`'s `mode` param and all existing callers — unchanged.

## Error Handling

- **A source raises or times out** — RRF fuses the sources that *did* return;
  a degraded result beats no result. The failure is logged at WARN and surfaced
  in the result's `provenance` (the missing source is simply absent).
- **A source returns nothing** — contributes nothing to any doc's fused score;
  not an error.
- **Unknown `budget` value** — falls back to `default_budget` with a WARN; never
  raises into a caller.
- **Malformed `search.yaml`** — fails closed to built-in defaults (`k=60`, the
  three budgets above), same fail-closed pattern as ADR-738's rule engine.

## Testing Strategy

RRF and sources are core lib → tests live in `tests/lib/index/` (the existing
core test location), standard `pytest` import (not the skill importlib
convention — this is `src/`, not a skill). TDD per the writing-plans skill:

- `test_rrf.py` — the fusion formula at known inputs (a doc ranked #1 in two
  sources beats a doc ranked #1 in one); `k` sensitivity; a doc absent from a
  source; empty-source handling; determinism
- `test_sources.py` — `RipgrepSource` and `BM25Source` conform to the
  `RetrieverSource` protocol and return well-formed `RankedHit`s
- `test_unified_search_fusion.py` — `unified_search.py` now fuses via RRF;
  `budget` sets `top_k`; result shape carries `score` / `budget` / `provenance`;
  a failing source degrades gracefully; backward compatibility — an old call
  with no `budget` still works

## Implementation Order

1. **RRF core + protocol** — `src/lib/index/rrf.py` (`fuse()` + `RetrieverSource`
   protocol + `RankedHit`).
2. **Core sources** — `src/lib/index/sources.py` (`RipgrepSource`, `BM25Source`
   wrapping the existing ripgrep + BM25 paths).
3. **Config** — `config/system/search.yaml` + a fail-closed loader.
4. **Fusion integration** — modify `unified_search.py` so its combine step calls
   `rrf.fuse()` over the registered sources; thread the `budget` param.
5. **Surface params** — add `budget` to `unified-search` / `memory-search` /
   the `rag` skill search path; add `score` / `budget` / `provenance` to the
   result shape.
6. **New MCP tools** — `search-stats`, `search-tune` + `capability_exposure.yaml`.
7. **Docs** — update the retrieval section of the relevant topic doc; regenerate
   agent instructions via `sync_agents`. Correct the ADR-739 body's "vector"
   premise when wiring `spec_file:`.

Phases 1–4 are a sequential pipeline. Phases 5–6 touch the MCP tool files
(sequential, shared files). Phase 7 is docs + the ADR body correction.

## Consequences

- New `src/lib/index/rrf.py` + `src/lib/index/sources.py`; `unified_search.py`'s
  combine step rewritten to fuse via RRF.
- New `config/system/search.yaml`.
- `unified-search` / `memory-search` results gain `score` / `budget` /
  `provenance` — consumed by ADR-742's eval harness as the regression contract.
- The `RetrieverSource` protocol is the seam: ADR-738's typed graph plugs in as a
  third source; a future vector-retriever ADR plugs in as a fourth — neither
  needs RRF to change.
- ADR-739's body is corrected: the "vector + keyword" premise and the "existing
  vector provider" non-goal reference are wrong and removed.
- No new database, no new retriever, no token cost — RRF is pure fusion math.
