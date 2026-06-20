# Track 1 / Library 4: rag → src/lib/index/ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track1-rag`.

**Goal:** Move rag's 12 library .py files from `skills/rag/scripts/` (excluding `mcp/` subdir) to `src/lib/index/` using rename-via-overlap. Migrate 5 external consumer sites in 4 files, 1 dynamic file load in `src/mcp/augur_mcp/infrastructure/browse/index.py`, rag's bundle MCP wrappers, and rag's own tests.

**Architecture:** Seven sequential PRs. PR 1 is purely additive (12 files copied, both old and new paths work). PRs 2–6 migrate one consumer group at a time. PR 7 deletes the 12 skill-side library files. The `mcp/` subdirectory stays in the bundle. Architecture-test allowlist entries `("ingest", "rag")` and `("knowledge", "rag")` do NOT retire here — bundle MCP (`rag_tools.py`) is still consumed cross-skill.

**Tech Stack:** Python 3.11+, pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Library 1+2+3 plans: `2026-04-29-track1-doc-extractor-extraction.md`, `2026-04-29-track1-knowledge-memory-extraction.md`, `2026-04-29-track1-daemon-runtime-extraction.md`

## File Structure

### New files (created in PR 1)

| File | Purpose |
|---|---|
| `src/lib/index/__init__.py` | Re-exports public API: `understand_document`, `reindex_all`, `reindex_category`, `index_documents`, `index_skills`, `list_category_entries`, `count_category_entries`, `read_index_entry`, `BM25Index`, `RAGSearchEngine`, `enrich_all` |
| `src/lib/index/_indexer_helpers.py` | Verbatim copy |
| `src/lib/index/_scanners_knowledge.py` | Verbatim copy |
| `src/lib/index/_scanners_structural.py` | Verbatim copy |
| `src/lib/index/bm25_index.py` | Verbatim copy |
| `src/lib/index/chunker.py` | Verbatim copy |
| `src/lib/index/document_understanding.py` | Verbatim copy |
| `src/lib/index/enrich_descriptions.py` | Verbatim copy |
| `src/lib/index/index_reader.py` | Verbatim copy |
| `src/lib/index/ocr_extractor.py` | Verbatim copy (already consumes `src.lib.extraction` from Library 1) |
| `src/lib/index/search_engine.py` | Verbatim copy |
| `src/lib/index/symbol_extractor.py` | Verbatim copy |
| `src/lib/index/unified_indexer.py` | Verbatim copy |
| `tests/lib/index/__init__.py` | Empty package marker |
| `tests/lib/index/test_index_imports.py` | Smoke tests |

All sibling imports inside the 12 files use relative paths (`from .X`, `from ._X`) — they continue to work after the move with no changes.

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `skills/ingest/scripts/wiki_reset.py:19` | 2 | `from skills.rag.scripts.unified_indexer import reindex_all, reindex_category` → `from src.lib.index.unified_indexer import reindex_all, reindex_category` |
| `skills/ingest/scripts/inbox_consume.py:12` | 2 | `from skills.rag.scripts.document_understanding import understand_document` → `from src.lib.index.document_understanding import understand_document` |
| `skills/ingest/scripts/inbox_consume.py:202` | 2 | `from skills.rag.scripts.unified_indexer import index_documents` → `from src.lib.index.unified_indexer import index_documents` |
| `src/mcp/augur_mcp/infrastructure/browse/index.py:192-203` | 3 | Replace dynamic file-load block with module-top `from src.lib.index.index_reader import list_category_entries, count_category_entries` |
| `tests/unit/test_rag_skill_source.py:17` | 4 | `from skills.rag.scripts._scanners_knowledge import index_skills` → `from src.lib.index._scanners_knowledge import index_skills` |
| `skills/rag/scripts/mcp/rag_tools.py:173,195,300,343` | 5 | 4 sites: `from ..X` (parent-relative) → `from src.lib.index.X` |
| `skills/rag/augur/tests/*.py` | 6 | Bulk substitution: `skills.rag.scripts.X` → `src.lib.index.X` (estimate: 100+ references) |

### Files deleted (in PR 7)

The 12 .py files in `skills/rag/scripts/` (NOT including `mcp/` subdir).

### What stays in the rag bundle

- `skills/rag/SKILL.md`, `config.yaml`
- `skills/rag/scripts/mcp/` (the MCP tool surface)
- `skills/rag/augur/tests/`, `actions/`, `evals/`, `assets/`

## PR Sequencing

| PR | Title | Net effect | Commits |
|---|---|---|---|
| 1 | Add `src/lib/index/` with smoke tests | Additive — both old and new paths work | 1 |
| 2 | Migrate ingest's 3 production sites | wiki_reset + inbox_consume | 1 |
| 3 | Migrate browse/index.py dynamic loader | Static `from src.lib.index.index_reader` | 1 |
| 4 | Migrate `tests/unit/test_rag_skill_source.py` | Single test import | 1 |
| 5 | Migrate rag's bundle MCP wrappers | rag_tools.py 4 sites | 1 |
| 6 | Migrate rag's own tests | Bulk substitution (~100+ references) | 1 |
| 7 | Delete 12 skill-side library files; final verification | Rename-via-overlap completes | 1 |

Total: **7 commits**.

## Architecture-test allowlist

**No allowlist entries get retired by Library 4.**

- `("ingest", "rag")` — production sites migrate (3 sites in 2 files), but `skills/ingest/augur/tests/test_rag_tools.py:33` still imports `from skills.rag.scripts.mcp import rag_tools` (bundle MCP). Pair stays in allowlist.
- `("knowledge", "rag")` — `skills/knowledge/scripts/rag_search_cli.py:29` imports `from skills.rag.scripts.mcp.rag_tools import unified_rag_search` (bundle MCP). Pair stays.

Both retire in Track 2 / Track 3 when the bundle MCP relocation/wrapping is addressed.

---

## Task 1: PR 1 — Add `src/lib/index/` (additive)

**Files:**
- Create: 12 files at `src/lib/index/` (verbatim copies of `skills/rag/scripts/*.py`)
- Create: `src/lib/index/__init__.py`
- Create: `tests/lib/index/__init__.py`, `tests/lib/index/test_index_imports.py`

This PR is **additive only**. Both old and new paths work after.

- [ ] **Step 1.1: Verify worktree branch**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && git branch --show-current
```

Expected: `track1-rag`. If not, STOP and report.

- [ ] **Step 1.2: Verify `src/lib/__init__.py` exists**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && ls src/lib/__init__.py
```

Expected: file exists.

- [ ] **Step 1.3: Copy the 12 .py files verbatim**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  mkdir -p src/lib/index && \
  for f in _indexer_helpers _scanners_knowledge _scanners_structural bm25_index chunker document_understanding enrich_descriptions index_reader ocr_extractor search_engine symbol_extractor unified_indexer; do \
    cp "skills/rag/scripts/$f.py" "src/lib/index/$f.py"; \
  done && \
  ls src/lib/index/
```

Expected output (12 files, no __init__.py yet):
```
_indexer_helpers.py
_scanners_knowledge.py
_scanners_structural.py
bm25_index.py
chunker.py
document_understanding.py
enrich_descriptions.py
index_reader.py
ocr_extractor.py
search_engine.py
symbol_extractor.py
unified_indexer.py
```

- [ ] **Step 1.4: Verify the 12 files parse**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  for f in src/lib/index/*.py; do uv run python -c "import ast; ast.parse(open('$f').read())" && echo "$f OK" || echo "$f FAIL"; done
```

Expected: 12 lines, all "OK".

- [ ] **Step 1.5: Create `src/lib/index/__init__.py`**

Save:

```python
"""RAG indexing and search library.

Migrated from skills/rag/scripts/ in Track 1 of the cross-client bundle
architecture migration. The rag bundle's MCP tool surface
(skills/rag/scripts/mcp/) consumes this library — the bundle no longer
hosts the library code itself.

Public API:
    understand_document(path) -> dict
        Document understanding orchestrator (PDF/DOCX/HTML/etc.).

    reindex_all(...), reindex_category(...), index_documents(...)
        Unified indexer entry points.

    index_skills(...)
        Skill-tier scanner (knowledge category).

    list_category_entries(...), count_category_entries(...), read_index_entry(...)
        RAG index reader API (used by dashboard browse).

    BM25Index, RAGSearchEngine
        Search backbones (consumed by rag's MCP tool surface).

    enrich_all(...)
        Description enrichment for indexed entries.
"""
from __future__ import annotations

from src.lib.index.bm25_index import BM25Index
from src.lib.index.document_understanding import understand_document
from src.lib.index.enrich_descriptions import enrich_all
from src.lib.index.index_reader import (
    count_category_entries,
    list_category_entries,
    read_index_entry,
)
from src.lib.index._scanners_knowledge import index_skills
from src.lib.index.search_engine import RAGSearchEngine
from src.lib.index.unified_indexer import (
    index_documents,
    reindex_all,
    reindex_category,
)

__all__ = [
    "BM25Index",
    "RAGSearchEngine",
    "count_category_entries",
    "enrich_all",
    "index_documents",
    "index_skills",
    "list_category_entries",
    "read_index_entry",
    "reindex_all",
    "reindex_category",
    "understand_document",
]
```

- [ ] **Step 1.6: Verify the public API imports cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run python -c "
from src.lib.index import (
    BM25Index, RAGSearchEngine,
    count_category_entries, enrich_all, index_documents, index_skills,
    list_category_entries, read_index_entry, reindex_all, reindex_category,
    understand_document,
)
print('OK', understand_document.__module__)
"
```

Expected: `OK src.lib.index.document_understanding`

If imports fail with ImportError on a relative `from .X`, one of the files has an ABSOLUTE import (`from skills.rag.scripts.X`) instead of relative. Re-grep:

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n "^from skills\.rag" src/lib/index/*.py
```

If matches: edit each to relative (`from .X`). At planning time, all sibling imports are relative — this fallback is unlikely.

- [ ] **Step 1.7: Create test scaffolding**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  mkdir -p tests/lib/index && \
  touch tests/lib/index/__init__.py
```

- [ ] **Step 1.8: Write smoke tests**

Save to `tests/lib/index/test_index_imports.py`:

```python
"""Smoke tests for the src.lib.index public API."""
from __future__ import annotations


def test_public_api_importable():
    """11 documented public symbols importable from src.lib.index."""
    from src.lib.index import (  # noqa: F401
        BM25Index,
        RAGSearchEngine,
        count_category_entries,
        enrich_all,
        index_documents,
        index_skills,
        list_category_entries,
        read_index_entry,
        reindex_all,
        reindex_category,
        understand_document,
    )


def test_public_api_origins():
    """Symbols originate in the right submodules."""
    from src.lib.index import (
        BM25Index,
        RAGSearchEngine,
        count_category_entries,
        index_documents,
        index_skills,
        list_category_entries,
        reindex_all,
        understand_document,
    )

    assert understand_document.__module__ == "src.lib.index.document_understanding"
    assert BM25Index.__module__ == "src.lib.index.bm25_index"
    assert RAGSearchEngine.__module__ == "src.lib.index.search_engine"
    assert list_category_entries.__module__ == "src.lib.index.index_reader"
    assert count_category_entries.__module__ == "src.lib.index.index_reader"
    assert index_skills.__module__ == "src.lib.index._scanners_knowledge"
    assert reindex_all.__module__ == "src.lib.index.unified_indexer"
    assert index_documents.__module__ == "src.lib.index.unified_indexer"


def test_submodule_paths_reachable():
    """Submodule access works for callers that bypass __init__ re-exports."""
    from src.lib.index import _indexer_helpers, chunker, symbol_extractor  # noqa: F401
```

- [ ] **Step 1.9: Run lib smoke tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/lib/index/ -v 2>&1 | tail -10
```

Expected: 3 passed.

- [ ] **Step 1.10: Run rag's existing tests to confirm old path still works**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/rag/augur/tests/ 2>&1 | tail -3
```

Expected: 174 passed (old path still works — additive PR).

- [ ] **Step 1.11: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git status --short
```

Expected: only new files under `src/lib/index/` and `tests/lib/index/`.

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add src/lib/index/ tests/lib/index/ && \
  git commit -m "$(cat <<'EOF'
feat(lib): add src/lib/index/ alongside rag (additive)

Track 1 / Library 4 of the cross-client bundle architecture migration.
Libraries 1-3 already landed. This PR moves rag's 12 library .py files
from skills/rag/scripts/ to their canonical home at src/lib/index/.

This PR is additive only:
- src/lib/index/ contains verbatim copies of all 12 non-mcp .py files
  in skills/rag/scripts/ (the unified indexer + scanners + indexer
  helpers + reader + chunker + bm25 index + search engine + ocr
  extractor + symbol extractor + document understanding + enrich
  descriptions).
- New __init__.py re-exports the public API consumed by ingest, browse,
  and rag's own MCP tools.
- New smoke tests at tests/lib/index/test_index_imports.py verify the
  public API origins and submodule reachability.

The 12 .py files in skills/rag/scripts/ stay in place; consumers
continue to import via the legacy path until PRs 2-6 migrate each
consumer group. PR 7 deletes the skill-side files.

Note on scope: the Layer 4 spec named only 4 files, but sibling
dependencies (relative `from .X` imports in unified_indexer.py and
elsewhere) require all 12 to move together.
EOF
)"
```

If pre-commit hooks reject, STOP and report.

---

## Task 2: PR 2 — Migrate ingest's 3 production sites

**Files:**
- Modify: `skills/ingest/scripts/wiki_reset.py:19`
- Modify: `skills/ingest/scripts/inbox_consume.py:12, 202`

3 import sites in 2 files. Same substitution rule: replace `skills.rag.scripts.X` with `src.lib.index.X`.

- [ ] **Step 2.1: Read each site**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  sed -n '17,22p' skills/ingest/scripts/wiki_reset.py
sed -n '10,16p;200,206p' skills/ingest/scripts/inbox_consume.py
```

- [ ] **Step 2.2: Update `wiki_reset.py:19`**

Replace:
```python
from skills.rag.scripts.unified_indexer import reindex_all, reindex_category
```

with:
```python
from src.lib.index.unified_indexer import reindex_all, reindex_category
```

(Or use `from src.lib.index import reindex_all, reindex_category` — same effect via the __init__ re-export.)

- [ ] **Step 2.3: Update `inbox_consume.py:12`**

Replace:
```python
from skills.rag.scripts.document_understanding import understand_document
```

with:
```python
from src.lib.index.document_understanding import understand_document
```

- [ ] **Step 2.4: Update `inbox_consume.py:202`**

Replace:
```python
    from skills.rag.scripts.unified_indexer import index_documents
```

with:
```python
    from src.lib.index.unified_indexer import index_documents
```

(Preserve the indentation — this is a function-internal import.)

- [ ] **Step 2.5: Verify no remaining references**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n "skills\.rag\.scripts" skills/ingest/scripts/wiki_reset.py skills/ingest/scripts/inbox_consume.py
```

Expected: zero matches.

- [ ] **Step 2.6: Run ingest tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/ingest/augur/tests/ 2>&1 | tail -3
```

Expected: most pass. Some pre-existing failures may exist (not introduced by this PR).

- [ ] **Step 2.7: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add skills/ingest/scripts/wiki_reset.py skills/ingest/scripts/inbox_consume.py && \
  git commit -m "$(cat <<'EOF'
refactor(ingest): consume src.lib.index instead of skills.rag.scripts

Track 1 / Library 4 PR 2: migrate ingest's 3 production-code consumers
of rag's library to import from src.lib.index (added in PR 1).

Files updated:
- wiki_reset.py: reindex_all, reindex_category
- inbox_consume.py: understand_document (line 12) + index_documents (line 202, lazy)

The skill-side skills/rag/scripts/*.py files still exist; PR 7 deletes
them after the rest of the consumers (browse/index.py dynamic loader,
tests/unit, rag's bundle MCP, rag's own tests) migrate.

The architecture-test allowlist entry ("ingest", "rag") does NOT retire
yet — skills/ingest/augur/tests/test_rag_tools.py still imports from
skills.rag.scripts.mcp (bundle MCP, stays). That allowlist entry retires
when Track 2/3 addresses bundle MCP coupling.
EOF
)"
```

---

## Task 3: PR 3 — Migrate browse/index.py dynamic loader to static import

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/browse/index.py:192-203`

The current code at this site uses `find_skill_file` + `importlib.util.spec_from_file_location` + `exec_module` to dynamically load `skills/rag/scripts/index_reader.py`. After Library 4, the file is at `src/lib/index/index_reader.py` — a normal Python import suffices.

- [ ] **Step 3.1: Read the current state**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  sed -n '185,210p' src/mcp/augur_mcp/infrastructure/browse/index.py
```

Expected: a block doing `find_skill_file(get_project_root(), "rag", "scripts", "index_reader.py")` then `spec_from_file_location` + `exec_module`, then extracting `list_category_entries` and `count_category_entries` from the loaded module.

- [ ] **Step 3.2: Replace the dynamic loader with a static import**

Edit `src/mcp/augur_mcp/infrastructure/browse/index.py`. Find the block that starts with `import importlib.util` (around line 192) and ends after `count_category_entries = _mod.count_category_entries`. Replace the entire block:

```python
    import importlib.util
    from src.config.paths import get_project_root

    _ir = find_skill_file(get_project_root(), "rag", "scripts", "index_reader.py")
    if _ir is None:
        raise FileNotFoundError("rag index_reader.py not found in live or staged skills")

    _spec = importlib.util.spec_from_file_location("rag_index_reader", str(_ir))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    list_category_entries = _mod.list_category_entries
    count_category_entries = _mod.count_category_entries
```

with:

```python
    from src.lib.index.index_reader import (
        count_category_entries,
        list_category_entries,
    )
```

This is a behavior change: the static import fails loudly at module-load time if `src/lib/index/index_reader.py` is missing, whereas the dynamic loader would have raised `FileNotFoundError` at function-call time. For the framework, this is desirable (fail fast).

- [ ] **Step 3.3: Verify the file parses + no leftover dynamic-loader code**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run python -c "import ast; ast.parse(open('src/mcp/augur_mcp/infrastructure/browse/index.py').read()); print('OK')"
```

Expected: `OK`

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n 'find_skill_file.*"rag"\|"rag_index_reader"' src/mcp/augur_mcp/infrastructure/browse/index.py
```

Expected: zero matches.

- [ ] **Step 3.4: Check if `find_skill_file` import is now unused**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n "find_skill_file" src/mcp/augur_mcp/infrastructure/browse/index.py
```

If `find_skill_file` only appeared in the deleted block, also remove its import line at the top of the file. If it's still used elsewhere, keep it.

- [ ] **Step 3.5: Run browse tests + architecture tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/architecture/ tests/lib/index/ 2>&1 | tail -3
```

Expected: all pass.

- [ ] **Step 3.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add src/mcp/augur_mcp/infrastructure/browse/index.py && \
  git commit -m "$(cat <<'EOF'
refactor(browse-index): replace rag dynamic file-load with static import

Track 1 / Library 4 PR 3: the browse-index MCP tool implementation
replaces its `find_skill_file` + spec_from_file_location + exec_module
dynamic loader for index_reader.py with a normal
`from src.lib.index.index_reader import list_category_entries,
count_category_entries`.

Behavior change: static import fails loudly at module-load if
src/lib/index/index_reader.py is missing, whereas the dynamic loader
would raise FileNotFoundError at function-call time. For the framework
this is desirable (fail fast).

Removes 12 lines of importlib boilerplate. Consumes the canonical
src.lib.index location added in PR 1.
EOF
)"
```

---

## Task 4: PR 4 — Migrate `tests/unit/test_rag_skill_source.py`

**Files:**
- Modify: `tests/unit/test_rag_skill_source.py:17`

Single import line. One-line change.

- [ ] **Step 4.1: Read the current state**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  sed -n '15,20p' tests/unit/test_rag_skill_source.py
```

- [ ] **Step 4.2: Update the import**

Edit `tests/unit/test_rag_skill_source.py`. Replace:

```python
        from skills.rag.scripts._scanners_knowledge import index_skills
```

with:

```python
        from src.lib.index._scanners_knowledge import index_skills
```

Preserve indentation.

- [ ] **Step 4.3: Run the test**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/unit/test_rag_skill_source.py -v 2>&1 | tail -5
```

Expected: pass.

- [ ] **Step 4.4: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add tests/unit/test_rag_skill_source.py && \
  git commit -m "test(unit): consume src.lib.index._scanners_knowledge"
```

---

## Task 5: PR 5 — Migrate rag's bundle MCP wrappers

**Files:**
- Modify: `skills/rag/scripts/mcp/rag_tools.py:173, 195, 300, 343`

4 sites. The current code uses `from ..X` (parent-relative, going up to rag/scripts/, then into the library file). After this PR, all 4 use `from src.lib.index.X` (absolute).

- [ ] **Step 5.1: Read all 4 sites**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n "from \.\." skills/rag/scripts/mcp/rag_tools.py
```

Expected output:
```
173:        from ..bm25_index import BM25Index
195:    from ..search_engine import RAGSearchEngine
300:        from ..unified_indexer import index_documents, reindex_all, reindex_category
343:        from ..unified_indexer import reindex_category
```

(Line numbers may shift slightly.)

- [ ] **Step 5.2: Replace all 4 sites**

Apply the substitutions:

| Before | After |
|---|---|
| `from ..bm25_index import BM25Index` | `from src.lib.index.bm25_index import BM25Index` |
| `from ..search_engine import RAGSearchEngine` | `from src.lib.index.search_engine import RAGSearchEngine` |
| `from ..unified_indexer import index_documents, reindex_all, reindex_category` | `from src.lib.index.unified_indexer import index_documents, reindex_all, reindex_category` |
| `from ..unified_indexer import reindex_category` | `from src.lib.index.unified_indexer import reindex_category` |

Preserve indentation at each site.

- [ ] **Step 5.3: Verify no remaining `from ..X` parent-relative imports**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -n "from \.\." skills/rag/scripts/mcp/rag_tools.py
```

Expected: zero matches.

- [ ] **Step 5.4: Run rag's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/rag/augur/tests/ 2>&1 | tail -3
```

Expected: 174 passed.

- [ ] **Step 5.5: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add skills/rag/scripts/mcp/rag_tools.py && \
  git commit -m "$(cat <<'EOF'
refactor(rag): bundle MCP wrappers consume src.lib.index

Track 1 / Library 4 PR 5: migrate rag's bundle-internal MCP tool
wrappers (rag_tools.py, 4 sites) from `from ..X` parent-relative
imports to `from src.lib.index.X` absolute imports.

Sites updated (line numbers approximate):
- rag_tools.py:173 — BM25Index
- rag_tools.py:195 — RAGSearchEngine
- rag_tools.py:300 — index_documents, reindex_all, reindex_category
- rag_tools.py:343 — reindex_category

After this PR, rag's MCP tool surface no longer depends on
skills/rag/scripts/*.py via parent-relative imports. The skill-side
files still exist (PR 6 migrates rag's own tests; PR 7 deletes the
12 library files).
EOF
)"
```

---

## Task 6: PR 6 — Migrate rag's own tests

**Files:**
- Modify: `skills/rag/augur/tests/*.py` (all test files that import `from skills.rag.scripts.X`)

Bulk substitution. Per Library 2 precedent, expect 100+ references across multiple test files.

- [ ] **Step 6.1: Find all references**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -rn "from skills\.rag\.scripts\|skills\.rag\.scripts" skills/rag/augur/tests/ 2>&1 | grep -v "Binary\|__pycache__" | wc -l
```

Note the count for the commit message.

- [ ] **Step 6.2: Apply bulk substitution**

For each match, apply:

| Before | After |
|---|---|
| `from skills.rag.scripts.X import Y` | `from src.lib.index.X import Y` |
| `"skills.rag.scripts.X.Y"` (string in patch target) | `"src.lib.index.X.Y"` |
| `importlib.import_module("skills.rag.scripts.X")` | `importlib.import_module("src.lib.index.X")` |

The pattern is uniform: replace `skills.rag.scripts` with `src.lib.index` everywhere in the test files.

**Important:** Don't touch references to `skills.rag.scripts.mcp.X` — those are bundle MCP imports (the `mcp/` subdir stays). Only replace `skills.rag.scripts.<non-mcp-file>` references.

For sed-based bulk edit (be careful to NOT touch mcp paths):

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  for f in skills/rag/augur/tests/*.py; do
    # Substitute non-mcp paths only
    sed -i '' -E 's/skills\.rag\.scripts\.([^m][a-zA-Z0-9_]*)/src.lib.index.\1/g' "$f"
    sed -i '' -E 's/skills\.rag\.scripts\.m([abcdefghijklnopqrstuvwxyz][a-zA-Z0-9_]*)/src.lib.index.m\1/g' "$f"
  done
```

Or just do it carefully with explicit per-module substitutions:
```bash
sed -i '' -E 's/skills\.rag\.scripts\.unified_indexer/src.lib.index.unified_indexer/g; s/skills\.rag\.scripts\._scanners_knowledge/src.lib.index._scanners_knowledge/g; s/skills\.rag\.scripts\._scanners_structural/src.lib.index._scanners_structural/g; s/skills\.rag\.scripts\._indexer_helpers/src.lib.index._indexer_helpers/g; s/skills\.rag\.scripts\.bm25_index/src.lib.index.bm25_index/g; s/skills\.rag\.scripts\.chunker/src.lib.index.chunker/g; s/skills\.rag\.scripts\.document_understanding/src.lib.index.document_understanding/g; s/skills\.rag\.scripts\.enrich_descriptions/src.lib.index.enrich_descriptions/g; s/skills\.rag\.scripts\.index_reader/src.lib.index.index_reader/g; s/skills\.rag\.scripts\.ocr_extractor/src.lib.index.ocr_extractor/g; s/skills\.rag\.scripts\.search_engine/src.lib.index.search_engine/g; s/skills\.rag\.scripts\.symbol_extractor/src.lib.index.symbol_extractor/g' skills/rag/augur/tests/*.py
```

Use whichever is easier to verify. The explicit per-module form is safer (won't accidentally rewrite mcp paths).

- [ ] **Step 6.3: Verify no library-path references remain**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -rn "skills\.rag\.scripts\.[a-z_]*" skills/rag/augur/tests/ 2>&1 | grep -v "Binary\|__pycache__\|skills\.rag\.scripts\.mcp"
```

Expected: zero matches (only `skills.rag.scripts.mcp.*` remains, which is bundle MCP — out of scope).

- [ ] **Step 6.4: Run rag's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/rag/augur/tests/ 2>&1 | tail -3
```

Expected: 174 passed.

If a test fails because a mock target couldn't be found at the new path, double-check the substitution preserved everything after the module name (e.g., `skills.rag.scripts.unified_indexer.SOME_CONSTANT` → `src.lib.index.unified_indexer.SOME_CONSTANT`).

- [ ] **Step 6.5: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add skills/rag/augur/tests/ && \
  git commit -m "$(cat <<'EOF'
refactor(rag): tests consume src.lib.index

Track 1 / Library 4 PR 6: migrate rag's own tests from
`from skills.rag.scripts.X` imports (and equivalent string-form
patch targets) to `from src.lib.index.X`.

Bulk substitution applied across all test files in
skills/rag/augur/tests/. References to skills.rag.scripts.mcp.* are
NOT changed — those reach into the bundle MCP surface (rag_tools.py)
which stays in the bundle.

After this PR, skills/rag/ has no remaining production code or test
imports of skills.rag.scripts.X library files. PR 7 deletes the 12
library files from the skill bundle.
EOF
)"
```

---

## Task 7: PR 7 — Delete 12 skill-side library files; final verification

**Files:**
- Delete: 12 .py files in `skills/rag/scripts/` (NOT the `mcp/` subdir)

Rename-via-overlap completes here.

- [ ] **Step 7.1: Final pre-deletion check**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  grep -rn "skills\.rag\.scripts\.[a-z_]*\|skills/rag/scripts/[a-z_]*\.py" skills/ src/ apps/ tests/ 2>/dev/null | grep -v "__pycache__\|.pyc\|skills\.rag\.scripts\.mcp\|skills/rag/scripts/mcp\|skills/rag/scripts/$" | head
```

Expected: zero matches (or only comment/docstring references). If anything appears outside the deletable files themselves, STOP and report.

- [ ] **Step 7.2: Delete the 12 .py files**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  for f in _indexer_helpers _scanners_knowledge _scanners_structural bm25_index chunker document_understanding enrich_descriptions index_reader ocr_extractor search_engine symbol_extractor unified_indexer; do \
    rm "skills/rag/scripts/$f.py"; \
  done && \
  ls skills/rag/scripts/
```

Expected output:
```
__pycache__
mcp
```

- [ ] **Step 7.3: Run the full test cascade**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/lib/index/ 2>&1 | tail -3
```

Expected: 3 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/lib/extraction/ tests/lib/knowledge/ tests/lib/runtime/ 2>&1 | tail -3
```

Expected: 13 passed (Libraries 1+2+3 baselines unchanged).

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/rag/augur/tests/ 2>&1 | tail -3
```

Expected: 174 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest skills/document-extractor/augur/tests/ skills/file-manager/augur/tests/ skills/knowledge/augur/tests/ skills/augur-core/augur/tests/ 2>&1 | tail -3
```

Expected: ~374 passed (Libraries 1+2 + augur-core baselines).

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  uv run pytest tests/architecture/ tests/unit/test_rag_skill_source.py 2>&1 | tail -3
```

Expected: 3 passed (2 architecture + 1 rag_skill_source).

If any test fails, the failure is a real regression introduced by PR 7. Investigate.

- [ ] **Step 7.4: Build the dashboard**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag/apps/dashboard && \
  ls node_modules >/dev/null 2>&1 || pnpm install
```

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 7.5: Worktree pollution check**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git status --short
```

Expected: only the deleted 12 files (plus possibly dashboard regenerated artifacts which should NOT be staged).

- [ ] **Step 7.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-rag && \
  git add -A skills/rag/scripts/ && \
  git commit -m "$(cat <<'EOF'
refactor(rag): remove 12 skill-side library files; canonical at src/lib/index

Track 1 / Library 4 PR 7 — final step of rag's library extraction.
Deletes 12 .py files in skills/rag/scripts/ (the non-mcp library
files: _indexer_helpers, _scanners_knowledge, _scanners_structural,
bm25_index, chunker, document_understanding, enrich_descriptions,
index_reader, ocr_extractor, search_engine, symbol_extractor,
unified_indexer). The canonical location is now src/lib/index/.

The rag bundle keeps:
- SKILL.md, config.yaml (metadata)
- scripts/mcp/ (the MCP tool surface — rag_tools, now consuming
  src.lib.index)
- augur/tests/ (with all imports migrated to src.lib.index)
- augur/actions/, evals/, assets/

Verified after deletion:
- tests/lib/index/ — 3 passed
- tests/lib/extraction/ + knowledge/ + runtime/ — 13 passed (Libraries 1-3 baselines unchanged)
- skills/rag/augur/tests/ — 174 passed
- skills/document-extractor/ + file-manager/ + knowledge/ + augur-core/ — ~374 passed
- tests/architecture/ + tests/unit/test_rag_skill_source.py — 3 passed
- pnpm --filter dashboard build — succeeded

Track 1 / Library 4 (rag → src/lib/index/) is complete. Next library
(per Layer 4 spec ordering): ai → src/lib/ai/.

Architecture-test allowlist: NO entries retired. Both ("ingest", "rag")
and ("knowledge", "rag") remain because the rag bundle's MCP wrappers
(skills/rag/scripts/mcp/rag_tools.py) are still cross-skill imported by
ingest tests and knowledge's rag_search_cli. Those couplings retire in
Track 2/3.
EOF
)"
```

---

## Done criteria

Track 1 / Library 4 is complete when:

1. ✅ `src/lib/index/` exists with 12 .py files and a public-API `__init__.py`.
2. ✅ All consumers (ingest production, browse dynamic loader, tests/unit, rag bundle MCP wrappers, rag's own tests) import from `src.lib.index`.
3. ✅ `skills/rag/scripts/` only contains `mcp/` (and `__pycache__/`).
4. ✅ All test suites pass (lib smoke, rag, ingest, knowledge, augur-core, doc-extractor, file-manager, architecture, tests/unit/test_rag_skill_source).
5. ✅ Dashboard builds.
6. ✅ All 7 commits merged to `main`.
