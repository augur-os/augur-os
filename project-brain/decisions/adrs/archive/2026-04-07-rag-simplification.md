# RAG Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the markdown chunking/contextualization pipeline that costs ~27% of Claude quota nightly, keeping only document extraction + BM25 for binary files, and ripgrep for everything else.

**Architecture:** Three-tier knowledge system. Tier 1 (markdown) uses ripgrep on source files. Tier 2 (documents) keeps BM25 over extracted chunks. Tier 3 (wiki) is Phase 2, not in this plan. This plan covers Phase 1 only: kill the waste.

**Tech Stack:** Python 3.11+, existing RAG scripts in `skills/rag/scripts/`

**Spec:** `docs/superpowers/specs/2026-04-07-rag-simplification-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/rag/scripts/unified_indexer.py` | Modify | Remove markdown chunking + contextualization, keep document chunking + BM25 |
| `skills/rag/scripts/search_engine.py` | Rewrite | Remove LLM evaluation/ranking, become thin wrapper over ripgrep + document BM25 |
| `skills/rag/scripts/retrieval.py` | Delete | RRF merge no longer needed — BM25 used directly for documents only |
| `skills/rag/scripts/contextualizer.py` | Delete | 1,031 Claude calls/night for 11 searches |
| `skills/rag/scripts/_circuit_breaker.py` | Delete | Only used by contextualizer and search_engine LLM path |
| `skills/rag/scripts/ops/enrich_metadata.py` | Delete | No markdown chunks to enrich |
| `skills/rag/scripts/mcp/rag_tools.py` | Modify | Simplify search to ripgrep + document BM25, remove hybrid/RRF |
| `skills/rag/SKILL.md` | Modify | Remove auto-enrich-metadata command, update description |
| `skills/ai/scripts/ops/rag_reindex.py` | Modify | Remove contextualize param |
| `skills/auto-rag-reindex/scripts/rag_reindex_ops.py` | Modify | Remove contextualize references |
| `llm.yaml` | Modify | Add active_profile: local |
| `skills/rag/augur/tests/test_unified_indexer.py` | Modify | Update tests for new behavior |
| `skills/rag/augur/tests/test_search_engine.py` | Rewrite | Match simplified search engine |
| `skills/rag/augur/tests/test_retrieval.py` | Delete | retrieval.py deleted |
| `skills/rag/augur/tests/test_enrich_metadata.py` | Delete | enrich_metadata.py deleted |

---

### Task 1: Safety Net — Set LLM Active Profile to Local

**Files:**
- Modify: `llm.yaml` (project root)

- [ ] **Step 1: Add active_profile to llm.yaml**

Open `llm.yaml` and add `active_profile: local` at the top level. This ensures any remaining LLM call routes through Ollama (free) instead of Claude CLI.

```yaml
active_profile: local

external:
  preferred_cli: claude

profiles:
  local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3.5:latest
    timeout_s: 120
    disable_thinking: true
  remote:
    provider: openai_compatible
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    model: llama-3.3-70b
  vision-local:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: llava-llama3
    timeout_s: 120

tasks: {}
```

- [ ] **Step 2: Verify config loads correctly**

Run:
```bash
cd ~/Projects/Augur && python3 -c "
from skills.ai.augur.lib import load_llm_config, resolve_llm_profile
config = load_llm_config()
profile = resolve_llm_profile(config)
print(f'Active: {profile.name}, Model: {profile.model}, URL: {profile.base_url}')
"
```

Expected: `Active: local, Model: qwen3.5:latest, URL: http://localhost:11434/v1`

- [ ] **Step 3: Commit**

```bash
git add llm.yaml
git commit -m "fix(rag): set active_profile to local — prevent Claude CLI calls from nightly loops"
```

---

### Task 2: Delete Contextualizer and Circuit Breaker

**Files:**
- Delete: `skills/rag/scripts/contextualizer.py`
- Delete: `skills/rag/scripts/_circuit_breaker.py`
- Modify: `skills/rag/scripts/search_engine.py:7` (remove circuit breaker import)

- [ ] **Step 1: Check for other imports of these modules**

Run:
```bash
grep -rn "contextualizer\|_circuit_breaker" skills/rag/scripts/ --include="*.py" | grep -v __pycache__ | grep -v test
```

Expected references:
- `contextualizer.py` imported only in `unified_indexer.py:367` (inside `if contextualize:` block — will be removed in Task 4)
- `_circuit_breaker.py` imported in `search_engine.py:7` and `contextualizer.py:16`

- [ ] **Step 2: Remove circuit breaker import from search_engine.py**

In `skills/rag/scripts/search_engine.py`, delete line 7:
```python
from skills.rag.scripts._circuit_breaker import CircuitBreaker
```

And delete line 20:
```python
_llm_cb = CircuitBreaker(threshold=3, cooldown=300.0)
```

And in `_call_llm_with_retry` (line 70-71), delete:
```python
        if _llm_cb.is_open:
            raise RuntimeError("LLM circuit breaker is open")
```

And delete the two `_llm_cb.record_success()` (line 82) and `_llm_cb.record_failure()` calls (lines 88, 92).

- [ ] **Step 3: Delete the files**

```bash
rm skills/rag/scripts/contextualizer.py
rm skills/rag/scripts/_circuit_breaker.py
```

- [ ] **Step 4: Commit**

```bash
git add -A skills/rag/scripts/contextualizer.py skills/rag/scripts/_circuit_breaker.py skills/rag/scripts/search_engine.py
git commit -m "refactor(rag): delete contextualizer and circuit breaker — zero LLM calls in RAG pipeline"
```

---

### Task 3: Delete Auto-Enrich-Metadata and Retrieval Module

**Files:**
- Delete: `skills/rag/scripts/ops/enrich_metadata.py`
- Delete: `skills/rag/scripts/retrieval.py`
- Delete: `skills/rag/augur/tests/test_retrieval.py`
- Delete: `skills/rag/augur/tests/test_enrich_metadata.py`
- Modify: `skills/rag/SKILL.md` (remove auto-enrich-metadata command)

- [ ] **Step 1: Check for imports of retrieval.py**

Run:
```bash
grep -rn "from.*retrieval import\|import retrieval" skills/rag/scripts/ --include="*.py" | grep -v __pycache__ | grep -v test
```

Expected: `search_engine.py:146` imports `hybrid_search` inside `iterative_search` method. This will be removed when we rewrite search_engine.py in Task 5.

- [ ] **Step 2: Remove auto-enrich-metadata from SKILL.md**

In `skills/rag/SKILL.md`, delete the auto-command entry (lines starting at line 9 of x-augur-auto-commands):
```yaml
- id: auto-enrich-metadata
  callable: skills/rag/scripts/ops/enrich_metadata.py
  loop:
    name: knowledge-enrichment
    tier: 1
    trigger: nightly
```

- [ ] **Step 3: Delete the files**

```bash
rm skills/rag/scripts/ops/enrich_metadata.py
rm skills/rag/scripts/retrieval.py
rm skills/rag/augur/tests/test_retrieval.py
rm skills/rag/augur/tests/test_enrich_metadata.py
```

- [ ] **Step 4: Commit**

```bash
git add -A skills/rag/scripts/ops/enrich_metadata.py skills/rag/scripts/retrieval.py skills/rag/augur/tests/test_retrieval.py skills/rag/augur/tests/test_enrich_metadata.py skills/rag/SKILL.md
git commit -m "refactor(rag): delete enrich-metadata ops and retrieval module — no markdown chunks to enrich or merge"
```

---

### Task 4: Simplify unified_indexer.py — Documents-Only Chunking

**Files:**
- Modify: `skills/rag/scripts/unified_indexer.py`
- Test: `skills/rag/augur/tests/test_unified_indexer.py`

This is the largest change. `_chunk_all()` currently chunks all categories in `_CHUNK_CATEGORIES`. We restrict it to `documents` only, remove `_contextualize_chunks()`, and remove the `contextualize` param from `reindex_all()`.

- [ ] **Step 1: Write test for documents-only chunking**

Add to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_chunk_all_only_chunks_documents(tmp_path):
    """_chunk_all should only produce chunks for the 'documents' category, not ADRs/vault/etc."""
    from skills.rag.scripts.unified_indexer import _chunk_all
    from src.lib.frontmatter_utils import write_frontmatter

    rag_dir = tmp_path / "rag"

    # Create a documents category entry with enough body to chunk
    docs_dir = rag_dir / "documents" / "test-skill"
    docs_dir.mkdir(parents=True)
    write_frontmatter(
        docs_dir / "invoice.md",
        {"name": "invoice", "source_path": "/tmp/invoice.pdf", "hub": "test"},
        "A" * 500,  # > 200 char threshold
    )

    # Create an ADRs category entry — should NOT be chunked
    adrs_dir = rag_dir / "adrs" / "dev"
    adrs_dir.mkdir(parents=True)
    write_frontmatter(
        adrs_dir / "ADR-001.md",
        {"name": "ADR-001", "hub": "dev"},
        "B" * 500,
    )

    # Create a vault entry — should NOT be chunked
    vault_dir = rag_dir / "vault" / "notes"
    vault_dir.mkdir(parents=True)
    write_frontmatter(
        vault_dir / "note.md",
        {"name": "note", "hub": "brain"},
        "C" * 500,
    )

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    count, bm25_chunks = _chunk_all(rag_dir, tmp_path)

    # Should have chunks from documents only
    assert count > 0
    chunks_dir = rag_dir / "chunks"
    doc_chunks = list((chunks_dir / "documents").rglob("*.md")) if (chunks_dir / "documents").exists() else []
    adr_chunks = list((chunks_dir / "adrs").rglob("*.md")) if (chunks_dir / "adrs").exists() else []
    vault_chunks = list((chunks_dir / "vault").rglob("*.md")) if (chunks_dir / "vault").exists() else []

    assert len(doc_chunks) > 0, "Documents should be chunked"
    assert len(adr_chunks) == 0, "ADRs should NOT be chunked"
    assert len(vault_chunks) == 0, "Vault should NOT be chunked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/test_unified_indexer.py::test_chunk_all_only_chunks_documents -v`

Expected: FAIL — current `_CHUNK_CATEGORIES` includes adrs and vault.

- [ ] **Step 3: Restrict _CHUNK_CATEGORIES to documents only**

In `skills/rag/scripts/unified_indexer.py`, line 576:

Change:
```python
_CHUNK_CATEGORIES = {"adrs", "vault", "documents", "actions", "prompts", "workflows", "scripts", "mcp-tools"}
```

To:
```python
_CHUNK_CATEGORIES = {"documents"}
```

And line 578, change:
```python
_CODE_CATEGORIES = {"scripts", "mcp-tools"}
```

To:
```python
_CODE_CATEGORIES: set[str] = set()  # No code categories chunked in simplified pipeline
```

- [ ] **Step 4: Remove _contextualize_chunks and contextualize param**

In `skills/rag/scripts/unified_indexer.py`:

Delete the entire `_contextualize_chunks` function (lines 716-760).

In `reindex_all()` (line 312), remove the `contextualize` parameter and the contextualization block:

Change signature from:
```python
def reindex_all(
    root: Path,
    rag_dir: Path,
    vault_dir: "Path | None" = None,
    documents_dir: "Path | None" = None,
    max_chunks: int = 0,
    contextualize: bool = True,
) -> "dict[str, int]":
```

To:
```python
def reindex_all(
    root: Path,
    rag_dir: Path,
    vault_dir: "Path | None" = None,
    documents_dir: "Path | None" = None,
) -> "dict[str, int]":
```

Delete lines 364-376 (the `if contextualize:` block and its contents).

In the CLI entry point at the bottom (lines 797-823), remove the `--max-chunks` and `--skip-contextualization` arguments and the `max_chunks` and `contextualize` kwargs from the `reindex_all()` call.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/test_unified_indexer.py::test_chunk_all_only_chunks_documents -v`

Expected: PASS

- [ ] **Step 6: Fix existing tests that reference contextualize param**

In `skills/rag/augur/tests/test_unified_indexer.py`, find and update:
- `test_reindex_all_can_skip_contextualization` — delete both copies (the param no longer exists)
- Any test calling `reindex_all(..., contextualize=False)` — remove the `contextualize` kwarg
- Any test calling `reindex_all(..., max_chunks=...)` — remove the `max_chunks` kwarg

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/test_unified_indexer.py -v`

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add skills/rag/scripts/unified_indexer.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "refactor(rag): restrict chunking to documents only — drop 9,200 markdown chunk files"
```

---

### Task 5: Simplify Search Engine — Remove LLM Ranking

**Files:**
- Rewrite: `skills/rag/scripts/search_engine.py`
- Rewrite: `skills/rag/augur/tests/test_search_engine.py`

The search engine currently has LLM evaluation, LLM ranking, circuit breaker, retry logic, and hybrid/RRF dispatch. Replace with a simple wrapper: ripgrep results + optional document BM25.

- [ ] **Step 1: Write test for simplified search engine**

Rewrite `skills/rag/augur/tests/test_search_engine.py`:

```python
"""Tests for simplified RAG search engine (no LLM, no hybrid/RRF)."""
import pytest


def test_search_without_bm25():
    """Without BM25 index, returns ripgrep results directly."""
    from skills.rag.scripts.search_engine import RAGSearchEngine

    fake_results = [{"type": "fulltext", "hits": [{"file": "a.md", "line": "hello"}]}]
    engine = RAGSearchEngine(search_func=lambda q: fake_results)
    results = engine.search("hello")
    assert results == fake_results


def test_search_with_bm25_appends_document_results():
    """With BM25 index, document results are appended as a separate group."""
    from skills.rag.scripts.search_engine import RAGSearchEngine

    rg_results = [{"type": "fulltext", "hits": [{"file": "a.md", "line": "hello"}]}]

    class FakeBM25:
        def query(self, q, top_k=10):
            return [{"path": "chunks/documents/invoice/chunk_0.md", "score": 0.8}]

    engine = RAGSearchEngine(search_func=lambda q: rg_results, bm25_index=FakeBM25())
    results = engine.search("hello")

    assert len(results) == 2
    assert results[0]["type"] == "fulltext"
    assert results[1]["type"] == "documents"
    assert results[1]["hits"][0]["path"] == "chunks/documents/invoice/chunk_0.md"


def test_search_with_bm25_none_returns_ripgrep_only():
    """BM25 index=None should not add document results."""
    from skills.rag.scripts.search_engine import RAGSearchEngine

    rg_results = [{"type": "user_data", "hits": [{"file": "b.md"}]}]
    engine = RAGSearchEngine(search_func=lambda q: rg_results, bm25_index=None)
    results = engine.search("test")
    assert len(results) == 1
    assert results[0]["type"] == "user_data"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/test_search_engine.py -v`

Expected: FAIL — `RAGSearchEngine.search()` doesn't exist yet.

- [ ] **Step 3: Rewrite search_engine.py**

Replace `skills/rag/scripts/search_engine.py` entirely:

```python
"""Simplified RAG search engine.

Ripgrep handles all markdown search. BM25 is used only for document chunks.
No LLM evaluation, no LLM ranking, no circuit breaker, no retries.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RAGSearchEngine:
    """Search engine: ripgrep for markdown, BM25 for document chunks."""

    def __init__(
        self,
        search_func: Callable[[str], list[dict]],
        bm25_index: Any | None = None,
    ):
        self.search_func = search_func
        self._bm25_index = bm25_index

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Run search: ripgrep tiers + optional document BM25.

        Returns list of result groups, each with 'type' and 'hits' keys.
        Document BM25 results are appended as a separate 'documents' group.
        """
        results = self.search_func(query)

        if self._bm25_index is not None:
            try:
                doc_hits = self._bm25_index.query(query, top_k=top_k)
                if doc_hits:
                    results.append({"type": "documents", "hits": doc_hits})
            except Exception as e:
                logger.warning("BM25 document search failed: %s", e)

        return results

    # Keep old method name as alias for backward compat during transition
    iterative_search = search
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/test_search_engine.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/search_engine.py skills/rag/augur/tests/test_search_engine.py
git commit -m "refactor(rag): simplify search engine — ripgrep + document BM25, no LLM"
```

---

### Task 6: Simplify MCP Search Tool

**Files:**
- Modify: `skills/rag/scripts/mcp/rag_tools.py`

- [ ] **Step 1: Simplify the iterative_search function**

In `skills/rag/scripts/mcp/rag_tools.py`, the `iterative_search` function (line 195-204) currently loads BM25 and creates a RAGSearchEngine with hybrid search. Simplify it:

Replace lines 195-204:
```python
def iterative_search(query: str, source_dirs: list[Path], priority_dirs: list[Path], rag_dirs: list[Path]) -> list[dict]:
    from ..search_engine import RAGSearchEngine

    bm25_index = _load_bm25_cached(rag_dirs)

    engine = RAGSearchEngine(
        search_func=lambda q: _raw_iterative_search(q, source_dirs, priority_dirs, rag_dirs),
        bm25_index=bm25_index,
    )
    return engine.iterative_search(query)
```

With:
```python
def iterative_search(query: str, source_dirs: list[Path], priority_dirs: list[Path], rag_dirs: list[Path]) -> list[dict]:
    from ..search_engine import RAGSearchEngine

    bm25_index = _load_bm25_cached(rag_dirs)

    engine = RAGSearchEngine(
        search_func=lambda q: _raw_iterative_search(q, source_dirs, priority_dirs, rag_dirs),
        bm25_index=bm25_index,
    )
    return engine.search(query)
```

(Only change: `iterative_search` → `search`. The alias in search_engine.py handles backward compat.)

- [ ] **Step 2: Simplify rag_reindex MCP tool**

In the `rag_reindex` tool function (line 267-306), the call to `reindex_all` on line 306 currently passes no `contextualize` param (defaults to True). Since we removed the param from `reindex_all()`, no change needed here — the function signature is now clean.

Verify no `contextualize` or `max_chunks` references remain:
```bash
grep -n "contextualize\|max_chunks" skills/rag/scripts/mcp/rag_tools.py
```

Expected: No matches.

- [ ] **Step 3: Remove hybrid_search import guard**

Search for any remaining imports of `retrieval` or `hybrid_search` in rag_tools.py:
```bash
grep -n "retrieval\|hybrid_search\|rrf" skills/rag/scripts/mcp/rag_tools.py
```

Expected: No matches (these were only in search_engine.py which we already rewrote).

- [ ] **Step 4: Commit**

```bash
git add skills/rag/scripts/mcp/rag_tools.py
git commit -m "refactor(rag): simplify MCP search tool — use new search engine"
```

---

### Task 7: Clean Up Callers — Remove contextualize Param

**Files:**
- Modify: `skills/ai/scripts/ops/rag_reindex.py`
- Modify: `skills/auto-rag-reindex/scripts/rag_reindex_ops.py`
- Modify: `skills/ai/scripts/ops/project_index.py`
- Modify: `skills/knowledge/scripts/mcp/tools_index.py`
- Modify: `skills/auto-e2e-pipeline/scripts/e2e_pipeline.py`

- [ ] **Step 1: Remove contextualize=False from rag_reindex.py**

In `skills/ai/scripts/ops/rag_reindex.py`, line 121:

Change:
```python
        stats = unified_indexer.reindex_all(
            root=ctx.project_root,
            rag_dir=get_rag_dir(),
            vault_dir=vault,
            documents_dir=documents,
            contextualize=False,
        )
```

To:
```python
        stats = unified_indexer.reindex_all(
            root=ctx.project_root,
            rag_dir=get_rag_dir(),
            vault_dir=vault,
            documents_dir=documents,
        )
```

- [ ] **Step 2: Same for auto-rag-reindex**

In `skills/auto-rag-reindex/scripts/rag_reindex_ops.py`, find the `reindex_all` call and remove `contextualize=False`.

- [ ] **Step 3: Remove --skip-contextualization from project_index.py**

In `skills/ai/scripts/ops/project_index.py`, line 109:

Change:
```python
        err = _run_script(
            indexer_script,
            ctx,
            timeout=index_timeout,
            extra_args=["--skip-contextualization"],
        )
```

To:
```python
        err = _run_script(
            indexer_script,
            ctx,
            timeout=index_timeout,
        )
```

- [ ] **Step 4: Verify no remaining contextualize references**

Run:
```bash
grep -rn "contextualize\|max_chunks\|skip.contextualization" skills/ --include="*.py" | grep -v __pycache__ | grep -v test | grep -v contextualizer
```

Expected: No matches (except possibly in tests — those are OK to clean up separately).

- [ ] **Step 5: Commit**

```bash
git add skills/ai/scripts/ops/rag_reindex.py skills/auto-rag-reindex/scripts/rag_reindex_ops.py skills/ai/scripts/ops/project_index.py skills/knowledge/scripts/mcp/tools_index.py skills/auto-e2e-pipeline/scripts/e2e_pipeline.py
git commit -m "refactor(rag): remove contextualize param from all callers"
```

---

### Task 8: Delete Test Files for Removed Modules

**Files:**
- Delete: `skills/rag/augur/tests/test_contextualizer.py` (if exists)
- Delete: `skills/rag/augur/tests/test_contextualizer_llm.py` (if exists)
- Modify: `skills/rag/augur/tests/test_unified_indexer.py` (remove contextualize tests)

- [ ] **Step 1: Delete contextualizer test files**

```bash
rm -f skills/rag/augur/tests/test_contextualizer.py
rm -f skills/rag/augur/tests/test_contextualizer_llm.py
```

- [ ] **Step 2: Remove contextualize-related tests from test_unified_indexer.py**

Delete:
- `test_reindex_all_can_skip_contextualization` (both copies if duplicated)
- Any test that passes `contextualize=` or `max_chunks=` kwargs

- [ ] **Step 3: Run all RAG tests**

Run: `cd ~/Projects/Augur && python3 -m pytest skills/rag/augur/tests/ -v`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A skills/rag/augur/tests/
git commit -m "test(rag): remove tests for deleted contextualizer, retrieval, and enrich-metadata modules"
```

---

### Task 9: Update SKILL.md Description

**Files:**
- Modify: `skills/rag/SKILL.md`

- [ ] **Step 1: Update the overview section**

Find the overview paragraph that says:
```
Key components: BM25 sparse index for ranked retrieval, contextual chunk enrichment via Ollama, circuit breaker for graceful degradation, hybrid search with Reciprocal Rank Fusion (RRF), and content-aware chunking strategies.
```

Replace with:
```
Key components: ripgrep for markdown search, BM25 sparse index for document retrieval, content-aware chunking for binary documents (PDFs, Office docs), and statically-generated index.md (Karpathy LLM Wiki pattern) for knowledge navigation.
```

- [ ] **Step 2: Update the nightly reindex section**

Find the description referencing contextualization and update it to reflect documents-only chunking.

- [ ] **Step 3: Commit**

```bash
git add skills/rag/SKILL.md
git commit -m "docs(rag): update SKILL.md to reflect three-tier architecture"
```

---

### Task 10: Runtime Cleanup — Delete Stale Chunks and Caches

**Files:** Runtime state only (no code changes)

- [ ] **Step 1: Delete non-document chunk directories**

```bash
RAG_DIR="$HOME/Library/Application Support/Augur/rag"

# List what will be deleted
ls "$RAG_DIR/chunks/" | grep -v documents

# Delete all chunk dirs except documents
for dir in "$RAG_DIR/chunks/"*/; do
  dirname=$(basename "$dir")
  if [ "$dirname" != "documents" ]; then
    echo "Deleting: $dir"
    rm -rf "$dir"
  fi
done
```

- [ ] **Step 2: Delete stale BM25 index (will be rebuilt for documents only)**

```bash
rm -f "$RAG_DIR/_meta/bm25_index.json"
rm -f "$RAG_DIR/_meta/bm25_chunk_map.json"
```

- [ ] **Step 3: Delete context cache**

```bash
rm -f "$HOME/Library/Application Support/Augur/state/adaptive/rag_context_cache.json"
```

- [ ] **Step 4: Rebuild clean index**

Run:
```bash
cd ~/Projects/Augur && python3 skills/rag/scripts/unified_indexer.py
```

Verify output shows:
- Category counts for all 15 categories (same as before)
- Chunks count is small (documents only, not 9,355)
- BM25 index built from document chunks only
- No contextualization message

- [ ] **Step 5: Verify chunk count**

```bash
find "$RAG_DIR/chunks/" -name "*.md" | wc -l
```

Expected: < 500 (documents only, down from 9,355)

- [ ] **Step 6: Commit state documentation**

No git commit needed (runtime state is outside repo). But verify the cleanup worked.

---

### Task 11: Website Messaging Updates

**Files:**
- Modify: `Au-docs/venture-augur/website-working/index.html`

- [ ] **Step 1: Update comparison table RAG row (line ~842)**

Find:
```html
<td>BM25 + ripgrep hybrid, content-aware chunking</td>
```

Replace with:
```html
<td>Three-tier: ripgrep for code, BM25 for documents, LLM Wiki for compiled knowledge</td>
```

- [ ] **Step 2: Add wiki paragraph after knowledge section (line ~753)**

After the paragraph ending "The knowledge base builds itself.", add:

```html
                    <p style="margin-top:1rem">Under the hood, Augur maintains a living wiki &mdash; inspired by Karpathy&rsquo;s LLM Wiki pattern. Every conversation distills what was learned into interlinked wiki pages stored in your vault. Cross-references are pre-built, contradictions flagged, synthesis already done. The next AI session starts where the last one left off &mdash; regardless of which client you use.</p>
```

- [ ] **Step 3: Update architecture tag (line ~953)**

Find:
```html
<span class="arch-tag">Plain text RAG</span>
```

Replace with:
```html
<span class="arch-tag">LLM Wiki + document search</span>
```

- [ ] **Step 4: Update skills description (line ~1003)**

Find:
```
RAG indexes connect everything.
```

Replace with:
```
A living wiki compiles your knowledge. Documents are searchable via BM25.
```

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Au-docs && git add venture-augur/website-working/index.html
git commit -m "content(website): update RAG messaging to three-tier architecture with LLM Wiki"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Set active_profile: local in llm.yaml | Low — safety net |
| 2 | Delete contextualizer + circuit breaker | Low — pure deletion |
| 3 | Delete enrich-metadata + retrieval module | Low — pure deletion |
| 4 | Restrict chunking to documents only | Medium — core pipeline change, test carefully |
| 5 | Simplify search engine | Medium — new search interface |
| 6 | Simplify MCP search tool | Low — thin adapter |
| 7 | Remove contextualize param from callers | Low — mechanical cleanup |
| 8 | Delete stale test files | Low — pure deletion |
| 9 | Update SKILL.md description | Low — docs only |
| 10 | Runtime cleanup — delete chunks/caches | Low — regeneratable |
| 11 | Website messaging | Low — content only |

**Do Task 1 first** (safety net). Then Tasks 2-3 (deletions). Then Task 4 (the core change). Then 5-11 in order.

**Phase 2 (Wiki Tier)** is a separate plan — requires ADR, schema prompt design, dashboard tab, and session hooks. Not covered here.
