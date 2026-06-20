# Track 1 / Library 2: knowledge memory subsystem → src/lib/knowledge/ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track1-knowledge`. The Library 1 worktree was already removed after merge.

**Goal:** Move knowledge's memory subsystem (11 .py files at `skills/knowledge/scripts/mcp/memory/`) to `src/lib/knowledge/` using rename-via-overlap. Migrate 1 external consumer (`src/mcp/augur_mcp/core/ask_retention.py`) plus 3 patch targets in `augur-core`'s tests, plus 4 internal bundle MCP-tool wrappers and the bundle's own tests.

**Architecture:** Five sequential PRs. PR 1 is purely additive (copy 11 files, both old and new paths work). PRs 2–4 migrate one consumer group at a time (external consumer + augur-core tests, then bundle MCP wrappers, then knowledge's own tests). PR 5 deletes `skills/knowledge/scripts/mcp/memory/`. Internal sibling imports inside the memory/ files are all RELATIVE (`from .X`) — they continue to work after the move with no changes.

**Tech Stack:** Python 3.11+, pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration (Track 1): `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Library 1 plan (reference for the rename-via-overlap pattern): `docs/superpowers/plans/2026-04-29-track1-doc-extractor-extraction.md`

## File Structure

### New files (created in PR 1)

| File | Purpose |
|---|---|
| `src/lib/knowledge/__init__.py` | Verbatim copy of `skills/knowledge/scripts/mcp/memory/__init__.py` — already exports the public API (`DailyLogger`, `MemoryStore`, `MemoryCurator`, `UnifiedSearcher`, `EventType`, `MemoryEvent`, `MemoryEntry`) |
| `src/lib/knowledge/_index.py` | Verbatim copy of `_index.py` (IndexMixin) |
| `src/lib/knowledge/_iterative.py` | Verbatim copy of `_iterative.py` (IterativeMixin) |
| `src/lib/knowledge/_ripgrep.py` | Verbatim copy of `_ripgrep.py` (RipgrepMixin) |
| `src/lib/knowledge/_types.py` | Verbatim copy of `_types.py` (SearchMode, SearchResult, MemoryEntry, SearchEvaluation, _normalize_path) |
| `src/lib/knowledge/curator.py` | Verbatim copy of `curator.py` (DistilledEntry, MemoryCurator) |
| `src/lib/knowledge/daily_logger.py` | Verbatim copy of `daily_logger.py` (DailyLogger, EventType, MemoryEvent) |
| `src/lib/knowledge/memory_store.py` | Verbatim copy of `memory_store.py` (MemoryStore, MemoryEntry) |
| `src/lib/knowledge/profile_generator.py` | Verbatim copy of `profile_generator.py` (regenerate_human_api_profile + helpers) |
| `src/lib/knowledge/search.py` | Verbatim copy of `search.py` (MemorySearcher) |
| `src/lib/knowledge/unified_search.py` | Verbatim copy of `unified_search.py` (UnifiedSearcher) |
| `tests/lib/knowledge/__init__.py` | Empty package marker |
| `tests/lib/knowledge/test_knowledge_imports.py` | Smoke tests verifying the public API loads from `src.lib.knowledge` |

Internal imports inside the 11 memory files are all relative (`from .X`, `from ._X`) — they continue to work without modification after the move.

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `src/mcp/augur_mcp/core/ask_retention.py` | 2 | Line 255: `from skills.knowledge.scripts.mcp.memory import DailyLogger` → `from src.lib.knowledge import DailyLogger`. Move from inside-function to module-top if it isn't already there. |
| `skills/augur-core/augur/tests/test_ask_retention.py` | 2 | Lines 107, 138, 180: change patch target string `"skills.knowledge.scripts.mcp.memory.DailyLogger"` → `"src.lib.knowledge.DailyLogger"` |
| `skills/knowledge/scripts/mcp/tools_memory.py` | 3 | Line 31: `from .memory import DailyLogger, MemoryStore, MemoryCurator` → `from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator` |
| `skills/knowledge/scripts/mcp/tools_memory_core.py` | 3 | Lines 23–25, 207, 234: replace 4 `from .memory...` imports with `from src.lib.knowledge...` (preserve which symbols are imported per line) |
| `skills/knowledge/scripts/mcp/tools_memory_dashboard.py` | 3 | Line 378 (lazy): `from .memory.search import MemorySearcher` → `from src.lib.knowledge.search import MemorySearcher` |
| `skills/knowledge/scripts/mcp/rag_search.py` | 3 | Line 50 (lazy): `from .memory import UnifiedSearcher` → `from src.lib.knowledge import UnifiedSearcher` |
| `skills/knowledge/augur/tests/test_knowledge.py` | 4 | Lines 68, 83, 97, 111 (and any other `from skills.knowledge.scripts.mcp.memory.X` imports): replace with `from src.lib.knowledge.X` |

### Files deleted (in PR 5)

| File | Why |
|---|---|
| `skills/knowledge/scripts/mcp/memory/__init__.py` | Library code; canonical location is `src/lib/knowledge/__init__.py` |
| `skills/knowledge/scripts/mcp/memory/_index.py` | Same |
| `skills/knowledge/scripts/mcp/memory/_iterative.py` | Same |
| `skills/knowledge/scripts/mcp/memory/_ripgrep.py` | Same |
| `skills/knowledge/scripts/mcp/memory/_types.py` | Same |
| `skills/knowledge/scripts/mcp/memory/curator.py` | Same |
| `skills/knowledge/scripts/mcp/memory/daily_logger.py` | Same |
| `skills/knowledge/scripts/mcp/memory/memory_store.py` | Same |
| `skills/knowledge/scripts/mcp/memory/profile_generator.py` | Same |
| `skills/knowledge/scripts/mcp/memory/search.py` | Same |
| `skills/knowledge/scripts/mcp/memory/unified_search.py` | Same |

After PR 5, `skills/knowledge/scripts/mcp/` no longer contains a `memory/` directory.

### What stays in the skill bundle

- `skills/knowledge/SKILL.md`, `config.yaml`
- `skills/knowledge/scripts/mcp/` minus `memory/` — all the tool wrapper files (`tools_*.py`, `rag_*.py`)
- `skills/knowledge/scripts/` standalone files (`batch_index.py`, `manage_*.py`, `index_docs.py`, etc.)
- `skills/knowledge/augur/`, `evals/`, `assets/`

## PR Sequencing

| PR | Title | Net effect | Commits |
|---|---|---|---|
| 1 | Add `src/lib/knowledge/` with smoke tests | Additive — both old and new paths work | 1 |
| 2 | Migrate `ask_retention.py` + augur-core test patches | External consumer migrated | 1 |
| 3 | Migrate knowledge's bundle MCP wrappers (4 files) | Internal consumers migrated | 1 |
| 4 | Migrate knowledge's own tests | Test imports migrated | 1 |
| 5 | Delete `skills/knowledge/scripts/mcp/memory/` | Rename-via-overlap completes | 1 |

Total: **5 commits**.

## Architecture-test allowlist

No allowlist entries get retired by Library 2. The only `(*, knowledge)` pair in `ALLOWED_CROSS_SKILL_IMPORTS` is `("knowledge", "rag")` — that's `knowledge → rag` (knowledge consuming rag), retired by **Library 4** (rag extraction), not Library 2.

Library 2 doesn't introduce new allowlist debt because:
- `src/mcp/augur_mcp/core/ask_retention.py` is `src/`, not a skill — the architecture test's cross-skill check doesn't apply
- The `skills/augur-core/augur/tests/test_ask_retention.py` patch targets are strings, not Python imports — also not flagged

---

## Task 1: PR 1 — Add `src/lib/knowledge/` (additive)

**Files:**
- Create: `src/lib/knowledge/__init__.py` (and 10 sibling .py files)
- Create: `tests/lib/knowledge/__init__.py`
- Create: `tests/lib/knowledge/test_knowledge_imports.py`

This PR is **additive only**. The 11 .py files in `skills/knowledge/scripts/mcp/memory/` remain in place. The new `src/lib/knowledge/` is an alternate, properly-importable path to the same code.

- [ ] **Step 1.1: Verify worktree is on `track1-knowledge` branch**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && git branch --show-current
```

Expected: `track1-knowledge`. If not, the `using-git-worktrees` step was skipped — go back and run it.

- [ ] **Step 1.2: Verify `src/lib/__init__.py` exists**

`src/lib/__init__.py` was created in Library 1 (Track 1 / document-extractor) and lives on `main`. Verify:

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && ls src/lib/__init__.py
```

Expected: file exists. If not, create it as an empty file (`touch src/lib/__init__.py`).

- [ ] **Step 1.3: Copy the 11 memory/ files verbatim**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  mkdir -p src/lib/knowledge && \
  cp -r skills/knowledge/scripts/mcp/memory/. src/lib/knowledge/ && \
  ls src/lib/knowledge/
```

Expected output:
```
__init__.py
_index.py
_iterative.py
_ripgrep.py
_types.py
curator.py
daily_logger.py
memory_store.py
profile_generator.py
search.py
unified_search.py
```

The `cp -r .../. <target>/` form copies all files (including hidden/dotfiles) without nesting. Verify there are no other files (no `__pycache__/`, no test files leaked) — if there are, delete them:

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  rm -rf src/lib/knowledge/__pycache__ 2>/dev/null
```

- [ ] **Step 1.4: Verify all 11 files parse cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  for f in src/lib/knowledge/*.py; do uv run python -c "import ast; ast.parse(open('$f').read())" && echo "$f OK" || echo "$f FAIL"; done
```

Expected: 11 lines, all ending in "OK".

- [ ] **Step 1.5: Verify the public API imports cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run python -c "
from src.lib.knowledge import (
    DailyLogger, EventType, MemoryEvent,
    MemoryStore, MemoryEntry,
    MemoryCurator, UnifiedSearcher,
)
print('OK', DailyLogger.__module__)
"
```

Expected: `OK src.lib.knowledge.daily_logger`

If any import fails, an internal sibling import inside one of the memory files is using an absolute path (`from skills.knowledge.scripts.mcp.memory.X`) instead of relative (`from .X`). Re-grep:

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -n "^from skills\.knowledge" src/lib/knowledge/*.py
```

If matches: edit each to a relative import (`from .X`) so the module is package-location-portable. Note: at planning time, all internal sibling imports were relative (`from ._types`, `from .daily_logger`, etc.), so this fallback shouldn't trigger.

- [ ] **Step 1.6: Verify additional public symbols are reachable via submodule paths**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run python -c "
from src.lib.knowledge.search import MemorySearcher
from src.lib.knowledge._types import SearchMode
from src.lib.knowledge.profile_generator import regenerate_human_api_profile
print('OK')
"
```

Expected: `OK`

These symbols aren't in `__init__.py`'s `__all__`; consumers reach them via direct submodule paths (the same pattern as the original code).

- [ ] **Step 1.7: Create test scaffolding**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  mkdir -p tests/lib/knowledge && \
  touch tests/lib/knowledge/__init__.py
```

- [ ] **Step 1.8: Write `tests/lib/knowledge/test_knowledge_imports.py`**

Save to `tests/lib/knowledge/test_knowledge_imports.py`:

```python
"""Smoke tests for the src.lib.knowledge public API.

Verifies the migrated memory subsystem is reachable via clean Python imports,
without sys.path tricks. Functional behavior is covered by the existing
skill-side tests in skills/knowledge/augur/tests/.
"""
from __future__ import annotations


def test_public_api_importable():
    """The 7 documented public symbols are importable from src.lib.knowledge."""
    from src.lib.knowledge import (  # noqa: F401
        DailyLogger,
        EventType,
        MemoryCurator,
        MemoryEntry,
        MemoryEvent,
        MemoryStore,
        UnifiedSearcher,
    )


def test_public_api_origin():
    """Public symbols originate in src.lib.knowledge.* (not the legacy skill path)."""
    from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator, UnifiedSearcher

    assert DailyLogger.__module__ == "src.lib.knowledge.daily_logger", (
        f"DailyLogger should come from src.lib.knowledge.daily_logger; got {DailyLogger.__module__}"
    )
    assert MemoryStore.__module__ == "src.lib.knowledge.memory_store", (
        f"MemoryStore should come from src.lib.knowledge.memory_store; got {MemoryStore.__module__}"
    )
    assert MemoryCurator.__module__ == "src.lib.knowledge.curator", (
        f"MemoryCurator should come from src.lib.knowledge.curator; got {MemoryCurator.__module__}"
    )
    assert UnifiedSearcher.__module__ == "src.lib.knowledge.unified_search", (
        f"UnifiedSearcher should come from src.lib.knowledge.unified_search; got {UnifiedSearcher.__module__}"
    )


def test_submodule_symbols_reachable():
    """Symbols not in __init__.__all__ but used by consumers (via submodule paths) still work."""
    from src.lib.knowledge.search import MemorySearcher  # noqa: F401
    from src.lib.knowledge._types import SearchMode  # noqa: F401
    from src.lib.knowledge.profile_generator import regenerate_human_api_profile  # noqa: F401


def test_memory_entry_is_dataclass():
    """MemoryEntry is the dataclass consumers expect."""
    from dataclasses import is_dataclass

    from src.lib.knowledge import MemoryEntry

    assert is_dataclass(MemoryEntry), "MemoryEntry should be a dataclass"
```

- [ ] **Step 1.9: Run the new lib tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest tests/lib/knowledge/ -v 2>&1 | tail -10
```

Expected: 4 passed.

- [ ] **Step 1.10: Run knowledge's own tests to confirm old path still works**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/knowledge/augur/tests/ 2>&1 | tail -3
```

Expected: 242 passed (or whatever the current count is — should be all green). PR 1 is additive — old `from skills.knowledge.scripts.mcp.memory.X` imports still work.

- [ ] **Step 1.11: Run augur-core's tests to confirm ask_retention's old import still works**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/augur-core/augur/tests/test_ask_retention.py 2>&1 | tail -3
```

Expected: all pass. Same reasoning — additive PR.

- [ ] **Step 1.12: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git add src/lib/knowledge/ tests/lib/knowledge/ && \
  git commit -m "$(cat <<'EOF'
feat(lib): add src/lib/knowledge/ alongside existing skill (additive)

Track 1 / Library 2 of the cross-client bundle architecture migration.
Library 1 (document-extractor) already landed at 7d31a8254. This PR
moves the next library — knowledge's memory subsystem — to its
canonical home at src/lib/knowledge/.

This PR is additive only:
- src/lib/knowledge/ contains verbatim copies of the 11 .py files in
  skills/knowledge/scripts/mcp/memory/ (DailyLogger, MemoryStore,
  MemoryCurator, UnifiedSearcher, MemorySearcher, MemoryEntry,
  SearchMode, profile_generator helpers, plus the _index/_iterative/
  _ripgrep/_types mixins).
- Internal sibling imports are all relative (from .X) and continue to
  work after the move with no changes.
- New smoke tests at tests/lib/knowledge/test_knowledge_imports.py
  verify the public API and the submodule-path-reachable symbols.

The 11 .py files in skills/knowledge/scripts/mcp/memory/ stay in place;
existing consumers (src/mcp/augur_mcp/core/ask_retention.py + 4 bundle
MCP tool wrappers + knowledge's own tests + augur-core's patch targets)
continue to import them via the old path until PRs 2-4 migrate each.

PR 5 deletes the skill-side memory/ directory.
EOF
)"
```

If pre-commit hooks reject the commit, STOP and report — do NOT skip hooks (`--no-verify` is forbidden per CLAUDE.md).

---

## Task 2: PR 2 — Migrate `ask_retention.py` + augur-core test patches

**Files:**
- Modify: `src/mcp/augur_mcp/core/ask_retention.py:255`
- Modify: `skills/augur-core/augur/tests/test_ask_retention.py:107,138,180`

The one external consumer of knowledge memory at the Python-import level. Plus 3 mock patch targets (string paths) in augur-core's tests that need to follow the canonical module location.

- [ ] **Step 2.1: Read ask_retention.py:250-260**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  sed -n '250,260p' src/mcp/augur_mcp/core/ask_retention.py
```

Confirm line 255 has:
```python
    from skills.knowledge.scripts.mcp.memory import DailyLogger
```

This is a function-internal import (not module-top). It may be wrapped in `try/except ImportError` or be plain.

- [ ] **Step 2.2: Update ask_retention.py to use `src.lib.knowledge`**

Edit `src/mcp/augur_mcp/core/ask_retention.py`. Replace line 255:

```python
    from skills.knowledge.scripts.mcp.memory import DailyLogger
```

with:

```python
    from src.lib.knowledge import DailyLogger
```

Keep the import inside the function (where it currently lives) — moving it to module top is OUT OF SCOPE for this migration. Track 3a's framework rewrite revisits the broader structure of `ask_retention.py`.

If the line was wrapped in `try/except ImportError`, preserve the wrapper. The new import should always succeed (since src/lib/knowledge ships with the framework), but keeping the wrapper preserves semantic equivalence.

- [ ] **Step 2.3: Read test_ask_retention.py patch targets**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  sed -n '105,115p;135,145p;177,188p' skills/augur-core/augur/tests/test_ask_retention.py
```

Confirm 3 patch targets at lines 107, 138, 180:
```python
        "skills.knowledge.scripts.mcp.memory.DailyLogger",
```

- [ ] **Step 2.4: Update the 3 patch targets**

Edit `skills/augur-core/augur/tests/test_ask_retention.py`. Replace each occurrence of:

```python
        "skills.knowledge.scripts.mcp.memory.DailyLogger",
```

with:

```python
        "src.lib.knowledge.DailyLogger",
```

There should be exactly 3 occurrences. After edit:

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -n "skills\.knowledge\.scripts\.mcp\.memory\|src\.lib\.knowledge\.DailyLogger" skills/augur-core/augur/tests/test_ask_retention.py
```

Expected: 3 matches, all `src.lib.knowledge.DailyLogger`. No remaining `skills.knowledge.scripts.mcp.memory` strings.

- [ ] **Step 2.5: Run augur-core's ask_retention tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/augur-core/augur/tests/test_ask_retention.py -v 2>&1 | tail -10
```

Expected: all pass. The patch targets now reference the canonical module path.

If a test fails because `src.lib.knowledge.DailyLogger` isn't patchable (e.g., `AttributeError`), `DailyLogger` may need to be importable at the package level (which it is — it's in `__all__`). Re-verify with:

```bash
uv run python -c "from src.lib.knowledge import DailyLogger; print('patchable:', hasattr(__import__('src.lib.knowledge', fromlist=['DailyLogger']), 'DailyLogger'))"
```

Expected: `patchable: True`.

- [ ] **Step 2.6: Run the architecture test**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest tests/architecture/ 2>&1 | tail -5
```

Expected: 2 passed.

- [ ] **Step 2.7: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git add src/mcp/augur_mcp/core/ask_retention.py skills/augur-core/augur/tests/test_ask_retention.py && \
  git commit -m "$(cat <<'EOF'
refactor(ask-retention): consume src.lib.knowledge instead of skills.knowledge.scripts.mcp.memory

Track 1 / Library 2 PR 2: migrate the one external consumer of
knowledge's memory subsystem from `from skills.knowledge.scripts.mcp.memory
import DailyLogger` to clean `from src.lib.knowledge import DailyLogger`
(added in PR 1).

Also updates 3 mock patch targets in skills/augur-core/augur/tests/
test_ask_retention.py from the legacy module string to the canonical
"src.lib.knowledge.DailyLogger" location.

The skill-side skills/knowledge/scripts/mcp/memory/ directory still
exists; PRs 3-4 migrate the bundle's MCP tool wrappers and the bundle's
own tests. PR 5 deletes the skill-side directory.
EOF
)"
```

---

## Task 3: PR 3 — Migrate knowledge's bundle MCP tool wrappers

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tools_memory.py:31`
- Modify: `skills/knowledge/scripts/mcp/tools_memory_core.py:23-25` (and lines 207, 234 — lazy imports)
- Modify: `skills/knowledge/scripts/mcp/tools_memory_dashboard.py:378` (lazy)
- Modify: `skills/knowledge/scripts/mcp/rag_search.py:50` (lazy)

Four files in the knowledge bundle's `mcp/` directory each import from `.memory` (relative). After this PR, they import from `src.lib.knowledge` (absolute). The skill-side `memory/` directory still exists — PR 5 deletes it.

- [ ] **Step 3.1: Read each consumer's current state**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -n "from \.memory\|from skills\.knowledge\.scripts\.mcp\.memory" \
    skills/knowledge/scripts/mcp/tools_memory.py \
    skills/knowledge/scripts/mcp/tools_memory_core.py \
    skills/knowledge/scripts/mcp/tools_memory_dashboard.py \
    skills/knowledge/scripts/mcp/rag_search.py
```

Expected output (line numbers may shift slightly):
```
tools_memory.py:31:from .memory import DailyLogger, MemoryStore, MemoryCurator
tools_memory_core.py:23:from .memory import DailyLogger, MemoryStore, MemoryCurator
tools_memory_core.py:24:from .memory.search import MemorySearcher, SearchMode
tools_memory_core.py:25:from .memory.profile_generator import regenerate_human_api_profile
tools_memory_core.py:207:            from .memory.search import MemorySearcher
tools_memory_core.py:234:            from .memory.search import MemorySearcher
tools_memory_dashboard.py:378:                from .memory.search import MemorySearcher
rag_search.py:50:    from .memory import UnifiedSearcher
```

- [ ] **Step 3.2: Update `tools_memory.py:31`**

Edit `skills/knowledge/scripts/mcp/tools_memory.py`. Replace line 31:

```python
from .memory import DailyLogger, MemoryStore, MemoryCurator
```

with:

```python
from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator
```

- [ ] **Step 3.3: Update `tools_memory_core.py` (4 sites)**

Edit `skills/knowledge/scripts/mcp/tools_memory_core.py`. Replace each `from .memory...` import:

Line 23:
```python
from .memory import DailyLogger, MemoryStore, MemoryCurator
```
→
```python
from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator
```

Line 24:
```python
from .memory.search import MemorySearcher, SearchMode
```
→
```python
from src.lib.knowledge.search import MemorySearcher
from src.lib.knowledge._types import SearchMode
```

(`SearchMode` lives in `_types.py`, not `search.py`. The original `from .memory.search import ... SearchMode` worked because `search.py:26` re-imports `SearchMode` from `_types`. The cleaner explicit form imports each from its actual module.)

Line 25:
```python
from .memory.profile_generator import regenerate_human_api_profile
```
→
```python
from src.lib.knowledge.profile_generator import regenerate_human_api_profile
```

Line 207 (lazy import inside function):
```python
            from .memory.search import MemorySearcher
```
→
```python
            from src.lib.knowledge.search import MemorySearcher
```

Line 234 (lazy import inside function):
```python
            from .memory.search import MemorySearcher
```
→
```python
            from src.lib.knowledge.search import MemorySearcher
```

- [ ] **Step 3.4: Update `tools_memory_dashboard.py:378`**

Edit `skills/knowledge/scripts/mcp/tools_memory_dashboard.py`. Replace line 378:

```python
                from .memory.search import MemorySearcher
```

with:

```python
                from src.lib.knowledge.search import MemorySearcher
```

- [ ] **Step 3.5: Update `rag_search.py:50`**

Edit `skills/knowledge/scripts/mcp/rag_search.py`. Replace line 50:

```python
    from .memory import UnifiedSearcher
```

with:

```python
    from src.lib.knowledge import UnifiedSearcher
```

- [ ] **Step 3.6: Verify no remaining `from .memory` imports in the four edited files**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -n "from \.memory" \
    skills/knowledge/scripts/mcp/tools_memory.py \
    skills/knowledge/scripts/mcp/tools_memory_core.py \
    skills/knowledge/scripts/mcp/tools_memory_dashboard.py \
    skills/knowledge/scripts/mcp/rag_search.py
```

Expected: zero matches.

- [ ] **Step 3.7: Run knowledge's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/knowledge/augur/tests/ 2>&1 | tail -5
```

Expected: 242 passed.

If tests fail because of import errors, double-check the substitutions matched the existing line shapes. The most common pitfall: tests import via patch targets that reference `.memory.X` — those would need updating in PR 4 (the test-migration PR).

- [ ] **Step 3.8: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git add skills/knowledge/scripts/mcp/tools_memory.py \
          skills/knowledge/scripts/mcp/tools_memory_core.py \
          skills/knowledge/scripts/mcp/tools_memory_dashboard.py \
          skills/knowledge/scripts/mcp/rag_search.py && \
  git commit -m "$(cat <<'EOF'
refactor(knowledge): bundle MCP wrappers consume src.lib.knowledge

Track 1 / Library 2 PR 3: migrate knowledge's bundle-internal MCP tool
wrappers from `from .memory import ...` to `from src.lib.knowledge import ...`.

Files updated:
- tools_memory.py (1 site)
- tools_memory_core.py (5 sites: top-of-file imports + 2 lazy imports inside functions)
- tools_memory_dashboard.py (1 lazy site)
- rag_search.py (1 lazy site)

Internal SearchMode lookup tightened: tools_memory_core.py now imports
SearchMode from src.lib.knowledge._types directly (its actual location)
instead of via search.py's re-export.

After this PR, no code in skills/knowledge/scripts/mcp/ uses `from .memory`.
The skill-side memory/ directory still exists (PR 4 migrates knowledge's
own tests, then PR 5 deletes the directory).
EOF
)"
```

---

## Task 4: PR 4 — Migrate knowledge's own tests

**Files:**
- Modify: `skills/knowledge/augur/tests/test_knowledge.py` (and any other test files in the same dir that import from `skills.knowledge.scripts.mcp.memory`)

The bundle's tests import from `skills.knowledge.scripts.mcp.memory.X` directly. After this PR, those imports use `src.lib.knowledge.X`.

- [ ] **Step 4.1: Find all skill-test imports of the memory subsystem**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -rn "from skills\.knowledge\.scripts\.mcp\.memory\|^import skills\.knowledge\.scripts\.mcp\.memory" \
    skills/knowledge/augur/tests/ 2>&1 | head -20
```

Expected output (per planning audit): at least 4 matches in `test_knowledge.py` lines 68, 83, 97, 111. May include more. List every match.

- [ ] **Step 4.2: Update each match**

Edit `skills/knowledge/augur/tests/test_knowledge.py` (and any other test files surfaced by Step 4.1). For each match, apply this substitution:

| Before | After |
|---|---|
| `from skills.knowledge.scripts.mcp.memory.memory_store import MemoryEntry` | `from src.lib.knowledge.memory_store import MemoryEntry` |
| `from skills.knowledge.scripts.mcp.memory import DailyLogger` | `from src.lib.knowledge import DailyLogger` |
| `from skills.knowledge.scripts.mcp.memory.X import Y` | `from src.lib.knowledge.X import Y` |

The pattern is: replace `skills.knowledge.scripts.mcp.memory` with `src.lib.knowledge` in any import line.

- [ ] **Step 4.3: Also check for and update mock patch targets in test files**

Some tests use `@patch("skills.knowledge.scripts.mcp.memory.X.Y", ...)`. These string paths must follow the canonical module location too.

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -rn 'patch.*"skills\.knowledge\.scripts\.mcp\.memory\|@patch.*skills\.knowledge\.scripts\.mcp\.memory' \
    skills/knowledge/augur/tests/ 2>&1 | head -20
```

For each match, replace the string `"skills.knowledge.scripts.mcp.memory"` with `"src.lib.knowledge"`. Preserve the rest of the path.

- [ ] **Step 4.4: Verify no remaining bareword references in knowledge's test dir**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -rn "skills\.knowledge\.scripts\.mcp\.memory" skills/knowledge/augur/tests/ 2>&1 | grep -v "^Binary"
```

Expected: zero matches.

- [ ] **Step 4.5: Run knowledge's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/knowledge/augur/tests/ 2>&1 | tail -5
```

Expected: 242 passed.

- [ ] **Step 4.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git add skills/knowledge/augur/tests/ && \
  git commit -m "$(cat <<'EOF'
refactor(knowledge): tests consume src.lib.knowledge

Track 1 / Library 2 PR 4: migrate knowledge's own tests from
`from skills.knowledge.scripts.mcp.memory.X` imports to
`from src.lib.knowledge.X`.

Mock patch target strings are also updated where they referenced the
legacy module path.

After this PR, skills/knowledge/ has no remaining references to its
own memory/ subsystem via the `skills.knowledge.scripts.mcp.memory`
path. PR 5 deletes the skill-side directory.
EOF
)"
```

---

## Task 5: PR 5 — Delete `skills/knowledge/scripts/mcp/memory/`

**Files:**
- Delete: `skills/knowledge/scripts/mcp/memory/__init__.py`
- Delete: `skills/knowledge/scripts/mcp/memory/_index.py`
- Delete: `skills/knowledge/scripts/mcp/memory/_iterative.py`
- Delete: `skills/knowledge/scripts/mcp/memory/_ripgrep.py`
- Delete: `skills/knowledge/scripts/mcp/memory/_types.py`
- Delete: `skills/knowledge/scripts/mcp/memory/curator.py`
- Delete: `skills/knowledge/scripts/mcp/memory/daily_logger.py`
- Delete: `skills/knowledge/scripts/mcp/memory/memory_store.py`
- Delete: `skills/knowledge/scripts/mcp/memory/profile_generator.py`
- Delete: `skills/knowledge/scripts/mcp/memory/search.py`
- Delete: `skills/knowledge/scripts/mcp/memory/unified_search.py`

Rename-via-overlap completes here. After this PR, the canonical (and only) location for the memory subsystem is `src/lib/knowledge/`.

- [ ] **Step 5.1: Final pre-deletion check — confirm no production-code or test references to the old paths**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -rn "skills\.knowledge\.scripts\.mcp\.memory\|skills/knowledge/scripts/mcp/memory" \
    skills/ src/ apps/ tests/ 2>/dev/null | grep -v "__pycache__\|.pyc\|/memory/" | head
```

Expected: zero matches (or only comment/docstring references that are harmless).

If anything appears outside the `/memory/` directory itself, STOP and report — the migration missed a reference.

- [ ] **Step 5.2: Verify no `from .memory` imports remain inside `skills/knowledge/scripts/mcp/`**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  grep -rn "from \.memory\b" skills/knowledge/scripts/mcp/ 2>/dev/null | grep -v "/memory/"
```

Expected: zero matches.

- [ ] **Step 5.3: Delete the 11 .py files (and the `memory/` directory)**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  rm -r skills/knowledge/scripts/mcp/memory && \
  ls skills/knowledge/scripts/mcp/
```

Expected output (no `memory/` directory):
```
__init__.py
__pycache__
rag_knowledge.py
rag_projects.py
rag_search.py
tests
tools.py
tools_index.py
tools_memory.py
tools_memory_core.py
tools_memory_dashboard.py
tools_memory_profile.py
tools_rag.py
tools_reflect.py
tools_summarize.py
```

- [ ] **Step 5.4: Run the full test cascade**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest tests/lib/knowledge/ 2>&1 | tail -3
```

Expected: 4 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest tests/lib/extraction/ 2>&1 | tail -3
```

Expected: 4 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/knowledge/augur/tests/ 2>&1 | tail -3
```

Expected: 242 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/augur-core/augur/tests/ 2>&1 | tail -3
```

Expected: all pass (including `test_ask_retention.py` with the migrated patch targets).

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest skills/document-extractor/augur/tests/ skills/rag/augur/tests/ skills/file-manager/augur/tests/ 2>&1 | tail -3
```

Expected: 35 + 174 + 73 = 282 passed (Library 1's test counts; should be unchanged).

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  uv run pytest tests/architecture/ 2>&1 | tail -3
```

Expected: 2 passed.

If any test suite fails, the failure is a real regression introduced by PR 5 (the deletions). Investigate the failure — most likely a stale reference somewhere.

- [ ] **Step 5.5: Build the dashboard to confirm no runtime regressions**

If `node_modules` is missing in this fresh worktree, install first:
```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge/apps/dashboard && \
  ls node_modules >/dev/null 2>&1 || pnpm install
```

Then build:
```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 5.6: Worktree pollution check before commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git status --short
```

Expected: only the deleted memory/ files (plus possibly dashboard regenerated artifacts which should NOT be staged).

If unrelated unmerged paths appear (`apps/dashboard/lib/plugin-runtime/assembled-hubs.json`, `skills/*/evals/rank.json`, `skills/daemon/scripts/adaptive/codex_schedule_manifest.py`), STOP and report — the controller will clean them.

- [ ] **Step 5.7: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-knowledge && \
  git add -A skills/knowledge/scripts/mcp/ && \
  git commit -m "$(cat <<'EOF'
refactor(knowledge): remove skill-side memory/; canonical at src/lib/knowledge

Track 1 / Library 2 PR 5 — final step of knowledge's library extraction.
Deletes skills/knowledge/scripts/mcp/memory/ (11 .py files: __init__,
_index, _iterative, _ripgrep, _types, curator, daily_logger,
memory_store, profile_generator, search, unified_search). The canonical
and only location for the memory subsystem is now src/lib/knowledge/.

The skill bundle keeps:
- SKILL.md, config.yaml (metadata)
- scripts/mcp/ (the MCP tool surface — tools_memory, tools_memory_core,
  tools_memory_dashboard, tools_memory_profile, tools_rag, tools_*,
  rag_*, etc., now consuming src.lib.knowledge internally)
- scripts/ standalone scripts (batch_index, manage_*, etc.)
- augur/tests/, augur/actions/, evals/, assets/

Verified after deletion:
- tests/lib/knowledge/ — 4 passed
- tests/lib/extraction/ — 4 passed (Library 1 unaffected)
- skills/knowledge/augur/tests/ — 242 passed
- skills/augur-core/augur/tests/ — all pass (ask_retention tests with migrated patches)
- skills/document-extractor/augur/tests/ — 35 passed (unchanged)
- skills/rag/augur/tests/ — 174 passed (unchanged)
- skills/file-manager/augur/tests/ — 73 passed (unchanged)
- tests/architecture/ — 2 passed
- pnpm --filter dashboard build — succeeded

Track 1 / Library 2 (knowledge memory) is complete. Next library
(per Layer 4 spec ordering): daemon library code → src/lib/runtime/.

No allowlist entries retired by this library — the only (*, knowledge)
allowlist entry is `("knowledge", "rag")` (knowledge consuming rag),
which retires when Library 4 (rag) extracts.
EOF
)"
```

---

## Done criteria

Track 1 / Library 2 is complete when:

1. ✅ `src/lib/knowledge/` exists with 11 .py files and a public-API `__init__.py`.
2. ✅ All consumers (`ask_retention.py`, `test_ask_retention.py` patch targets, 4 bundle MCP wrappers, knowledge's own tests) import from `src.lib.knowledge`.
3. ✅ `skills/knowledge/scripts/mcp/memory/` no longer exists.
4. ✅ All test suites pass (lib smoke, knowledge, augur-core, doc-extractor, rag, file-manager, architecture).
5. ✅ Dashboard builds.
6. ✅ All 5 commits merged to `main`.

After Library 2 lands, the next session brainstorms Library 3 (daemon library code → `src/lib/runtime/`).
