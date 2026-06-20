# Track 1 / Library 3: daemon library code → src/lib/runtime/ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track1-daemon`.

**Goal:** Move daemon's 2 library files (`skills/daemon/augur/lib/performance_ledger.py` + `behavior_thresholds.py`) to `src/lib/runtime/` using rename-via-overlap. Migrate 1 external consumer + 1 internal consumer + 2 importability tests.

**Architecture:** Three sequential PRs. PR 1 is purely additive (copy 2 files, write `__init__.py`, smoke tests). PR 2 migrates all 4 consumer sites in 4 files. PR 3 deletes the skill-side `augur/lib/` directory. The daemon bundle keeps all 42 scripts and 5 subdirectories (`adaptive/`, `mcp/`, `monitor/`, `ops/`, `self_heal/`) — only the 2 library files in `augur/lib/` move.

**Tech Stack:** Python 3.11+, pytest, uv. No new dependencies.

**Audit reality check:** The Layer 4 spec predicted "11 importers" for daemon, but the original audit counted false positives (string path refs, subprocess invocations, self-imports). Real surface verified at planning time: 1 external Python import + 1 internal lazy import + 2 importability tests = 4 sites total.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration (Track 1): `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Library 1 plan (reference): `docs/superpowers/plans/2026-04-29-track1-doc-extractor-extraction.md`
- Library 2 plan (reference): `docs/superpowers/plans/2026-04-29-track1-knowledge-memory-extraction.md`

## File Structure

### New files (created in PR 1)

| File | Purpose |
|---|---|
| `src/lib/runtime/__init__.py` | Re-exports public API: `TaskRecord`, `record_task`, `get_aggregates`, `compact` (from performance_ledger); `AUTONOMY_THRESHOLDS`, `LEARNING_THRESHOLDS`, `AUTONOMY_LEVELS`, `LEARNING_LEVELS`, `get_action_required_level`, `get_learning_behavior_at_level`, `is_behavior_enabled` (from behavior_thresholds) |
| `src/lib/runtime/performance_ledger.py` | Verbatim copy of `skills/daemon/augur/lib/performance_ledger.py` |
| `src/lib/runtime/behavior_thresholds.py` | Verbatim copy of `skills/daemon/augur/lib/behavior_thresholds.py` |
| `tests/lib/runtime/__init__.py` | Empty package marker |
| `tests/lib/runtime/test_runtime_imports.py` | Smoke tests verifying the public API loads from `src.lib.runtime` |

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `src/mcp/augur_mcp/infrastructure/settings/system.py:20` | 2 | `from skills.daemon.augur.lib.performance_ledger import TaskRecord, record_task` → `from src.lib.runtime.performance_ledger import TaskRecord, record_task` |
| `skills/daemon/scripts/nightly_maintainer.py:258` | 2 | `from skills.daemon.augur.lib.performance_ledger import compact` → `from src.lib.runtime.performance_ledger import compact` |
| `skills/daemon/augur/tests/test_performance_ledger.py:19` | 2 | `importlib.import_module("skills.daemon.augur.lib.performance_ledger")` → `importlib.import_module("src.lib.runtime.performance_ledger")` |
| `skills/daemon/augur/tests/test_behavior_thresholds.py:19` | 2 | `importlib.import_module("skills.daemon.augur.lib.behavior_thresholds")` → `importlib.import_module("src.lib.runtime.behavior_thresholds")` |

### Files deleted (in PR 3)

| File | Why |
|---|---|
| `skills/daemon/augur/lib/performance_ledger.py` | Library code; canonical at `src/lib/runtime/performance_ledger.py` |
| `skills/daemon/augur/lib/behavior_thresholds.py` | Same |
| `skills/daemon/augur/lib/` directory | Now empty after the 2 file deletions |

### What stays in the daemon bundle

- `skills/daemon/SKILL.md`, `config.yaml`
- `skills/daemon/scripts/` — all 42 files + 5 subdirs (`adaptive/`, `mcp/`, `monitor/`, `ops/`, `self_heal/`)
- `skills/daemon/augur/tests/` (with 2 test files updated; rest unchanged)
- `skills/daemon/augur/actions/`, `evals/`, `assets/`

## PR Sequencing

| PR | Title | Net effect | Commits |
|---|---|---|---|
| 1 | Add `src/lib/runtime/` with smoke tests | Additive — both old and new paths work | 1 |
| 2 | Migrate 4 consumers (system.py + nightly_maintainer.py + 2 tests) | All consumers on canonical path | 1 |
| 3 | Delete `skills/daemon/augur/lib/` | Rename-via-overlap completes | 1 |

Total: **3 commits**.

## Architecture-test allowlist

No allowlist entries get retired by Library 3. Daemon is not in `ALLOWED_CROSS_SKILL_IMPORTS` (no skill imports daemon at the Python level except via the augur/lib/ path which the architecture test's regex doesn't catch as a `skills.daemon.scripts.*` pattern).

---

## Task 1: PR 1 — Add `src/lib/runtime/` (additive)

**Files:**
- Create: `src/lib/runtime/__init__.py`
- Create: `src/lib/runtime/performance_ledger.py`
- Create: `src/lib/runtime/behavior_thresholds.py`
- Create: `tests/lib/runtime/__init__.py`
- Create: `tests/lib/runtime/test_runtime_imports.py`

This PR is **additive only**. The 2 .py files in `skills/daemon/augur/lib/` remain in place. The new `src/lib/runtime/` is an alternate, properly-importable path to the same code.

- [ ] **Step 1.1: Verify worktree branch**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && git branch --show-current
```

Expected: `track1-daemon`. If not, STOP and report.

- [ ] **Step 1.2: Verify `src/lib/__init__.py` exists**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && ls src/lib/__init__.py
```

Expected: file exists (created in Library 1, lives on main). If not, create as empty: `touch src/lib/__init__.py`.

- [ ] **Step 1.3: Copy the 2 lib files verbatim**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  mkdir -p src/lib/runtime && \
  cp skills/daemon/augur/lib/performance_ledger.py src/lib/runtime/performance_ledger.py && \
  cp skills/daemon/augur/lib/behavior_thresholds.py src/lib/runtime/behavior_thresholds.py && \
  ls src/lib/runtime/
```

Expected output:
```
behavior_thresholds.py
performance_ledger.py
```

(`__init__.py` is added in Step 1.4.)

- [ ] **Step 1.4: Create `src/lib/runtime/__init__.py`**

Save to `src/lib/runtime/__init__.py`:

```python
"""Runtime telemetry and threshold helpers.

Migrated from skills/daemon/augur/lib/ in Track 1 of the cross-client
bundle architecture migration. The daemon bundle keeps its scripts/
subsystem (adaptive loop engine, monitors, ops, self-heal) — only these
runtime/telemetry helpers move here so external consumers (e.g.,
src/mcp/augur_mcp/infrastructure/settings/system.py) can import them
via a clean Python path.

Public API:
    TaskRecord (dataclass), record_task, get_aggregates, compact
        Performance ledger for agent task tracking (ADR-460).

    AUTONOMY_THRESHOLDS, LEARNING_THRESHOLDS,
    AUTONOMY_LEVELS, LEARNING_LEVELS,
    get_action_required_level, get_learning_behavior_at_level,
    is_behavior_enabled
        Shared behavior threshold definitions for dashboard and
        orchestrator sync.
"""
from __future__ import annotations

from src.lib.runtime.behavior_thresholds import (
    AUTONOMY_LEVELS,
    AUTONOMY_THRESHOLDS,
    LEARNING_LEVELS,
    LEARNING_THRESHOLDS,
    get_action_required_level,
    get_learning_behavior_at_level,
    is_behavior_enabled,
)
from src.lib.runtime.performance_ledger import (
    TaskRecord,
    compact,
    get_aggregates,
    record_task,
)

__all__ = [
    # Performance ledger
    "TaskRecord",
    "compact",
    "get_aggregates",
    "record_task",
    # Behavior thresholds
    "AUTONOMY_LEVELS",
    "AUTONOMY_THRESHOLDS",
    "LEARNING_LEVELS",
    "LEARNING_THRESHOLDS",
    "get_action_required_level",
    "get_learning_behavior_at_level",
    "is_behavior_enabled",
]
```

- [ ] **Step 1.5: Verify the 3 files parse cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  for f in src/lib/runtime/__init__.py src/lib/runtime/performance_ledger.py src/lib/runtime/behavior_thresholds.py; do uv run python -c "import ast; ast.parse(open('$f').read())" && echo "$f OK" || echo "$f FAIL"; done
```

Expected: 3 lines, all ending in "OK".

- [ ] **Step 1.6: Verify the public API imports cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run python -c "
from src.lib.runtime import (
    TaskRecord, record_task, compact, get_aggregates,
    AUTONOMY_THRESHOLDS, LEARNING_THRESHOLDS,
    AUTONOMY_LEVELS, LEARNING_LEVELS,
    get_action_required_level, get_learning_behavior_at_level, is_behavior_enabled,
)
print('OK', TaskRecord.__module__, get_action_required_level.__module__)
"
```

Expected: `OK src.lib.runtime.performance_ledger src.lib.runtime.behavior_thresholds`

- [ ] **Step 1.7: Create test scaffolding**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  mkdir -p tests/lib/runtime && \
  touch tests/lib/runtime/__init__.py
```

- [ ] **Step 1.8: Write `tests/lib/runtime/test_runtime_imports.py`**

Save to `tests/lib/runtime/test_runtime_imports.py`:

```python
"""Smoke tests for the src.lib.runtime public API.

Verifies the migrated runtime helpers (performance ledger + behavior thresholds)
are reachable via clean Python imports. Functional behavior is covered by the
existing skill-side tests in skills/daemon/augur/tests/.
"""
from __future__ import annotations


def test_public_api_importable():
    """All 11 documented public symbols are importable from src.lib.runtime."""
    from src.lib.runtime import (  # noqa: F401
        AUTONOMY_LEVELS,
        AUTONOMY_THRESHOLDS,
        LEARNING_LEVELS,
        LEARNING_THRESHOLDS,
        TaskRecord,
        compact,
        get_action_required_level,
        get_aggregates,
        get_learning_behavior_at_level,
        is_behavior_enabled,
        record_task,
    )


def test_performance_ledger_origin():
    """Performance ledger symbols originate in src.lib.runtime.performance_ledger."""
    from src.lib.runtime import TaskRecord, record_task, compact, get_aggregates

    assert TaskRecord.__module__ == "src.lib.runtime.performance_ledger"
    assert record_task.__module__ == "src.lib.runtime.performance_ledger"
    assert compact.__module__ == "src.lib.runtime.performance_ledger"
    assert get_aggregates.__module__ == "src.lib.runtime.performance_ledger"


def test_behavior_thresholds_origin():
    """Behavior threshold symbols originate in src.lib.runtime.behavior_thresholds."""
    from src.lib.runtime import (
        get_action_required_level,
        get_learning_behavior_at_level,
        is_behavior_enabled,
    )

    assert get_action_required_level.__module__ == "src.lib.runtime.behavior_thresholds"
    assert get_learning_behavior_at_level.__module__ == "src.lib.runtime.behavior_thresholds"
    assert is_behavior_enabled.__module__ == "src.lib.runtime.behavior_thresholds"


def test_task_record_is_dataclass():
    """TaskRecord is the dataclass consumers expect."""
    from dataclasses import is_dataclass, fields

    from src.lib.runtime import TaskRecord

    assert is_dataclass(TaskRecord)
    field_names = {f.name for f in fields(TaskRecord)}
    # Documented fields per the original definition:
    expected_fields = {"id", "timestamp", "agent", "tier", "model",
                       "tokens_in", "tokens_out", "duration_seconds",
                       "files_edited", "files_created", "outcome", "task_signals"}
    assert expected_fields.issubset(field_names), (
        f"TaskRecord missing expected fields. Got: {field_names}"
    )


def test_autonomy_thresholds_is_list():
    """AUTONOMY_THRESHOLDS is a list of dicts (the format consumers expect)."""
    from src.lib.runtime import AUTONOMY_THRESHOLDS

    assert isinstance(AUTONOMY_THRESHOLDS, list)
    assert len(AUTONOMY_THRESHOLDS) > 0
    assert all(isinstance(t, dict) for t in AUTONOMY_THRESHOLDS)
    assert all("level" in t and "action" in t for t in AUTONOMY_THRESHOLDS)
```

- [ ] **Step 1.9: Run the new lib tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest tests/lib/runtime/ -v 2>&1 | tail -10
```

Expected: 5 passed.

- [ ] **Step 1.10: Run daemon's importability tests to confirm old path still works**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest skills/daemon/augur/tests/test_performance_ledger.py skills/daemon/augur/tests/test_behavior_thresholds.py -v 2>&1 | tail -5
```

Expected: 2 passed (old `skills.daemon.augur.lib.X` path still works — additive PR).

- [ ] **Step 1.11: Worktree pollution check**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git status --short
```

Expected: only new files under `src/lib/runtime/` and `tests/lib/runtime/`. If unrelated unmerged paths appear, STOP and report.

- [ ] **Step 1.12: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git add src/lib/runtime/ tests/lib/runtime/ && \
  git commit -m "$(cat <<'EOF'
feat(lib): add src/lib/runtime/ alongside daemon's augur/lib/ (additive)

Track 1 / Library 3 of the cross-client bundle architecture migration.
Libraries 1 (document-extractor) and 2 (knowledge memory) already
landed. This PR moves daemon's 2 library files (performance_ledger.py
and behavior_thresholds.py) to their canonical home at src/lib/runtime/.

This PR is additive only:
- src/lib/runtime/ contains verbatim copies of the 2 .py files in
  skills/daemon/augur/lib/.
- New __init__.py re-exports the public API: TaskRecord, record_task,
  get_aggregates, compact (performance ledger); AUTONOMY_THRESHOLDS,
  LEARNING_THRESHOLDS, AUTONOMY_LEVELS, LEARNING_LEVELS,
  get_action_required_level, get_learning_behavior_at_level,
  is_behavior_enabled (behavior thresholds).
- New smoke tests at tests/lib/runtime/test_runtime_imports.py verify
  the public API and the dataclass shape of TaskRecord.

The 2 .py files in skills/daemon/augur/lib/ stay in place; existing
consumers (src/mcp/augur_mcp/infrastructure/settings/system.py +
skills/daemon/scripts/nightly_maintainer.py + 2 importability tests)
continue to import via the old path until PR 2 migrates them.

PR 3 deletes the skill-side augur/lib/ directory.

Note on scope: the Layer 4 spec predicted "11 importers" for daemon,
but the original audit counted false positives. Real surface verified
at planning time: 1 external + 1 internal + 2 tests = 4 consumer sites
across 4 files.
EOF
)"
```

If pre-commit hooks reject the commit, STOP and report.

---

## Task 2: PR 2 — Migrate all consumers

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/settings/system.py:20`
- Modify: `skills/daemon/scripts/nightly_maintainer.py:258`
- Modify: `skills/daemon/augur/tests/test_performance_ledger.py:19`
- Modify: `skills/daemon/augur/tests/test_behavior_thresholds.py:19`

Four consumer sites in four files. Same substitution rule: replace `skills.daemon.augur.lib` with `src.lib.runtime` in any import line or `importlib.import_module()` string argument.

- [ ] **Step 2.1: Read each consumer's current state**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  grep -n "skills\.daemon\.augur\.lib\|skills/daemon/augur/lib" \
    src/mcp/augur_mcp/infrastructure/settings/system.py \
    skills/daemon/scripts/nightly_maintainer.py \
    skills/daemon/augur/tests/test_performance_ledger.py \
    skills/daemon/augur/tests/test_behavior_thresholds.py
```

Expected output (line numbers may shift slightly):
```
src/mcp/augur_mcp/infrastructure/settings/system.py:20:    from skills.daemon.augur.lib.performance_ledger import TaskRecord, record_task
skills/daemon/scripts/nightly_maintainer.py:258:        from skills.daemon.augur.lib.performance_ledger import compact
skills/daemon/augur/tests/test_performance_ledger.py:19:    mod = importlib.import_module("skills.daemon.augur.lib.performance_ledger")
skills/daemon/augur/tests/test_behavior_thresholds.py:19:    mod = importlib.import_module("skills.daemon.augur.lib.behavior_thresholds")
```

- [ ] **Step 2.2: Update `system.py:20`**

Edit `src/mcp/augur_mcp/infrastructure/settings/system.py`. Replace:

```python
    from skills.daemon.augur.lib.performance_ledger import TaskRecord, record_task
```

with:

```python
    from src.lib.runtime.performance_ledger import TaskRecord, record_task
```

Keep the import in its current location (function-internal, if that's where it is — the leading whitespace suggests it's inside a function or `try` block). Don't move it to module top.

- [ ] **Step 2.3: Update `nightly_maintainer.py:258`**

Edit `skills/daemon/scripts/nightly_maintainer.py`. Replace:

```python
        from skills.daemon.augur.lib.performance_ledger import compact
```

with:

```python
        from src.lib.runtime.performance_ledger import compact
```

Preserve indentation (8 spaces — the import is inside `compact_performance_ledger()`).

- [ ] **Step 2.4: Update `test_performance_ledger.py:19`**

Edit `skills/daemon/augur/tests/test_performance_ledger.py`. Replace:

```python
    mod = importlib.import_module("skills.daemon.augur.lib.performance_ledger")
```

with:

```python
    mod = importlib.import_module("src.lib.runtime.performance_ledger")
```

- [ ] **Step 2.5: Update `test_behavior_thresholds.py:19`**

Edit `skills/daemon/augur/tests/test_behavior_thresholds.py`. Replace:

```python
    mod = importlib.import_module("skills.daemon.augur.lib.behavior_thresholds")
```

with:

```python
    mod = importlib.import_module("src.lib.runtime.behavior_thresholds")
```

- [ ] **Step 2.6: Verify no remaining references in the 4 edited files**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  grep -n "skills\.daemon\.augur\.lib\|skills/daemon/augur/lib" \
    src/mcp/augur_mcp/infrastructure/settings/system.py \
    skills/daemon/scripts/nightly_maintainer.py \
    skills/daemon/augur/tests/test_performance_ledger.py \
    skills/daemon/augur/tests/test_behavior_thresholds.py
```

Expected: zero matches.

- [ ] **Step 2.7: Run daemon's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest skills/daemon/augur/tests/ 2>&1 | tail -5
```

Expected: all pass (the 2 importability tests now point at `src.lib.runtime`).

- [ ] **Step 2.8: Run the consumer's tests if any (settings/system.py)**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest src/mcp/augur_mcp/infrastructure/settings/ tests/mcp/ -k "system" 2>&1 | tail -5
```

Expected: all pass (or 0 collected if no relevant tests exist).

- [ ] **Step 2.9: Run architecture tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest tests/architecture/ 2>&1 | tail -3
```

Expected: 2 passed.

- [ ] **Step 2.10: Worktree pollution check**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git status --short
```

Expected: only the 4 modified files. If unrelated unmerged paths appear, STOP and report.

- [ ] **Step 2.11: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git add src/mcp/augur_mcp/infrastructure/settings/system.py \
          skills/daemon/scripts/nightly_maintainer.py \
          skills/daemon/augur/tests/test_performance_ledger.py \
          skills/daemon/augur/tests/test_behavior_thresholds.py && \
  git commit -m "$(cat <<'EOF'
refactor(daemon): consume src.lib.runtime instead of skills.daemon.augur.lib

Track 1 / Library 3 PR 2: migrate all 4 consumers of daemon's library
files (performance_ledger + behavior_thresholds) to import from
src.lib.runtime (added in PR 1).

Files updated:
- src/mcp/augur_mcp/infrastructure/settings/system.py: external Python
  import of TaskRecord, record_task
- skills/daemon/scripts/nightly_maintainer.py: internal lazy import of
  compact (inside compact_performance_ledger())
- skills/daemon/augur/tests/test_performance_ledger.py: importlib
  importability test target
- skills/daemon/augur/tests/test_behavior_thresholds.py: same

The skill-side skills/daemon/augur/lib/ directory still exists; PR 3
deletes it.
EOF
)"
```

If pre-commit hooks reject the commit, STOP and report.

---

## Task 3: PR 3 — Delete `skills/daemon/augur/lib/`

**Files:**
- Delete: `skills/daemon/augur/lib/performance_ledger.py`
- Delete: `skills/daemon/augur/lib/behavior_thresholds.py`
- Delete: `skills/daemon/augur/lib/` (now-empty directory)

Rename-via-overlap completes here.

- [ ] **Step 3.1: Final pre-deletion check**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  grep -rn "skills\.daemon\.augur\.lib\|skills/daemon/augur/lib" \
    skills/ src/ apps/ tests/ 2>/dev/null | grep -v "__pycache__\|.pyc\|/augur/lib/" | head
```

Expected: zero matches (or only comment/docstring references that are harmless). If anything appears outside the `/augur/lib/` directory itself, STOP and report.

- [ ] **Step 3.2: Delete the 2 files (and the empty `lib/` directory)**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  rm -r skills/daemon/augur/lib && \
  ls skills/daemon/augur/
```

Expected output (no `lib/`):
```
actions
data
tests
```

(or similar — the directories present in `augur/` should remain except `lib/`).

- [ ] **Step 3.3: Run the full test cascade**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest tests/lib/runtime/ 2>&1 | tail -3
```

Expected: 5 passed.

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest tests/lib/extraction/ tests/lib/knowledge/ 2>&1 | tail -3
```

Expected: 8 passed (Library 1+2 baselines unchanged).

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest skills/daemon/augur/tests/ 2>&1 | tail -3
```

Expected: all pass (the 2 importability tests now use `src.lib.runtime`).

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest skills/document-extractor/augur/tests/ skills/rag/augur/tests/ skills/file-manager/augur/tests/ skills/knowledge/augur/tests/ 2>&1 | tail -3
```

Expected: 35 + 174 + 73 + 242 = 524 passed (Libraries 1+2 baselines unchanged).

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest skills/augur-core/augur/tests/ 2>&1 | tail -3
```

Expected: all pass (ask_retention tests unchanged from Library 2).

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  uv run pytest tests/architecture/ 2>&1 | tail -3
```

Expected: 2 passed.

If any test suite fails, the failure is a real regression introduced by PR 3 — investigate.

- [ ] **Step 3.4: Build the dashboard**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon/apps/dashboard && \
  ls node_modules >/dev/null 2>&1 || pnpm install
```

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  pnpm --filter dashboard build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 3.5: Worktree pollution check**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git status --short
```

Expected: only the deleted 2 files (plus possibly dashboard regenerated artifacts which should NOT be staged).

If unrelated unmerged paths appear, STOP and report — controller will clean.

- [ ] **Step 3.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-daemon && \
  git add -A skills/daemon/augur/lib/ && \
  git commit -m "$(cat <<'EOF'
refactor(daemon): remove skill-side augur/lib/; canonical at src/lib/runtime

Track 1 / Library 3 PR 3 — final step of daemon's library extraction.
Deletes skills/daemon/augur/lib/ (2 .py files: performance_ledger,
behavior_thresholds, plus the directory). The canonical and only
location for these runtime helpers is now src/lib/runtime/.

The daemon bundle keeps:
- SKILL.md, config.yaml (metadata)
- scripts/ (the daemon-process subsystem — adaptive loop engine,
  monitors, ops, self-heal, MCP tools, lifecycle scripts)
- augur/tests/ (with the 2 importability tests now pointing at
  src.lib.runtime)
- augur/actions/, augur/data/, evals/, assets/

Verified after deletion:
- tests/lib/runtime/ — 5 passed
- tests/lib/extraction/ + tests/lib/knowledge/ — 8 passed (Libraries 1+2 unchanged)
- skills/daemon/augur/tests/ — all pass
- skills/document-extractor/+ rag + file-manager + knowledge — 524 passed (Libraries 1+2 baselines unchanged)
- skills/augur-core/augur/tests/ — all pass
- tests/architecture/ — 2 passed
- pnpm --filter dashboard build — succeeded

Track 1 / Library 3 (daemon library code) is complete. Next library
(per Layer 4 spec ordering): rag → src/lib/index/.

No allowlist entries retired by this library — daemon was never in
ALLOWED_CROSS_SKILL_IMPORTS (its imports went via augur/lib/ which the
architecture test's regex doesn't catch as skills.daemon.scripts.* pattern).
EOF
)"
```

If pre-commit hooks reject the commit, STOP and report.

---

## Done criteria

Track 1 / Library 3 is complete when:

1. ✅ `src/lib/runtime/` exists with 2 .py files and a public-API `__init__.py`.
2. ✅ All 4 consumers (system.py, nightly_maintainer.py, 2 importability tests) import from `src.lib.runtime`.
3. ✅ `skills/daemon/augur/lib/` no longer exists.
4. ✅ All test suites pass (lib smoke, daemon, augur-core, Libraries 1+2 baselines, architecture).
5. ✅ Dashboard builds.
6. ✅ All 3 commits merged to `main`.

After Library 3 lands, the next session brainstorms Library 4 (rag → `src/lib/index/`) — the largest remaining extraction.
