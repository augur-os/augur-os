# ADR-757 Implementation Plan — Journal Retirement

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. TDD per task (failing test first). Augur skill-test convention: load target modules via `importlib.util.spec_from_file_location`. **Independent of ADR-755 and ADR-756** — can land before either; the journal retirement touches different code paths than the orchestrator or skill consolidation.

**Goal:** Retire `~/.Library/Application Support/Augur/state/adaptive/journal.jsonl` as a parallel observability stream. ADR-743 ledger becomes the sole substrate. Migrate every verified consumer first (additive, reversible). Deprecate writes behind a feature flag (reversible). Delete code + archive file after one release cycle (irreversible).

**Architecture:** Add a translator `ledger_view.py` that produces journal-shaped records by reducing per-job ledger events. Migrate each journal-reading consumer to use the translator (gated by `AUGUR_USE_LEDGER_VIEW` flag, default off in Phase 1, default on in Phase 2). Gate journal writes by `AUGUR_DISABLE_JOURNAL_WRITES` flag (default off in Phase 1, default on in Phase 2). Phase 3 removes the flags + the file + the writer module.

**Tech Stack:** Python 3.11 stdlib; pytest with `importlib.util.spec_from_file_location`; ADR-743 ledger as the data source; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-16-journal-retirement-design.md`. **Depends on:** ADR-743 (Implemented). **Independent of:** ADR-755, ADR-756.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `shared-vault/skills/daemon/scripts/routine_orchestrator/ledger_view.py` | Translator: reads per-job ledger events, reduces to journal-equivalent record shape. Used by every migrated consumer. |
| `shared-vault/skills/daemon/augur/tests/test_ledger_view.py` | Parity tests: for a fixture run that writes to both journal and ledger, the translator's output matches the journal's records exactly. |
| `docs/migrations/2026-05-16-journal-retirement-manifest.md` | Audit table: every verified journal consumer + its migration status. Updated as each consumer migrates. |

### Modify (Phase 1)

| Path | Change |
|------|--------|
| `shared-vault/skills/daemon/scripts/mcp/_loops.py` | Add `AUGUR_USE_LEDGER_VIEW` gated path that reads via `ledger_view`. Legacy journal path preserved. |
| `shared-vault/skills/daemon/scripts/ops/heal_validate.py` | Same: feature-flagged ledger path; legacy preserved. |
| `shared-vault/skills/daemon/scripts/adaptive/engine.py` | Internal reads switch to flagged ledger path |
| `shared-vault/skills/daemon/scripts/adaptive/engine_context.py` | Same |
| `shared-vault/skills/daemon/scripts/adaptive/__init__.py` | Same |

### Modify (Phase 2)

| Path | Change |
|------|--------|
| `shared-vault/skills/daemon/scripts/adaptive/journal.py` | Gate `append()` behind `AUGUR_DISABLE_JOURNAL_WRITES` env flag |
| `shared-vault/skills/daemon/scripts/unified_daemon.py` | Set `AUGUR_DISABLE_JOURNAL_WRITES=1` and `AUGUR_USE_LEDGER_VIEW=1` in the daemon's environment by default |

### Delete (Phase 3)

| Path | Disposition |
|------|------|
| `shared-vault/skills/daemon/scripts/adaptive/journal.py` | Deleted |
| `shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py` | Deleted |
| `~/.Library/Application Support/Augur/state/adaptive/journal.jsonl` | Archived to `_archive/journal.jsonl.frozen-<date>` then removed from live path |
| Feature-flag references | Removed from every modified file |
| Legacy journal-read fallback paths | Removed from every migrated consumer |

---

## Task 0: Audit verified consumers + produce migration manifest

**Files:** Create `docs/migrations/2026-05-16-journal-retirement-manifest.md`

**Dependencies:** None.

- [x] **Step 1:** Run a final `grep -rln "journal.jsonl\|journal_path\|JournalWriter\|adaptive/journal" shared-vault src tests apps` — confirm the consumer list from the spec is exhaustive; add any newly-found references.

- [x] **Step 2:** For each consumer, document:
  - The journal API it uses (e.g. `read all entries`, `last N for loop X`)
  - Whether it's a runtime read, an MCP read, or a test
  - Its migration owner (which Phase-1 task absorbs it)

- [x] **Step 3:** Commit the manifest.

---

## Task 1: `ledger_view.py` translator + parity tests

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_orchestrator/ledger_view.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_ledger_view.py`

**Dependencies:** Task 0.

- [x] **Step 1: Write failing parity tests**

`test_ledger_view.py`:
- `test_translator_reduces_per_phase_events_to_one_run_summary` — fixture: a ledger job with 4 phase events (running, phase=scan, phase=fix, complete); translator returns one journal-equivalent record with summary fields
- `test_translator_handles_failed_runs` — fixture job ends in `failed`; record has `result="failed"`, `error` set
- `test_translator_filters_by_loop_and_category` — fixture: 3 jobs in ledger, only one matches filter; translator returns just one
- `test_translator_recent_runs_orders_by_creation_descending` — fixture: 5 jobs across 5 days; `read_recent_runs(limit=3)` returns 3 most recent in descending order

- [x] **Step 2: Implement `ledger_view.py`**

Public API:
- `read_recent_runs(loop: str | None = None, category: str | None = None, limit: int = 100) -> list[JournalRecord]` — walks the ledger, filters by `kind="loop"` + the optional loop/category, reduces each matching job to one `JournalRecord`
- `read_all_for_loop(loop: str) -> list[JournalRecord]` — equivalent to old `journal.read_all_for_loop`

`JournalRecord` dataclass mirrors the journal entry shape: `{loop, action, category, result, timestamp, files, commit, error, duration_ms}`.

Reduction logic: for each job dir, read `events.jsonl`, identify the terminal `state` (complete / failed / cancelled / timeout), pull duration from `t` deltas, extract `commit` from event messages, etc.

- [x] **Step 3:** Run tests green; commit.

---

## Task 2: Migrate `mcp/_loops.py` (parallel with Task 3)

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/mcp/_loops.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_mcp_loops_ledger_path.py`

**Dependencies:** Task 1. **Parallel-safe with Tasks 3 and 4.**

- [x] **Step 1: Write parity test**

`test_mcp_loops_ledger_path.py`: for a fixture that writes to both journal and ledger, the MCP tool's output is byte-identical whether `AUGUR_USE_LEDGER_VIEW` is set or not.

- [x] **Step 2: Implement**

Inside `_loops.py`, find each journal-reading call site. Wrap with:

```python
if os.environ.get("AUGUR_USE_LEDGER_VIEW") == "1":
    records = ledger_view.read_recent_runs(loop=loop, limit=limit)
else:
    records = journal.read_recent_runs(loop=loop, limit=limit)  # legacy path
```

- [x] **Step 3:** Run tests green with flag both set and unset (parity in both modes); commit.

---

## Task 3: Migrate `ops/heal_validate.py` (parallel with Task 2)

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/ops/heal_validate.py`
- Create: `shared-vault/skills/daemon/augur/tests/test_heal_validate_ledger_path.py`

**Dependencies:** Task 1. **Parallel-safe with Tasks 2 and 4.**

Same pattern as Task 2.

---

## Task 4: Migrate adaptive engine's internal reads (parallel with Tasks 2 + 3)

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/adaptive/engine.py`
- Modify: `shared-vault/skills/daemon/scripts/adaptive/engine_context.py`
- Modify: `shared-vault/skills/daemon/scripts/adaptive/__init__.py`

**Dependencies:** Task 1. **Parallel-safe with Tasks 2 and 3** (different files; the adaptive engine modifications are scoped to read sites only, no writes touched in this task).

Same pattern: gate each journal read with the `AUGUR_USE_LEDGER_VIEW` flag.

---

## Task 5: Phase 2 — Default flags to "on" in daemon environment

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/unified_daemon.py`
- Modify: `shared-vault/skills/daemon/scripts/adaptive/journal.py` (gate `append()` behind `AUGUR_DISABLE_JOURNAL_WRITES`)
- Create: `shared-vault/skills/daemon/augur/tests/test_journal_writes_gated.py`

**Dependencies:** Tasks 2, 3, 4 (every consumer migrated). Real-world parity validation across one release cycle in Phase 1 mode before proceeding.

- [x] **Step 1: Write test**

`test_journal_writes_gated.py`: `journal.append()` with `AUGUR_DISABLE_JOURNAL_WRITES=1` is a no-op; without the flag, writes happen as before.

- [x] **Step 2: Implement gate**

In `journal.py`'s `append()` function, return early if `os.environ.get("AUGUR_DISABLE_JOURNAL_WRITES") == "1"`.

- [x] **Step 3: Update daemon environment**

In `unified_daemon.py`, set both flags in the child process environment:
- `AUGUR_DISABLE_JOURNAL_WRITES=1`
- `AUGUR_USE_LEDGER_VIEW=1`

- [x] **Step 4:** Run tests green; commit.

- [x] **Step 5: Real-world soak waiver** — the owner explicitly waived the timed one-release-cycle soak on 2026-05-16 after Phase 2 tests and live ledger-history checks passed. The waiver is recorded in ADR-757 and the migration manifest.

---

## Task 6: Phase 3 — Code + file deletion (irreversible)

**Files:**
- Delete: `shared-vault/skills/daemon/scripts/adaptive/journal.py`
- Delete: `shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py`
- Modify: every Phase-1-migrated file (remove the legacy fallback path + the `AUGUR_USE_LEDGER_VIEW` flag check; ledger view becomes the only path)
- Modify: `shared-vault/skills/daemon/scripts/unified_daemon.py` (remove the flag-setting since the flag no longer exists)
- Move: `~/.Library/Application Support/Augur/state/adaptive/journal.jsonl` → `~/.Library/Application Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-<today>`

**Dependencies:** Task 5 + one release cycle of soak.

- [x] **Step 1: Confirm soak gate disposition** — timed soak waived by owner on 2026-05-16; Phase 3 proceeded with explicit waiver rather than claiming the timed soak completed.

- [x] **Step 2: Delete journal writer + tests**

```bash
git rm shared-vault/skills/daemon/scripts/adaptive/journal.py
git rm shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py
```

- [x] **Step 3: Remove fallback paths from consumers**

For each file modified in Tasks 2, 3, 4: remove the `if AUGUR_USE_LEDGER_VIEW: ... else: journal.read_...` branching; keep only the ledger_view path.

- [x] **Step 4: Remove flag references from `unified_daemon.py`** — flags no longer exist.

- [x] **Step 5: Archive the live file**

```bash
mkdir -p ~/Library/Application\ Support/Augur/state/adaptive/_archive/
mv ~/Library/Application\ Support/Augur/state/adaptive/journal.jsonl ~/Library/Application\ Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-$(date +%Y-%m-%d)
```

- [x] **Step 6:** Run `/auto-test-pytest`; full suite must stay green. Run a real auto-loop end-to-end and confirm `/dev-loops history` (now ledger-derived) shows the run.

Evidence: `/auto-test-pytest` reported `4016 passed, 8 warnings`; `self-heal --validate` produced a ledger-only `self-heal` / `auto-file-growth` success record at `2026-05-16T14:00:43Z` with `journal.jsonl` absent.

- [x] **Step 7:** Commit.

---

## Task 7: ADR-757 status flip + post-write hook

**Dependencies:** Task 6.

- [x] **Step 1: Flip status** Proposed → Implemented.
- [x] **Step 2: Post-write hook:**
  ```bash
  python3 .github/scripts/adr_upsert_live.py
  python3 .github/scripts/generate_adr_index.py
  python3 src/lib/index/unified_indexer.py --category adrs
  python3 -m skills.ai.scripts.sync_agents sync agents all
  ```
- [x] **Step 3:** Final commit + handoff via `superpowers:finishing-a-development-branch`.

---

## Parallelism Map

- **Task 0** (audit): sequential first
- **Task 1** (ledger_view translator): sequential after Task 0
- **Tasks 2, 3, 4** (per-consumer migrations): **parallel-safe**, 3 teammates
- **Task 5** (Phase 2 flag flip): sequential after Tasks 2–4 + one release cycle of soak
- **Task 6** (Phase 3 deletion): sequential after Task 5 + one release cycle of soak
- **Task 7** (status flip): sequential after Task 6

Critical path: **Task 0 → Task 1 → {Tasks 2,3,4 parallel} → Task 5 → soak → Task 6 → soak → Task 7** = 5 sequential code steps + 2 release cycles of soak. Without parallelism: 8 sequential code steps + soak.

---

## Rollback

- **Phase 1 (Tasks 2–4):** Fully reversible. Set `AUGUR_USE_LEDGER_VIEW=0` and consumers revert to the legacy journal path. Per-consumer migration commits are individually revertable.
- **Phase 2 (Task 5):** Fully reversible. Set `AUGUR_DISABLE_JOURNAL_WRITES=0` and journal writes resume; set `AUGUR_USE_LEDGER_VIEW=0` and reads revert to legacy. Two flag flips; no code deletion.
- **Phase 3 (Task 6):** **Irreversible** for the code+file deletion. The archived `journal.jsonl.frozen-<date>` preserves historical data for offline inspection. The 30-day soak in Phase 2 is the safety window — if anything's going to regress, it surfaces there, not after deletion.
