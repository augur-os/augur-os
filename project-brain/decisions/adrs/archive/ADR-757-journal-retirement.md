---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-176
  - ADR-181
  - ADR-743
  - ADR-755
hub: command
tags:
  - observability
  - journal
  - job-ledger
  - retirement
superseded_by: null
spec_file: 2026-05-16-journal-retirement-design.md
plan_file: 2026-05-16-journal-retirement.md
---

# ADR-757: `journal.jsonl` Retirement — ADR-743 Job Ledger as Sole Observability Substrate

## Status

Implemented.

Implementation completed on 2026-05-16. The planned Phase 2 release-cycle soak
was explicitly waived by the owner in-session after Phase 2 tests and live
ledger-history checks passed; Phase 3 deletion proceeded with that waiver
recorded here and in the migration manifest.

## Context

Auto-loop runs today produce two parallel observability streams:

- **`journal.jsonl`** at `~/.Library/Application Support/Augur/state/adaptive/journal.jsonl` — append-only event log written by `adaptive_loop_executor.py` (file: `shared-vault/skills/daemon/scripts/adaptive/journal.py`). Predates the ADR-743 ledger; was the original run-record layer for adaptive loops.
- **ADR-743 job ledger** at `~/.Library/Application Support/Augur/state/jobs/<job-id>/` — per-job directory with `meta.json` + append-only `events.jsonl`. Newer; designed crash-safe; the lowest-common-denominator substrate for *every* dispatch path in Augur (auto-loops, dream cycle, self-heal, scheduled agents).

The two streams capture overlapping data. Adaptive loops write to **both** today. The dream cycle (ADR-744) writes to **only** the ledger. ADR-755's new orchestrator will also write to both during its migration window — but the long-term state is "one substrate, not two."

Verified during ADR-755 planning: `journal.jsonl` has real consumers outside the adaptive engine itself:

- `shared-vault/skills/daemon/scripts/mcp/_loops.py` — MCP-exposed loop history readers
- `shared-vault/skills/daemon/scripts/ops/heal_validate.py` — self-heal pipeline validation
- `shared-vault/skills/daemon/augur/tests/test_adaptive_journal.py` — direct journal tests

Retirement requires migrating each consumer to read the ledger instead, *before* the journal writes can be turned off.

## Decision

Retire `journal.jsonl` in three sequential phases, each independently shippable and revertable:

1. **Consumer migration.** For each journal reader (`mcp/_loops.py`, `ops/heal_validate.py`, the test file, plus any others surfaced by a final audit), add a ledger-derived equivalent that produces the same shape of data. Verify parity in tests (the new reader produces equivalent output for the same set of underlying runs). Old journal-reading code path stays in place behind a feature flag for one release cycle as a safety net.

2. **Write deprecation.** Once every consumer is on the ledger, gate journal writes behind an environment flag (default off). Existing `journal.jsonl` files stay on disk; new runs don't append to them. Confirm via real-world usage that no consumer regressed; one release cycle for surface bugs to appear.

3. **Code + file deletion.** Delete `adaptive/journal.py`. Delete the read-fallback code paths added in Phase 1. Optionally archive the existing `journal.jsonl` file to `~/.Library/Application Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-<date>` and remove the live path.

After this ADR ships:
- The ADR-743 ledger is the sole observability substrate for every dispatch path.
- `/dev-loops history`, `/dev-loops report`, and all MCP `loops-*` tools derive their output from the ledger.
- `shared-vault/skills/daemon/scripts/adaptive/journal.py` is deleted.
- The former live journal was archived to `~/Library/Application Support/Augur/state/adaptive/_archive/journal.jsonl.frozen-2026-05-16` and removed from `~/Library/Application Support/Augur/state/adaptive/journal.jsonl`.

## Non-Goals

- **Not changing the ADR-743 ledger schema.** Already adequate; just gains more readers.
- **Not migrating data.** The historical `journal.jsonl` content is not back-filled into the ledger. The ledger has its own historical accumulation from when adaptive loops started writing to it (in addition to the journal). The journal-only historical events stay in the archived file and are not surfaced by the new readers.
- **Not changing report formats.** `/dev-loops report` output format stays the same; only its data source changes.
- **Not touching the adaptive engine's runtime behavior.** Trust mutations, difficulty escalation, fix dispatch — all preserved exactly. Journal writes are the only thing turned off.
- **Not touching the dream cycle or ADR-755 orchestrator.** They already write to the ledger only.

## Consequences

- One observability substrate, not two. Less cognitive overhead, fewer schema-drift opportunities.
- `adaptive/journal.py` deleted; ~150 LOC removed.
- Each consumer's ledger-derived reader is purely additive in Phase 1 — old code path stays as fallback.
- Write deprecation (Phase 2) is feature-flagged, so the journal can be re-enabled in 30 seconds if a regression surfaces.
- File deletion (Phase 3) is the only irreversible step, and it only runs after a full release cycle of write deprecation has shown no consumer regression.
- Any external tooling that read `journal.jsonl` directly outside the daemon skill (e.g. a user-built dashboard script) will break in Phase 3. Mitigation: announce in the migration manifest; one-release deprecation window.
- After Phase 3, `cat ~/.Library/Application Support/Augur/state/adaptive/journal.jsonl` returns "no such file" — anyone with a personal tooling reference learns about it then. The archived `_archive/journal.jsonl.frozen-<date>` file is available for offline inspection.

## Alternatives Considered

1. **Keep both substrates forever.** Rejected — the two-stream duplication is real cognitive overhead and an ongoing source of subtle schema drift when one stream gains a new field the other doesn't.
2. **Retire the ledger and keep the journal.** Rejected — the ledger is the shared substrate for every dispatch path (auto-loops, dream, self-heal, scheduled agents). Retiring it would force every non-adaptive consumer (dream cycle, supervisor sweep) to grow journal-style writes. Wrong direction.
3. **Auto-migrate historical `journal.jsonl` content into the ledger.** Rejected — the schemas don't map cleanly (ledger is per-job dirs, journal is one append-only stream). The migration cost exceeds the value of preserving 30+ days of historical event records.
4. **Single-shot deletion (skip the feature-flag phase).** Rejected — too risky given the verified external consumers; the feature-flag step is cheap insurance against undiscovered consumers.

## Related

- ADR-176 / ADR-181 (Adaptive Loop Engine — the original home of `journal.jsonl`)
- ADR-743 (File-Based Job Ledger — the substrate that absorbs the journal's role)
- ADR-755 (Auto-Loop Runner Modernization — orthogonal; the new orchestrator writes to the ledger natively from day one)
- ADR-756 (Skill consolidation — orthogonal; can land before or after this ADR)
- ADR-758 (Routines unification — depends on this ADR for the observability layer being clean)

---

## Implementation

Run `/adr implement ADR-757` from the intended active worktree. The slash command reads this ADR's `plan_file`, reuses the current linked Augur worktree when invoked from one, creates a new implementation worktree only when invoked from the main checkout, and executes the three-phase migration via `superpowers:subagent-driven-development`. Each phase ships independently (Phase 1 is fully reversible; Phase 2 is feature-flagged; only Phase 3 is irreversible). The plan is structured so per-consumer migrations in Phase 1 are parallel-safe teammates.

Phase 3 verification used real runtime state with the legacy journal absent:
`/auto-test-pytest` reported 4016 passing tests, `/dev-loops history/status/report`
read from the ADR-743 ledger, and `self-heal --validate` produced a new
ledger-only history record at `2026-05-16T14:00:43Z`.
