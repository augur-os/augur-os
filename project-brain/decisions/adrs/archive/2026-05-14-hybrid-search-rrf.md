# Hybrid Search with RRF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad-hoc score-merging in `unified_search.py` with Reciprocal Rank Fusion over the lexical sources Augur actually has (ripgrep + BM25), behind a `RetrieverSource` protocol so ADR-738's graph and a future vector retriever slot in without a refork. Add three named search budgets (`conservative`/`balanced`/`tokenmax`).

**Architecture:** `src/lib/index/rrf.py` holds the RRF algorithm + `RetrieverSource` protocol + `RankedHit`. `src/lib/index/sources.py` holds `RipgrepSource` and `BM25Source`. `src/lib/index/unified_search.py`'s combine step is rewritten to fuse via `rrf.fuse()`. `config/system/search.yaml` holds the RRF `k` and the budget table; `src/lib/index/search_config.py` is its fail-closed loader.

**Tech Stack:** Python 3.11+, `src/lib/index/` (core retrieval lib), the existing `BM25Index` + ripgrep paths. No new dependencies. No vector retriever, no database — RRF is pure fusion math over ranked lists.

**Spec:** `docs/superpowers/specs/2026-05-14-hybrid-search-rrf-design.md` · **ADR:** ADR-739

---

## Test Convention

RRF, sources, and the config loader are **core lib**, not a skill — tests live in
`tests/lib/index/` with **standard pytest imports** (`from src.lib.index.rrf import ...`),
not the skill importlib convention. Run with `/auto-test-pytest tests/lib/index/`
(never raw `pytest` — rule 29).

---

# Phase 1 — RRF Core + Protocol

## Task 1: `rrf.py` — RankedHit, RetrieverSource, fuse()

**Files:**
- Create: `src/lib/index/rrf.py`
- Test: `tests/lib/index/test_rrf.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for src/lib/index/rrf.py — Reciprocal Rank Fusion (ADR-739)."""
from __future__ import annotations

from src.lib.index.rrf import RankedHit, RetrieverSource, fuse


def test_doc_ranked_high_in_two_sources_beats_one() -> None:
    a = [RankedHit("doc-A", 1, 9.0), RankedHit("doc-B", 2, 8.0)]
    b = [RankedHit("doc-A", 1, 0.9), RankedHit("doc-C", 2, 0.8)]
    fused = fuse({"ripgrep": a, "bm25": b}, k=60, top_k=10)
    assert fused[0]["doc_id"] == "doc-A"                       # ranked #1 in both
    assert sorted(fused[0]["provenance"]) == ["bm25", "ripgrep"]
    # doc-A score = 1/61 + 1/61; doc-B = 1/62; doc-C = 1/62
    assert fused[0]["score"] > fused[1]["score"]


def test_absent_doc_contributes_nothing_and_k_is_configurable() -> None:
    a = [RankedHit("doc-A", 1, 1.0)]
    # doc-A only in source a; score = 1/(k+1)
    assert fuse({"a": a}, k=60, top_k=5)[0]["score"] == round(1 / 61, 6)
    assert fuse({"a": a}, k=10, top_k=5)[0]["score"] == round(1 / 11, 6)


def test_empty_sources_and_determinism() -> None:
    assert fuse({}, k=60, top_k=5) == []
    assert fuse({"a": []}, k=60, top_k=5) == []
    a = [RankedHit("d1", 1, 1.0), RankedHit("d2", 2, 0.5)]
    assert fuse({"a": a}, k=60, top_k=5) == fuse({"a": a}, k=60, top_k=5)


def test_ripgrep_source_satisfies_protocol() -> None:
    class _Stub:
        name = "stub"
        def search(self, query: str, *, limit: int) -> list[RankedHit]:
            return []
    assert isinstance(_Stub(), RetrieverSource)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/lib/index/test_rrf.py`
Expected: FAIL — `src/lib/index/rrf.py` does not exist.

- [ ] **Step 3: Write `rrf.py`**

```python
"""Reciprocal Rank Fusion for hybrid search (ADR-739).

score(doc) = Σ over sources of 1 / (k + rank_i(doc)). Pure function over ranked
lists — no index, no state, no model call. The RetrieverSource protocol is the
extension seam: ripgrep + BM25 ship here; ADR-738's graph and a future vector
retriever register through the same protocol with no refork.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RankedHit:
    """One hit from a retriever, with its 1-indexed rank in that retriever's list."""

    doc_id: str
    rank: int
    raw_score: float = 0.0
    snippet: str = ""


@runtime_checkable
class RetrieverSource(Protocol):
    """A named retriever that returns ranked hits for a query."""

    name: str

    def search(self, query: str, *, limit: int) -> list[RankedHit]: ...


def fuse(
    ranked_lists: dict[str, list[RankedHit]], *, k: int = 60, top_k: int = 10
) -> list[dict]:
    """Fuse per-source ranked lists via RRF; return the top_k fused results.

    Each result: {doc_id, score, provenance: [source, ...], snippet}.
    Deterministic given the same inputs.
    """
    scores: dict[str, float] = {}
    provenance: dict[str, list[str]] = {}
    snippets: dict[str, str] = {}
    for source_name, hits in sorted(ranked_lists.items()):
        for hit in hits:
            scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + 1.0 / (k + hit.rank)
            provenance.setdefault(hit.doc_id, []).append(source_name)
            snippets.setdefault(hit.doc_id, hit.snippet)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "doc_id": doc_id,
            "score": round(score, 6),
            "provenance": sorted(provenance[doc_id]),
            "snippet": snippets.get(doc_id, ""),
        }
        for doc_id, score in ranked[:top_k]
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/lib/index/test_rrf.py`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/index/rrf.py tests/lib/index/test_rrf.py
git commit -m "feat(search): RRF fusion + RetrieverSource protocol (ADR-739)"
```

## Task 2: `config/system/search.yaml` + `search_config.py` loader

**Files:**
- Create: `config/system/search.yaml`
- Create: `src/lib/index/search_config.py`
- Test: `tests/lib/index/test_search_config.py`

- [ ] **Step 1: Write `config/system/search.yaml`**

```yaml
# Hybrid search — RRF fusion + search budgets (ADR-739)
rrf:
  k: 60                       # RRF constant; literature default
  per_source_limit: 50        # hits each source returns before fusion
search_budgets:
  conservative: {top_k: 5,  token_estimate: 4000}
  balanced:     {top_k: 10, token_estimate: 10000}
  tokenmax:     {top_k: 20, token_estimate: 20000}
default_budget: balanced
```

- [ ] **Step 2: Write the failing test**

```python
"""Tests for src/lib/index/search_config.py (ADR-739)."""
from __future__ import annotations

from pathlib import Path

from src.lib.index import search_config


def test_load_real_config_has_budgets() -> None:
    cfg = search_config.load_search_config()
    assert cfg["rrf"]["k"] == 60
    assert set(cfg["search_budgets"]) == {"conservative", "balanced", "tokenmax"}


def test_budget_top_k_resolves_and_falls_back() -> None:
    cfg = search_config.load_search_config()
    assert search_config.budget_top_k(cfg, "conservative") == 5
    assert search_config.budget_top_k(cfg, "tokenmax") == 20
    assert search_config.budget_top_k(cfg, None) == 10           # default_budget
    assert search_config.budget_top_k(cfg, "bogus") == 10        # unknown -> default


def test_malformed_config_fails_closed(tmp_path: Path, monkeypatch) -> None:
    bad = tmp_path / "search.yaml"
    bad.write_text("rrf: [not a mapping", encoding="utf-8")
    monkeypatch.setattr(search_config, "_config_path", lambda: bad)
    cfg = search_config.load_search_config()                     # must not raise
    assert cfg["rrf"]["k"] == 60                                 # built-in defaults
    assert cfg["default_budget"] == "balanced"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/auto-test-pytest tests/lib/index/test_search_config.py`
Expected: FAIL — `search_config.py` does not exist.

- [ ] **Step 4: Write `search_config.py`**

```python
"""Loader for config/system/search.yaml — RRF k + search budgets (ADR-739).

Fails closed: a malformed config never raises into a search call — it falls back
to built-in defaults.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("index.search_config")

_DEFAULTS: dict[str, Any] = {
    "rrf": {"k": 60, "per_source_limit": 50},
    "search_budgets": {
        "conservative": {"top_k": 5, "token_estimate": 4000},
        "balanced": {"top_k": 10, "token_estimate": 10000},
        "tokenmax": {"top_k": 20, "token_estimate": 20000},
    },
    "default_budget": "balanced",
}


def _config_path() -> Path:
    """Path to config/system/search.yaml. Monkeypatchable in tests."""
    from src.config.paths import get_project_root

    return get_project_root() / "config" / "system" / "search.yaml"


def load_search_config() -> dict[str, Any]:
    """Load search.yaml merged over built-in defaults. Fails closed."""
    cfg: dict[str, Any] = {
        "rrf": dict(_DEFAULTS["rrf"]),
        "search_budgets": {k: dict(v) for k, v in _DEFAULTS["search_budgets"].items()},
        "default_budget": _DEFAULTS["default_budget"],
    }
    try:
        data = yaml.safe_load(_config_path().read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            if isinstance(data.get("rrf"), dict):
                cfg["rrf"].update(data["rrf"])
            if isinstance(data.get("search_budgets"), dict):
                for name, spec in data["search_budgets"].items():
                    if isinstance(spec, dict):
                        cfg["search_budgets"][name] = spec
            if data.get("default_budget") in cfg["search_budgets"]:
                cfg["default_budget"] = data["default_budget"]
    except Exception as exc:  # noqa: BLE001 — fail closed to defaults
        logger.warning("search.yaml unusable (%s); using built-in defaults", exc)
    return cfg


def budget_top_k(cfg: dict[str, Any], budget: str | None) -> int:
    """Resolve a budget name to its top_k, falling back to default_budget."""
    budgets = cfg["search_budgets"]
    name = budget if budget in budgets else cfg["default_budget"]
    return int(budgets[name]["top_k"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest tests/lib/index/test_search_config.py`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add config/system/search.yaml src/lib/index/search_config.py tests/lib/index/test_search_config.py
git commit -m "feat(search): search.yaml + fail-closed config loader (ADR-739)"
```

---

# Phase 2 — Core Sources

## Task 3: `sources.py` — RipgrepSource + BM25Source

**Files:**
- Create: `src/lib/index/sources.py`
- Test: `tests/lib/index/test_sources.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for src/lib/index/sources.py — core RetrieverSources (ADR-739)."""
from __future__ import annotations

from src.lib.index.rrf import RankedHit, RetrieverSource
from src.lib.index.sources import BM25Source


class _FakeBM25:
    def query(self, query: str, top_k: int = 50) -> list[dict]:
        return [
            {"path": "doc-A.md", "score": 9.1, "meta": {}},
            {"path": "doc-B.md", "score": 4.2, "meta": {}},
        ][:top_k]


def test_bm25_source_conforms_and_ranks_1_indexed() -> None:
    src = BM25Source(_FakeBM25())
    assert isinstance(src, RetrieverSource)
    assert src.name == "bm25"
    hits = src.search("anything", limit=10)
    assert [(h.doc_id, h.rank) for h in hits] == [("doc-A.md", 1), ("doc-B.md", 2)]
    assert all(isinstance(h, RankedHit) for h in hits)


def test_bm25_source_with_no_index_returns_empty() -> None:
    assert BM25Source(None).search("anything", limit=10) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/lib/index/test_sources.py`
Expected: FAIL — `src/lib/index/sources.py` does not exist.

- [ ] **Step 3: Write `sources.py`**

```python
"""Core RetrieverSource implementations for RRF fusion (ADR-739).

BM25Source wraps the existing BM25Index; RipgrepSource wraps the existing
ripgrep hit-collection path in unified_search.py. Both convert their native hits
into 1-indexed RankedHit lists for rrf.fuse().
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.lib.index.rrf import RankedHit


class BM25Source:
    """RetrieverSource over the existing BM25Index."""

    name = "bm25"

    def __init__(self, bm25_index: Any | None) -> None:
        self._index = bm25_index

    def search(self, query: str, *, limit: int) -> list[RankedHit]:
        if self._index is None or not query.strip():
            return []
        hits = self._index.query(query, top_k=limit)
        return [
            RankedHit(
                doc_id=str(hit.get("path", "")),
                rank=i + 1,
                raw_score=float(hit.get("score", 0.0)),
                snippet=str(hit.get("meta", {}).get("snippet", "")),
            )
            for i, hit in enumerate(hits)
            if hit.get("path")
        ]


class RipgrepSource:
    """RetrieverSource over the existing ripgrep full-text path.

    Wraps unified_search.py's `_collect_active_search_hits` + `_score_hits` +
    `_dedup_by_file` — it does not reimplement ripgrep collection, it adapts it.
    """

    name = "ripgrep"

    def __init__(self, search_dirs: list[Path], rag_dirs: list[Path]) -> None:
        self._search_dirs = search_dirs
        self._rag_dirs = rag_dirs

    def search(self, query: str, *, limit: int) -> list[RankedHit]:
        if not query.strip():
            return []
        from src.lib.index.unified_search import (
            _collect_active_search_hits,
            _dedup_by_file,
            _score_hits,
            _to_rg_pattern,
        )

        raw = _collect_active_search_hits(
            _to_rg_pattern(query), self._search_dirs, rag_dirs=self._rag_dirs
        )
        scored = _dedup_by_file(_score_hits(raw, query.strip().split()))[:limit]
        return [
            RankedHit(
                doc_id=str(hit.get("path", hit.get("file", ""))),
                rank=i + 1,
                raw_score=float(hit.get("score", 0.0)),
                snippet=str(hit.get("line", hit.get("snippet", ""))),
            )
            for i, hit in enumerate(scored)
            if hit.get("path") or hit.get("file")
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/lib/index/test_sources.py`
Expected: PASS (2 passed). (`RipgrepSource` is covered end-to-end in Task 4's integration test — its constructor + protocol conformance are exercised here.)

- [ ] **Step 5: Commit**

```bash
git add src/lib/index/sources.py tests/lib/index/test_sources.py
git commit -m "feat(search): RipgrepSource + BM25Source RetrieverSources (ADR-739)"
```

---

# Phase 3 — Fusion Integration

## Task 4: Rewrite `unified_search.py`'s combine step to fuse via RRF

**Files:**
- Modify: `src/lib/index/unified_search.py`
- Test: `tests/lib/index/test_unified_search_fusion.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for unified_search RRF integration (ADR-739)."""
from __future__ import annotations

from src.lib.index import unified_search


def test_fuse_results_uses_rrf_and_carries_provenance() -> None:
    """fuse_results() takes per-source ranked lists and returns RRF-fused rows
    with score / budget / provenance fields."""
    from src.lib.index.rrf import RankedHit

    ranked = {
        "ripgrep": [RankedHit("doc-A", 1, 9.0), RankedHit("doc-B", 2, 8.0)],
        "bm25": [RankedHit("doc-A", 1, 0.9)],
    }
    fused = unified_search.fuse_results(ranked, budget="conservative")
    assert fused[0]["doc_id"] == "doc-A"
    assert fused[0]["budget"] == "conservative"
    assert "score" in fused[0] and "provenance" in fused[0]
    assert len(fused) <= 5                                       # conservative top_k


def test_unified_rag_search_still_returns_target_and_results() -> None:
    """Backward compatibility: the public entry shape is unchanged; a call with
    no budget still works (defaults to balanced)."""
    import json

    out = json.loads(unified_search.unified_rag_search({"query": "augur"}))
    assert "target" in out and "results" in out
    assert isinstance(out["results"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/lib/index/test_unified_search_fusion.py`
Expected: FAIL — `unified_search.fuse_results` does not exist.

- [ ] **Step 3: Add `fuse_results()` to `unified_search.py`**

Add a new function that wraps `rrf.fuse()` with budget resolution:

```python
def fuse_results(
    ranked_lists: dict, *, budget: str | None = None
) -> list[dict]:
    """Fuse per-source ranked lists via RRF, sized to the given search budget.

    Each row: {doc_id, score, budget, provenance, snippet}.
    """
    from src.lib.index.rrf import fuse
    from src.lib.index.search_config import budget_top_k, load_search_config

    cfg = load_search_config()
    budget_name = budget if budget in cfg["search_budgets"] else cfg["default_budget"]
    fused = fuse(
        ranked_lists,
        k=int(cfg["rrf"]["k"]),
        top_k=budget_top_k(cfg, budget_name),
    )
    for row in fused:
        row["budget"] = budget_name
    return fused
```

- [ ] **Step 4: Rewrite the combine step in `_raw_iterative_search` / `iterative_search`**

Replace the ad-hoc "append a typed `{type, hits}` group per source" logic so it
instead builds a `dict[str, list[RankedHit]]` from the registered sources
(`RipgrepSource` over `priority_dirs`/`source_dirs`/`rag_dirs`, `BM25Source` over
the cached BM25 index) and returns `fuse_results(ranked_lists, budget=budget)`.
Thread an optional `budget: str | None = None` parameter through
`iterative_search` and `unified_rag_search` (read from `args.get("budget")` in
the latter). Keep `resolve_scope_paths`, `_to_rg_pattern`, and the ripgrep
collection helpers intact — only the *combine* step changes.

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest tests/lib/index/test_unified_search_fusion.py tests/lib/index/test_unified_search_imports.py tests/lib/index/test_unified_search_inactive_scopes.py`
Expected: PASS — fusion works and the existing unified_search tests still pass (no regression).

- [ ] **Step 6: Commit**

```bash
git add src/lib/index/unified_search.py tests/lib/index/test_unified_search_fusion.py
git commit -m "feat(search): fuse unified_search combine step via RRF (ADR-739)"
```

---

# Phase 4 — Surface Params + New Tools

## Task 5: Thread `budget` through the search surfaces

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/rag_search.py` (the `unified-search` MCP tool)
- Modify: the `memory-search` tool path (`shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py` or wherever `memory-search` retrieves)
- Modify: `shared-vault/skills/rag/scripts/mcp/rag_tools.py` (`search-skill-knowledge`)

- [ ] **Step 1: Add the `budget` param to `unified-search`** — in `rag_search.py`'s
`unified_search_tool`, add `budget: str | None = None` to the signature and pass
it into `unified.search(...)` / `unified_rag_search(...)`. The existing `mode`,
`top_k`, `max_results` params are **unchanged** — `budget` is additive and
orthogonal (`mode` = retrieval strategy, `budget` = depth/token cost).

- [ ] **Step 2: Locate the `memory-search` retrieval path** and route it through
the same `unified_search` fusion (or `fuse_results`) so `memory-search` results
also carry `score` / `budget` / `provenance`. Add the `budget` param to the tool.

- [ ] **Step 3: Route `search-skill-knowledge`** (`rag_tools.py`) through the shared
`unified_search` fusion step the same way.

- [ ] **Step 4: Verify the result shape** — confirm `unified-search` /
`memory-search` results now carry explicit `score`, `budget`, and `provenance`
fields (consumed by ADR-742's eval harness). Add a focused test under
`shared-vault/skills/knowledge/augur/tests/` (importlib convention — this is a
skill tool) asserting the tool output includes those fields.

- [ ] **Step 5: Run tests + knowledge-skill regression**

Run: `/auto-test-pytest tests/lib/index/ shared-vault/skills/knowledge/augur/tests/`
Expected: PASS — fusion + surface params work, no knowledge-skill regressions.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/rag_search.py shared-vault/skills/knowledge/scripts/mcp/tools_memory_core.py shared-vault/skills/rag/scripts/mcp/rag_tools.py shared-vault/skills/knowledge/augur/tests/
git commit -m "feat(search): thread budget param + score/provenance shape (ADR-739)"
```

## Task 6: `search-stats` + `search-tune` MCP tools

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/rag_search.py` (add the two tools)
- Modify: `config/system/capability_exposure.yaml`
- Test: `shared-vault/skills/knowledge/augur/tests/test_search_tools.py`

- [ ] **Step 1: Write the failing test** (importlib convention — skill tools)

```python
# (prepend the knowledge-skill importlib loader block)
def test_search_stats_reports_bm25_freshness_and_budgets() -> None:
    mod = _load("rag_search", "mcp/rag_search.py")
    result = mod.search_stats()                      # the pure-logic helper
    assert "bm25_index" in result and "budgets" in result


def test_search_tune_recommends_a_known_budget() -> None:
    mod = _load("rag_search", "mcp/rag_search.py")
    rec = mod.search_tune(query="a very long deep multi-part question about retrieval internals")
    assert rec["recommended_budget"] in {"conservative", "balanced", "tokenmax"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/knowledge/augur/tests/test_search_tools.py`
Expected: FAIL — `search_stats` / `search_tune` do not exist.

- [ ] **Step 3: Add `search_stats()` and `search_tune()` helpers + their MCP tools**
to `rag_search.py`:
- `search_stats()` — returns BM25 index freshness (last rebuild mtime of
  `get_rag_dir()/_meta/bm25_index.json`, doc count) + the budget table from
  `load_search_config()`.
- `search_tune(query)` — a simple heuristic: short query → `conservative`, very
  long / multi-clause query → `tokenmax`, else `balanced`. Returns
  `{recommended_budget, reason}` — a recommendation string, never an automatic
  switch.
- Register both as `readOnlyHint` MCP tools (`search-stats`, `search-tune`)
  following the existing `@mcp.tool` pattern in `rag_search.py`.

- [ ] **Step 4: Add capability-exposure entries** — append `mcp-tool:search-stats`
and `mcp-tool:search-tune` to `config/system/capability_exposure.yaml`
(`management: generated`, `owner_kind: augur`, `primary_surface: cli`,
`preferred_client: shell`, `scope: project`, `export_to: [browse]`).

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/knowledge/augur/tests/test_search_tools.py`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/rag_search.py config/system/capability_exposure.yaml shared-vault/skills/knowledge/augur/tests/test_search_tools.py
git commit -m "feat(search): search-stats + search-tune MCP tools (ADR-739)"
```

---

# Phase 5 — Docs + Final Validation

## Task 7: Docs + regeneration + validation gate

**Files:**
- Modify: `docs/agent-topics/CONTEXT.md` (the retrieval section)

- [ ] **Step 1: Update `CONTEXT.md`** — document that retrieval now fuses via RRF
over `RetrieverSource`s (ripgrep + BM25 today; ADR-738 graph + a future vector
retriever plug in via the protocol); the `budget` param (conservative/balanced/
tokenmax) is orthogonal to the existing `mode` strategy param.

- [ ] **Step 2: Regenerate agent instructions**

Run: `PYTHONPATH=shared-vault python3 -m skills.ai.scripts.sync_agents sync agents all`
Expected: regenerates `CLAUDE.md` / per-client surfaces with the new
`mcp-tool:search-stats` / `mcp-tool:search-tune` rows.

- [ ] **Step 3: Full RRF test suite**

Run: `/auto-test-pytest tests/lib/index/`
Expected: PASS — `test_rrf`, `test_search_config`, `test_sources`,
`test_unified_search_fusion` green + the pre-existing `test_unified_search_*`
green (no regression).

- [ ] **Step 4: Lint**

Run: `/auto-lint`
Expected: clean — no new findings in `src/lib/index/` or the modified MCP tools.

- [ ] **Step 5: Confirm no vector retriever / no DB was introduced**

Run: `grep -rnE "faiss|sentence.transformer|sqlite|lancedb|embedding_model" src/lib/index/rrf.py src/lib/index/sources.py src/lib/index/search_config.py || echo "clean"`
Expected: `clean` — RRF is pure fusion math; ADR-739 adds no retriever and no database.

- [ ] **Step 6: End-to-end smoke**

Run: `aug unified-search --query "augur" --budget conservative` (or the MCP tool)
Expected: JSON results carrying `score` / `budget: conservative` / `provenance`,
at most 5 results.

- [ ] **Step 7: Commit**

```bash
git add docs/agent-topics/CONTEXT.md CLAUDE.md AGENTS.md .claude/ .codex/ .gemini/
git commit -m "docs(search): document RRF + budgets + regenerate surfaces (ADR-739)"
```

---

## Completion Checklist (maps to ADR-739 Completion Gates)

- [ ] `rrf.py`, `sources.py`, `search_config.py` written — no orphan code
- [ ] `unified_search.py` combine step fuses via `rrf.fuse()`; `budget` threaded through
- [ ] `unified-search` / `memory-search` / `search-skill-knowledge` carry `score` / `budget` / `provenance`
- [ ] `config/system/search.yaml` shipped; `capability_exposure.yaml` has `search-stats` + `search-tune`
- [ ] Every plan test case green; pre-existing `tests/lib/index/` green (no regression)
- [ ] `RetrieverSource` protocol in place — the seam ADR-738's graph + a future vector ADR plug into
- [ ] `CONTEXT.md` documents RRF + budgets; agent instructions regenerated
- [ ] `grep` confirms no vector retriever, no database introduced
- [ ] `superpowers:verification-before-completion` run before declaring done
```
