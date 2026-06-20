---
title: Loop Quality Escalation Design
date: 2026-04-12
status: proposed
author: Codex
---

# Loop Quality Escalation Design

## Goal

Improve the quality of loop-generated fixes and the depth of what loops inspect and enforce, without forcing every loop into a heavy architectural workflow.

The desired end state is:

- loops are more aggressive about fixing real problems
- loops inspect more deeply when the issue warrants it
- wiki and ADR context are used only when needed
- broad structural changes are design-gated before implementation
- reports distinguish between local fixes, design-gated fixes, and blocked structural work

## Recommendation

Use `adaptive context escalation`.

Loops start with local evidence and low ceremony. They escalate only when the problem implies architectural ambiguity, ownership changes, or cross-file structural consequences.

This is preferable to:

- `always-load-context`
  - too slow
  - too noisy
  - overuses wiki/ADR context for mechanical problems
- `manually-tagged structural loops`
  - too rigid
  - misses structural findings discovered inside otherwise local loops

## Quality Model

Loop quality is split into two axes:

1. `inspection depth`
   - how much evidence the loop gathers before deciding
   - ranges from local file inspection to cross-file tracing to wiki/ADR lookup

2. `fix authority`
   - how much change the loop is allowed to make
   - ranges from mechanical patching to broad structural refactors

Core behavior:

`scan -> classify -> gather more context only if needed -> choose fix authority -> if structural, write design artifact first -> implement -> verify -> report`

## Fix Bands

### 1. Mechanical

Examples:

- path fixes
- tool-name mismatches
- response-shape mismatches
- small config drift
- generated artifact refreshes

Rules:

- no wiki required
- no design gate
- auto-fix directly
- verify immediately

### 2. Local Semantic

Examples:

- improving a command flow
- tightening validation logic
- improving reporting behavior in one area
- refactoring a small local boundary

Rules:

- local code and nearby docs first
- wiki/ADR context optional if intent is unclear
- no design gate unless the change becomes structural
- verification must match the actual surface affected

### 3. Structural

Examples:

- moving ownership between daemon and Codex
- changing scheduler or source-of-truth boundaries
- splitting loop families into new execution units
- broad refactors across skills or subsystems
- redesigning a control-plane surface

Rules:

- local evidence first
- targeted wiki + ADR context when needed
- design gate required before implementation
- verification must cover both implementation and runtime behavior

## Structural Escalation Signals

A finding becomes `structural` when one or more of these are true:

- it touches multiple subsystems
- it changes ownership or execution boundaries
- it changes prompts, schedules, or control-plane behavior
- it requires cross-file redesign rather than local repair
- intended behavior is ambiguous without prior project memory
- a relevant ADR or wiki page is likely to contain governing intent

## Context Escalation Rules

Loops should not load project memory by default. They should escalate context only after local evidence suggests it is needed.

### Context priority order

1. local code and nearby docs
2. loop implementation references
3. ADRs
4. wiki pages
5. recent loop reports and journal history

This order ensures direct code truth wins unless broader intent is required.

### Required behavior

- low-scope findings stay local
- ambiguous or boundary-changing findings trigger targeted context pull
- wiki context is selective, not global
- loops must record what context they used when they escalate

## Design-Gated Structural Flow

Structural fixes follow a stricter path:

1. detect structural issue
2. gather local code evidence
3. load targeted ADR/wiki/reference context when needed
4. synthesize a short design note
5. write or update the governing design artifact
6. implement the change
7. run focused verification
8. emit a detailed report with escalation rationale

The loop should not simulate a human brainstorming conversation. It should generate an internal design-gate artifact.

## Design Artifacts

Use two design-gate artifact types:

### ADR

Use when the loop changes:

- architecture
- ownership
- scheduler/control-plane boundaries
- long-lived system behavior

### Runtime design note

Use when the fix is structural but narrower, such as:

- limited cross-file reorganization
- operational restructuring of one loop family
- bounded internal redesign that does not rise to full ADR level

The reporting layer must include the artifact path or identifier.

## Operational Definition Of Better Fix Quality

Each loop-generated fix should be evaluated on:

- `correctness`
  - did it solve the intended issue
- `scope discipline`
  - did it avoid unrelated edits unless structural escalation justified them
- `intent alignment`
  - did it follow relevant wiki/ADR/project intent when context was needed
- `verification depth`
  - were the right checks used for the affected surface
- `report quality`
  - can a human understand why the loop acted this way

## Outcome Taxonomy

Current loop reporting is too coarse for aggressive structural behavior. Add explicit outcome categories:

- `auto-fixed`
- `report-only`
- `blocked-needs-design`
- `design-written`
- `design-gated-fixed`
- `verification-failed-reverted`
- `context-insufficient`

These outcomes should be visible both in loop reports and future browse/observability surfaces where appropriate.

## Verification Rules

Verification must scale with fix authority.

### Mechanical

- focused unit or script verification
- no broader runtime gate unless user-visible behavior changed

### Local Semantic

- focused tests
- targeted runtime or command verification where applicable

### Structural

- tests for changed areas
- runtime verification on the actual affected workflow
- evidence that the design artifact was written before implementation
- revert or mark `verification-failed-reverted` if the gate fails

## Loop-Specific Implications

This model is especially relevant for:

- `skill-quality`
  - should be able to escalate from scoring/reporting to design-gated structural skill improvements
- `observability`
  - should use project memory when redesigning monitoring surfaces or ownership boundaries
- `knowledge-enrichment`
  - should stay local for index/runtime fixes, but escalate for broader knowledge system changes
- `ui-quality`
  - should remain local for polish, but design-gate any cross-surface UX restructuring

Other loops can still trigger structural escalation if their findings justify it.

## Safety Boundary

The target posture is:

- aggressive by default
- broad structural change allowed
- but design-gated before implementation

This preserves ambition while preventing undocumented architectural drift.

## Non-Goals

This design does not:

- force wiki/ADR loading for every loop run
- require human review for every structural fix
- turn loops into full conversational planning agents
- reduce loops back to conservative report-only behavior

## Success Criteria

The design is successful when:

- loops apply more useful fixes with fewer low-confidence edits
- structural fixes use relevant project memory only when needed
- broad fixes produce explicit design artifacts before code changes
- reports clearly distinguish local fixes from design-gated structural work
- deeper inspection increases signal rather than noise

## Implementation Direction

Implementation should introduce:

- a classifier that maps findings into `mechanical`, `local semantic`, or `structural`
- a context escalation layer that can pull nearby docs, ADRs, wiki pages, and recent loop history
- a design-gate writer for ADRs or runtime notes
- richer loop outcome reporting
- stricter verification behavior tied to fix authority

Before implementation planning, the architectural parts of this design should also be reflected in the governing ADR flow required by the repo instructions.
