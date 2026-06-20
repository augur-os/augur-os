# Auto ADR Lifecycle — Design Spec

## Overview

A single autoloop skill (`auto-adr-lifecycle`) in the `hardening` loop (tier 3) that manages the full ADR lifecycle: detect orphan designs, create missing ADRs, run gap analysis on recent Accepted ADRs, and implement found gaps. Replaces `auto-orphan-plans` entirely.

## Motivation

Today, orphan design docs are detected but never acted on (`auto-orphan-plans` produces a report). Gap analysis (`/adr gaps`) and implementation (`/adr implement`) are manual. This loop closes the automation gap: designs that lack ADRs get documented, documented ADRs that lack implementation get built — all difficulty-gated for safety.

## Difficulty Gates

| Level | Phase | Actions | Risk |
|-------|-------|---------|------|
| d0 | **Scan** | Detect orphan designs, stale Proposed ADRs (>60 days), lightweight gap check on recent Accepted ADRs | Zero — read-only |
| d1 | **Document** | Create missing ADRs from orphan designs, full gap analysis on newly created + recent Accepted ADRs (30 days), write reports | Low — markdown only |
| d2 | **Implement** | Implement all found gaps in worktrees, auto-merge on completion gate pass | Medium — code changes, worktree-isolated |

## Scan Phase (d0+)

### `scan(ctx: OpsContext) -> ScanResult`

Collects three categories of issues in a single pass:

### Category 1: Orphan Designs

- Cross-reference `docs/plans/*-design.md` against ADR content in `get_vault_dir()/dev/adrs/`
- Plans not referenced by any ADR produce: `make_issue(category="adr-lifecycle", kind="actionable", orphan_type="design-doc", detail="Orphan design: {title}")`

### Category 2: Stale Proposed ADRs

- Use `adr_utils.detect_stale_status()` with 60-day threshold
- Proposed ADRs >60 days without implementation produce: `make_issue(kind="maintenance", orphan_type="stale-proposed", detail="Stale Proposed ADR: {title}")`

### Category 3: Potential Implementation Gaps

- Use `adr_utils.scan_adrs()` to collect Accepted ADRs from last 30 days
- Lightweight check: grep codebase for file paths/module names referenced in each ADR's Decision section
- ADRs where >50% of referenced paths don't exist produce: `make_issue(kind="actionable", orphan_type="impl-gap", detail="Potential implementation gaps: {title}", gap_count=N)`

### Evolution Gap

At d0, if zero issues found across all three categories:
```python
evolution_gap(
    "No ADR lifecycle issues. Consider: scanning for skills without "
    "governing ADRs, detecting ADR/code drift beyond path existence."
)
```

### Output

`ScanResult` with severity: `"warning"` if >5 issues, else `"info"`.

## Fix Phase — d1 (Document)

### Sub-phase 1a: Create Missing ADRs

For each issue with `orphan_type="design-doc"`:

1. Read the design doc fully
2. Find next ADR number via `adr_utils.find_next_adr_number()`
3. Generate ADR content: extract context/decisions/consequences/alternatives from the design doc (same logic as `/adr write` Phase 0 — absorb brainstorming)
4. Write to `get_vault_dir()/dev/adrs/ADR-{NNN}-{slug}.md` with status=Proposed
5. Classify fix via `classify_fix()` — skip if the design doc was modified by user in last 7 days
6. Track created ADR numbers for sub-phase 1b

Run post-write hooks after all ADRs created:
- Regenerate ADR index: `python .github/scripts/generate_adr_index.py`
- Regenerate agent instructions: `python3 -m skills.ai.scripts.sync_agents sync agents all`
- Commit all new ADRs + generated files in a single commit

### Sub-phase 1b: Full Gap Analysis

Target set:
- (a) ADRs created in sub-phase 1a
- (b) All Accepted ADRs from last 30 days

For each target ADR:
1. Parse the Decision section using regex for: file paths (`src/`, `skills/`, `apps/`, `config/`), MCP tool references (`@mcp.tool`, tool name strings), API route paths (`/api/`), and module imports. Extract as a list of "expected artifacts."
2. Grep codebase for each expected artifact — classify as implemented (exists), missing (not found), or partial (file exists but referenced function/class missing)
3. Score: count of unimplemented requirements per ADR
4. Produce: `make_issue(category="adr-lifecycle", kind="actionable", orphan_type="confirmed-gap", adr_number=NNN, detail="ADR-{NNN}: {count} unimplemented requirements", gap_details=[...])`

### Sub-phase 1c: Reports

Write two artifacts:
- `docs/generated/orphan-plans-report.md` — same path as before (continuity with deleted `auto-orphan-plans`)
- `docs/generated/adr-gaps-report.md` — new, gap analysis results sorted by severity

Commit reports. Return `FixResult(fix_type="report")` for gap analysis, `fix_type="sync"` for ADR creation.

## Fix Phase — d2 (Implement)

### Sub-phase 2a: Prioritize Gaps

- Read gap issues from d1 (or from persisted `adr-gaps-report.md` if d2 runs in subsequent cycle)
- Sort by severity: Critical > High > Medium
- No per-session cap — implement all found gaps. The hardening loop budget (24) naturally constrains total work.
- No cooldown on auto-generated ADRs — d1 creates, d2 implements in the same run.

### Sub-phase 2b: Implement in Worktrees

For each gap:
1. Create git worktree: `adr-{number}-{slug}`
2. Apply `/adr implement` completion gates:
   - Library code — all modules/classes written
   - Integration wiring — new code called from existing entry points
   - Tests — every requirement validated
   - Build — `npm run build` passes, no regressions
3. Scope: specific missing requirements only, not full ADR
4. On success: commit in worktree, **auto-merge to main** if all completion gates pass
5. On failure: leave worktree with partial work, report as `kind="manual"` issue
6. Requires LLM escalation (`session.has_llm == True`) — skip d2 in non-LLM daemon mode, report as `kind="manual"`

### Sub-phase 2c: Results

- `FixResult(fix_type="code-fix")` with merged branches and remaining manual gaps
- Update `adr-gaps-report.md` with implementation status per gap

### Evolution Gap at d2

If all gaps implemented and none remaining:
```python
evolution_gap(
    "All recent ADR gaps resolved. Consider: expanding scan window "
    "beyond 30 days, adding code-drift detection for Implemented ADRs, "
    "detecting undocumented architectural decisions from code patterns."
)
```

## Safety Constraints

- `classify_fix()` on every file — never overwrite files modified by user in last 7 days
- Worktree isolation for all d2 code changes — main branch untouched until gates pass
- Each sub-phase is independent — one failure doesn't abort the run
- d2 requires LLM escalation — graceful degradation to report-only without LLM

## Idempotency

Running twice at the same difficulty produces no duplicate work:
- Orphan detection checks existing ADRs before creating
- Gap analysis skips already-implemented requirements
- Worktree creation checks for existing branches

## Skill Structure

```
skills/auto-adr-lifecycle/
├── SKILL.md                          # Frontmatter + description
├── scripts/
│   └── adr_lifecycle_ops.py          # scan() + fix() ops module
└── augur/
    └── dashboard/
        └── (no pages — contributes to /adaptive/overview)
```

### SKILL.md Frontmatter

```yaml
---
name: auto-adr-lifecycle
description: >
  Full ADR lifecycle automation — detect orphan designs, create missing ADRs,
  run gap analysis on recent Accepted ADRs, implement found gaps in worktrees.
  Replaces auto-orphan-plans.
x-augur-type: autoloop
x-augur-visibility: auto
x-augur-hub: adaptive
x-augur-tab: advisor
x-augur-callable: scripts/adr_lifecycle_ops.py
x-augur-loop:
  name: hardening
  tier: 3
  trigger: nightly
x-augur-dashboard-pages:
  - /adaptive/overview
x-augur-evolution:
  last_updated: 2026-04-02T00:00:00Z
  improvements_applied: 0
---
```

### Dependencies

- `src.lib.ops_protocol` — `OpsContext`, `ScanResult`, `FixResult`, `make_issue`, `evolution_gap`, `classify_fix`, `write_report`
- `src.lib.adr_utils` — `scan_adrs`, `find_next_adr_number`, `detect_stale_status`, `find_gaps`
- `src.config.paths` — `get_vault_dir`, `get_project_root`

## Deletion

Remove `skills/auto-orphan-plans/` entirely. The orphan-plans report continues to be generated at the same path by this loop.

## Reports

| Report | Path | Content |
|--------|------|---------|
| Orphan plans | `docs/generated/orphan-plans-report.md` | Design docs without ADR references |
| ADR gaps | `docs/generated/adr-gaps-report.md` | Implementation gaps sorted by severity, updated with status after d2 |

## Error Handling

Each sub-phase is independent:
- If ADR creation fails for one orphan, the rest proceed
- If one gap implementation fails, it's reported as `kind="manual"` and the loop continues
- A single failure never aborts the entire run

## Data Flow

```
Nightly trigger (hardening loop, tier 3)
  │
  ▼
d0: scan()
  ├─ Cross-ref docs/plans/ vs vault/dev/adrs/ → orphans
  ├─ detect_stale_status(60 days) → stale Proposed
  └─ Lightweight path grep on Accepted ADRs → potential gaps
  → ScanResult(issues=[...])
  │
  ▼
d1: fix() — Document
  ├─ For each orphan design:
  │   read plan → find_next_adr_number() → write ADR
  ├─ Post-hooks: regen index + sync agents
  ├─ Gap analysis on:
  │   (a) newly created ADRs
  │   (b) Accepted ADRs from last 30 days
  │   Parse Decision section → grep codebase → score
  └─ Write orphan-plans-report.md + adr-gaps-report.md
  → FixResult(fix_type="report" | "sync")
  │
  ▼
d2: fix() — Implement
  ├─ Sort gaps by severity, no cap
  ├─ For each gap:
  │   create worktree → implement missing requirements
  │   → run completion gates → auto-merge on pass
  └─ Update adr-gaps-report.md with status
  → FixResult(fix_type="code-fix")
```
