---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related:
  - ADR-412
  - ADR-417
  - ADR-434
  - ADR-443
hub: null
tags: []
superseded_by: null
---

# ADR-606: Remaining ADR Implementation Gaps Tracking

## Context

Across multiple long sessions, several Accepted ADRs accumulated partial implementation: ADR-443 (auto-loop safety, git-aware fixes), ADR-417 (upgrade report-only auto-commands), ADR-412 (adaptive loop hotspot system, Phase 3), and ADR-434 (migration verification test harnesses). Each had different scope, urgency, and carry-over context, and risked being lost between sessions if there was no durable index of what remained, what was completed, and where to resume.

Auto-loops were silently reverting intentional architectural changes by applying workarounds without checking git history (e.g. ADR-430/431 deleted `augur.yaml` files, auto-loops recreated them as "fixes" for broken blocks). Some report-only auto-commands (`auto-markers`, `auto-debt-scan`) were stuck at `fix_type="report"` despite ADR-417 prescribing escalation to `code-fix` at higher difficulty. ADR-412's hotspot-first deepening (Phase 3) had zero codebase matches for `hot_paths`, `hot_patterns`, or `dominant_root_cause`. ADR-434's seven test categories (`test-fresh`, `test-full`, `test-migrate`, `test-parity`, `test-sync`, `test-adr`, `test-rollback`) were entirely unimplemented.

A meta-tracking plan was needed — not as a single architectural decision, but as a working index that survives session boundaries and orients the next agent on priority order, target files, and resume points.

## Decision

Maintain `docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md` as the durable resume index for partially-implemented ADRs, with an active `/adr gaps` command surface that scans Accepted/Proposed ADRs against the codebase and surfaces unimplemented portions.

The plan documents, for each priority bucket: the governing ADR, a concise "what's missing" statement, the precise files where implementation lands (e.g. `src/lib/ops_protocol.py`, `.claude/skills/daemon/scripts/adaptive/engine_fix_phase.py`, `src/mcp/augur_framework/...`), the recommended starting test (e.g. for ADR-434, start with `test-adr` and `test-parity`), and a "Completed This Session" reference table with commit SHAs so prior progress is auditable.

Priority order:
1. **ADR-443 — Auto-Loop Safety** — `_check_git_deletion_history(path)` helper, `classify_fix(fix_type, target_path)` returning Safe/Structural/Reverting, gated apply behavior at d0/d1/d2.
2. **ADR-417 — Upgrade Report-Only Auto-Commands** — `auto-markers` TODO_CLEANUP application at d≥1; `auto-debt-scan` marker injection at d≥1 and helper extraction at d≥2.
3. **ADR-412 — Adaptive Loop Hotspot System** — persist hotspot data between cycles; add `hot_paths`, `hot_patterns`, `dominant_root_cause` to issue protocol and snapshot.
4. **ADR-434 — Migration Verification Test Harnesses** — seven test categories (`test-fresh`, `test-full`, `test-migrate`, `test-parity`, `test-sync`, `test-adr`, `test-rollback`).

Resume entry point: `/ask load docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md`. The gap-tracking process is in active use via the `/adr gaps` command surface.

## Consequences

### Positive
- Session-portable resume context — any agent can pick up where the previous left off without re-deriving priority order.
- Audit trail of completed work (commit SHAs in "Completed This Session" table) prevents accidental rework.
- Priority bucketing surfaces the right "next thing" cheaply.
- Pairs with the `/adr gaps` command surface so the index can be regenerated if it drifts.
- ADR-443, ADR-417 (`auto-markers`, `auto-debt-scan`), and ADR-412 Phase 3 hotspots have all since landed (commits `dc74a60`, `349b5b5`, `b6d9523`).

### Negative
- Plan file is human-curated and can drift from codebase reality if not refreshed; mitigated by the `/adr gaps` scanner.
- Meta-tracking docs add a layer of indirection — agents must know to load the plan before resuming.
- Priority order is one user's snapshot; new ADRs may need re-prioritization.

### Neutral
- ADR-434's seven test harnesses remain the largest open item; recommended starting points are documented.
- Plan lives in `docs/superpowers/plans/`, parallel to other multi-session plans.
- Format is informal markdown; not a registry, schema, or structured artifact.

## Alternatives Considered

### Alternative 1: Track in ADR frontmatter (e.g. `status: Partial`)
Rejected. ADR status is binary at the architectural-decision level (Proposed/Accepted/Implemented/Superseded/Deprecated); fine-grained "what's left" lives better in a plan, not in the ADR's status field.

### Alternative 2: One issue per gap in a tracker
Rejected for this project. Augur is local-first and prefers in-repo plans over external trackers; the plan + scanner combination keeps everything inside `git`.

### Alternative 3: Auto-generate the plan from a scanner
Partially adopted. The `/adr gaps` command surface scans against the codebase; the plan adds priority/sequencing/commentary that a scanner can't infer.

### Alternative 4: Inline the gaps into each governing ADR
Rejected. ADRs are decisions, not task lists. Splitting tasks across multiple ADRs hides the priority order and cross-ADR dependencies.

## References
- Plan: docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md
- ADR-412 — Adaptive Loop Adaptivity
- ADR-417 — Upgrade Report-Only Auto-Commands
- ADR-434 — Plugin Migration Verification
- ADR-443 — Autoloop Safety (Git-Aware Fixes)
