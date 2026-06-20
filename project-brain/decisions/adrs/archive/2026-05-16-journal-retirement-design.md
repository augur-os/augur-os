---
date: 2026-05-16
status: Draft
adr: ADR-757
deciders:
  - gsannikov
related:
  - ADR-176
  - ADR-743
  - ADR-755
---

# Journal Retirement — Design

> Design spec for **ADR-757**. Companion to `docs/adrs/ADR-757-journal-retirement.md`.

## Goal

Retire `adaptive/journal.jsonl` as a parallel observability stream. The ADR-743 ledger becomes the sole substrate. Each existing journal consumer migrates to ledger-derived equivalents; journal writes are deprecated behind a feature flag; finally the file + write code are deleted. Three phases, each shippable independently.

## Verified consumers (audit during ADR-755 work)

```
shared-vault/skills/daemon/scripts/mcp/_loops.py           # MCP loop history readers
shared-vault/skills/daemon/scripts/ops/heal_validate.py    # self-heal pipeline validation
shared-vault/skills/daemon/scripts/adaptive/engine.py      # reads its own writes
shared-vault/skills/daemon/scripts/adaptive/engine_context.py
shared-vault/skills/daemon/scripts/adaptive/__init__.py
shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py
shared-vault/skills/daemon/augur/tests/test_runtime_state_consumers.py
shared-vault/skills/daemon/augur/tests/test_engine_context.py
```

External (out-of-repo) consumers: unknown. Mitigation: announce in the migration manifest with one-release deprecation window before Phase 3.

## Mapping journal events to ledger events

Journal event shape (today):
```json
{"loop":"testing","action":"run","category":"auto-test-build","result":"success","timestamp":"...","files":[...],"commit":"abc","error":null,"duration_ms":4500}
```

ADR-743 ledger event shape:
```json
{"state":"running"|"complete"|"failed","t":"...","msg":"...","phase":"...","..."}
```

The ledger captures everything the journal captures, but with finer per-phase granularity. The migration adds a small `ledger_to_journal_view()` translator at the consumer boundary — produces journal-shaped records by reducing a job's ledger events into one summary line per category.

This translator lives in `routine_orchestrator/ledger_view.py` (under ADR-755's module so it's available from the orchestrator + the legacy engine + the MCP readers).

## Three phases in detail

### Phase 1 — Consumer migration (parallel-safe per consumer)

For each journal consumer:

1. Identify the journal-derived API the consumer uses (read entire file, last-N entries, filter by loop/category, etc.).
2. Add an equivalent that reads from the ledger via `ledger_view.read_recent_runs(loop=..., category=..., limit=...)` and returns the same shape via the translator.
3. Behind a flag (env var: `AUGUR_USE_LEDGER_VIEW=1`), the consumer uses the new path. Default still uses journal.
4. Parity tests: for a fixture run that writes to both, the new ledger-derived API produces the same records as the legacy journal-derived API.

This is purely additive — old code path stays. Reversible by simply not setting the flag.

### Phase 2 — Write deprecation (feature-flagged)

Once every consumer has the ledger-derived path passing parity:

1. Add a flag (env var: `AUGUR_DISABLE_JOURNAL_WRITES=1`) gating `journal.py`'s append calls.
2. Set the flag default to `1` in the daemon supervisor's environment.
3. Default the consumer flag (`AUGUR_USE_LEDGER_VIEW`) to `1` in the same release.
4. Existing `journal.jsonl` stays on disk; new runs don't append. Existing read-via-journal code paths are now dormant but present.

Reversible by un-setting either flag. One full release cycle for surface bugs to appear in real-world usage.

### Phase 3 — Code + file deletion (irreversible)

After one release cycle of Phase 2 being stable:

1. Delete `shared-vault/skills/daemon/scripts/adaptive/journal.py`.
2. Delete the journal-read fallback paths in each consumer.
3. Delete the `AUGUR_USE_LEDGER_VIEW` / `AUGUR_DISABLE_JOURNAL_WRITES` flags (no longer needed; ledger view is the only path).
4. Optionally archive existing `journal.jsonl` files: rename to `~/.Library/Application Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-<date>` so historical data is preserved for offline inspection but isn't on the read path.
5. Delete `shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py` (the journal tests).

After Phase 3: `journal.py` gone, no live `journal.jsonl`, every read path goes through the ledger.

## Risks

- **Undiscovered external consumers.** A user's personal dashboard or CI integration might tail `journal.jsonl` directly. Mitigation: Phase 2's feature-flag period gives external consumers a release cycle to notice and migrate. Phase 3 documents the irrevocability in CHANGELOG / migration manifest.
- **Parity test gaps.** The ledger captures more granular per-phase events than the journal's per-run summary. The translator's reduction must be deterministic — same set of phase events always reduces to the same journal-equivalent line. Mitigation: comprehensive parity tests in Phase 1 covering all observed event shapes.
- **Ledger volume.** The ledger stores per-job dirs; long-running deployments accumulate many. Mitigation: ADR-743's supervisor sweep already handles retention; this ADR doesn't touch that.

## What does NOT change

- ADR-743 ledger schema, file layout, supervisor sweep behavior — all unchanged.
- Adaptive engine runtime behavior, trust calculations, fix dispatch — unchanged.
- `/dev-loops` slash command UX — unchanged. (Its `history` and `report` verbs derive from ledger instead of journal; output format preserved.)
- The dream cycle and ADR-755 orchestrator — already write to the ledger natively; unaffected by this ADR.
