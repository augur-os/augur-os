# Journal retirement migration manifest (ADR-757)

Date: 2026-05-16
Scope: retire the adaptive loop `journal.jsonl` read path by moving consumers to ADR-743 job-ledger-derived records.

## Audit command

Final audit used:

```bash
rg -n "JournalWriter|JournalReader|JournalEntry|journal\\.jsonl|adaptive\\.journal|from adaptive\\.journal|import journal|journal_file|journal_dir" shared-vault/skills/daemon src tests apps -g '*.py' -g '*.ts' -g '*.tsx'
```

## Current consumers and producers

| Path | Journal API | Kind | Phase-1 owner | Migration status |
|---|---|---|---|---|
| `shared-vault/skills/daemon/scripts/adaptive/engine.py` | Creates ledger-backed history writer and reader; reads recent failures via `filter()` | Runtime read/write | Task 1 + Task 4 | Phase 3 complete: legacy writer/reader removed; ledger view is sole path |
| `shared-vault/skills/daemon/scripts/adaptive/engine_entry_runner.py` | Writes action results through `engine.journal_writer.log()` | Runtime write | Task 1 | Phase 3 complete: call shape retained; implementation writes only ADR-743 ledger events |
| `shared-vault/skills/daemon/scripts/adaptive/engine_auto_cycle.py` | Writes action results through `engine.journal_writer.log()` | Runtime write | Task 1 | Phase 3 complete: call shape retained; implementation writes only ADR-743 ledger events |
| `shared-vault/skills/daemon/scripts/adaptive/engine_fix_phase.py` | Writes action results through `engine.journal_writer.log()` | Runtime write | Task 1 | Phase 3 complete: call shape retained; implementation writes only ADR-743 ledger events |
| `shared-vault/skills/daemon/scripts/adaptive/engine_context.py` | Instantiates ledger-derived history reader for recent runtime context | Runtime read | Task 4 | Phase 3 complete: feature flag and legacy fallback removed |
| `shared-vault/skills/daemon/scripts/adaptive/cycle_helpers.py` | Reads recent failures through injected `journal_reader.filter()` | Runtime read | Task 4 | Phase 3 complete: covered by engine-injected ledger reader |
| `shared-vault/skills/daemon/scripts/adaptive/loop_reporter.py` | Reads `engine.journal_reader.read_all()` for `/dev-loops report` and status formatting | Runtime read | Task 4 | Phase 3 complete: covered by engine-injected ledger reader |
| `shared-vault/skills/daemon/scripts/adaptive/heal.py` | Consumes history-shaped entries passed by caller | Runtime read | Task 4 | Phase 3 complete: legacy `JournalEntry` import removed |
| `shared-vault/skills/daemon/scripts/adaptive/trust_ledger.py` | Accepts journal-shaped dicts in `diagnose(journal_entries)` | Runtime read | Task 4 | Phase 1 complete: CLI diagnose can supply ledger-derived records |
| `shared-vault/skills/daemon/scripts/adaptive/trust_diagnostics.py` | Detects death spirals, script errors, and budget hogs from journal-shaped dicts | Runtime read | Task 4 | Phase 1 complete: journal-shaped contract preserved |
| `shared-vault/skills/daemon/scripts/adaptive_loop_executor.py` | Reads `engine.journal_reader.read_all()` for `history`, `diagnose`, `heal`, report, and nightly cleanup | CLI read | Task 4 + Task 5 | Phase 3 complete: direct CLI uses ledger view only |
| `shared-vault/skills/daemon/scripts/mcp/_loops.py` | Reads ADR-743 jobs via `routine_orchestrator.ledger_view` for MCP status and history payloads | MCP read | Task 2 | Phase 3 complete: legacy file reader removed |
| `shared-vault/skills/daemon/scripts/adaptive/journal.py` | Former owner of `JournalWriter`, `JournalReader`, and `JournalEntry`; wrote `journal.jsonl` | Legacy substrate | Tasks 1 and 5 | Phase 3 complete: file deleted |
| `shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py` | Direct legacy writer/reader behavior tests | Test | Task 1 and Task 5 | Phase 3 complete: test deleted with legacy module |
| `shared-vault/skills/daemon/augur/tests/test_journal_writes_gated.py` | Verified disabled legacy writes during Phase 2 | Test | Task 5 | Phase 3 complete: test deleted with deprecated flag path |
| `shared-vault/skills/daemon/augur/tests/test_adaptive_loop_executor.py` | Uses ledger-view fixtures for public history behavior | Test | Task 4 + Task 5 | Phase 3 complete |
| `shared-vault/skills/daemon/augur/tests/test_engine_context.py` | Verifies structural context ordering without legacy journal fixture | Test | Task 4 | Phase 3 complete |
| `shared-vault/skills/daemon/augur/tests/test_engine_context_ledger_path.py` | Reads fixture ledger event for recent context | Test | Task 4 | Phase 1 complete |
| `shared-vault/skills/daemon/augur/tests/test_runtime_state_consumers.py` | Writes fixture ADR-743 job event for MCP loop tools | Test | Task 2 | Phase 3 complete |
| `shared-vault/skills/daemon/augur/tests/test_mcp_loops_ledger_path.py` | Verifies MCP loop payload shape in ledger-only mode | Test | Task 2 | Phase 3 complete |

## Plan drift found

- The ADR-743 job ledger implementation currently lives under `shared-vault/skills/daemon/scripts/job_ledger/`, not `routine_orchestrator/job_ledger.py`.
- `shared-vault/skills/daemon/scripts/routine_orchestrator/` does not exist yet in this checkout. ADR-757 can still create `routine_orchestrator/ledger_view.py` as a small compatibility module that imports the existing `job_ledger.job_record`.
- `shared-vault/skills/daemon/scripts/ops/heal_validate.py` does not read adaptive `journal.jsonl`; it appends a daemon-local `state/daemon/journal.log` marker. No ADR-757 code migration is required there.
- Existing ledger wrapper events only record job-level state (`pending`, `running`, terminal states) plus coarse phases such as `dispatch`. They do not carry journal fields (`loop`, `action`, `category`, `result`, `files`, `commit`, `error`, `duration_ms`). A ledger-derived history cannot be equivalent until `JournalWriter.log()` also appends a journal-shaped event into the active job's `events.jsonl`.
- `adaptive/__init__.py` is an export shim, not a Phase-1 reader. It matters for Phase 3 API removal only.

## Phase boundary

Phase 3 is complete. The planned Phase 2 release-cycle soak was explicitly
waived by the owner in-session on 2026-05-16 after Phase 2 tests and live
ledger-history checks passed. The waiver is recorded here so the irreversible
deletion is not mistaken for a completed timed soak.

Final runtime evidence:

- Archived legacy file: `~/Library/Application Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-2026-05-16` (`1932974` bytes).
- Removed live file: `~/Library/Application Support/Augur/state/adaptive/journal.jsonl` no longer exists.
- `/auto-test-pytest`: `4016 passed, 8 warnings`.
- `/dev-loops history/status/report`: completed against ADR-743 ledger history with the live journal absent.
- `self-heal --validate`: produced a new ledger-only history record for `self-heal` / `auto-file-growth` at `2026-05-16T14:00:43Z`.
