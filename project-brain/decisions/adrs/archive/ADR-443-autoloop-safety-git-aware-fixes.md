---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related:
  - ADR-430
  - ADR-431
hub: system
tags:
  - auto-loop
  - safety
  - adaptive-engine
  - git
superseded_by: null
---

# ADR-443: Auto-Loop Safety — Git-Aware Fix Classification

## Context

The adaptive engine's auto-loops can silently revert intentional architectural changes. When an auto-loop detects a "broken" state — a missing file, a broken reference, a removed config key — it applies a fix without understanding whether the breakage was deliberate.

**Real incident**: ADR-430 and ADR-431 intentionally deleted `augur.yaml` files as part of the skill metadata migration to `SKILL.md` frontmatter. Auto-loops detected missing `augur.yaml` files, classified them as broken data sources, and recreated them — effectively reverting the ADR implementation without human knowledge. The auto-loop was doing exactly what it was designed to do (fix broken things), but it lacked the context to distinguish "intentionally removed" from "accidentally broken."

This class of problem will recur with every architectural migration that removes or restructures files. Without a classification gate, auto-loops are a liability during any deliberate cleanup.

## Decision

Introduce a three-layer safety system for auto-loop fixes: **pre-fix git history check**, **fix classification gate**, and **migration-incomplete reporting**.

### 1. Pre-Fix Git History Check

Before any auto-loop creates or restores a file, run `git log --diff-filter=D -- <file>` to check if the file was recently deleted. If the file was deleted within 7 days and the commit message references an ADR (`ADR-\d+`), classify the fix as "Reverting" and block it.

Add a `_check_git_deletion_history(path: str) -> DeletionInfo | None` helper to `ops_protocol.py` that returns:
- `None` if the file has no deletion history
- A `DeletionInfo` dataclass with `deleted_date`, `commit_hash`, `commit_message`, and `adr_reference` (extracted ADR number or `None`)

### 2. Fix Classification Gate

All auto-loop fixes must be classified before application:

| Classification | Criteria | Action |
|---------------|----------|--------|
| Safe | Formatting, lint, marker updates | Apply + commit |
| Structural | Missing files, broken data sources, deleted references | Report only, no auto-fix |
| Reverting | Recreating a recently deleted file, re-adding removed config | Block + alert human |

Add `classify_fix(fix_type: str, target_path: str) -> FixClassification` to `ops_protocol.py` that:
1. Determines base classification from `fix_type` (formatting → Safe, missing file → Structural)
2. Calls `_check_git_deletion_history(target_path)` for Structural fixes
3. Escalates to Reverting if the file was deleted within 7 days with an ADR reference

### 3. Migration-Incomplete Reporting

When an auto-loop detects a broken reference caused by a deliberate deletion, it must not attempt a fix. Instead, report `kind: "migration-incomplete"` with the ADR number. This surfaces the real problem — a consumer that was not migrated to the new pattern — instead of masking it by recreating the deleted artifact.

Example output:
```yaml
kind: migration-incomplete
adr: ADR-430
deleted_file: .claude/skills/career/augur.yaml
affected_consumer: config/dashboard/career.yaml
message: "File was intentionally deleted by ADR-430. Consumer needs migration, not file restoration."
```

### Difficulty-Based Gating

Auto-loop difficulty level constrains which fix classifications can be applied:

- **Difficulty 0–1**: Only Safe fixes (formatting, lint, markers)
- **Difficulty 2+**: Safe + Structural fixes (with logging)
- **All difficulties**: Reverting fixes always require human approval

### Implementation Files

- `ops_protocol.py`: Add `_check_git_deletion_history()`, `classify_fix()`, `DeletionInfo` dataclass, `FixClassification` enum
- `engine_fix_phase.py`: Call `classify_fix()` before applying any fix; gate on difficulty level
- Auto-loop reporters: Emit `migration-incomplete` entries alongside existing `evolution_gap` entries

## Consequences

### Positive

- Auto-loops cannot silently revert intentional architectural changes
- Migration gaps are surfaced as actionable reports instead of being masked by workarounds
- Difficulty-based gating prevents low-confidence loops from making structural changes
- The 7-day window provides a safety net during active migrations without permanently blocking fixes

### Negative

- Legitimate fixes for accidentally deleted files may be delayed by the classification gate
- Git history checks add subprocess overhead to each fix evaluation
- The 7-day window is a heuristic — long-running migrations may need manual extension

### Neutral

- Existing Safe-class fixes (formatting, lint) are unaffected
- The classification gate is additive — no existing fix logic is removed, only gated
- Human-initiated fixes bypass classification entirely (this only applies to auto-loop fixes)

## Alternatives Considered

### Alternative 1: Allowlist/Denylist of Protected Paths

Maintain a static list of paths that auto-loops should not touch.

**Rejected because**: Requires manual maintenance on every migration. Paths would go stale. The git history approach is self-maintaining — it automatically knows what was recently deleted and why.

### Alternative 2: ADR-Aware Lockfiles

Each ADR implementation writes a lockfile listing affected paths, and auto-loops check against it.

**Rejected because**: Adds a new artifact to maintain and risks going stale. Git history already contains this information with higher fidelity (exact timestamps, commit messages, diff context).

### Alternative 3: Disable Auto-Loops During Migrations

Pause all auto-loops when a migration is in progress.

**Rejected because**: Overly broad — Safe fixes (lint, formatting) should still run. The classification gate allows fine-grained control without an all-or-nothing switch.

## References

- ADR-430: Skill metadata migration (triggered the incident)
- ADR-431: Plugin decentralization (related deletions)
- `ops_protocol.py`: Evolution gap reporting (`evolution_gap()`)
- `engine_fix_phase.py`: Auto-loop fix application logic
- CLAUDE.md Rule 5: No workarounds — fix root cause, not fallbacks
- CLAUDE.md Rule 8: Auto-loops must evolve

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "New function: _check_git_deletion_history() in ops_protocol.py"
    - "New function: classify_fix() in ops_protocol.py"
    - "New dataclass: DeletionInfo in ops_protocol.py"
    - "New enum: FixClassification in ops_protocol.py"
    - "New report kind: migration-incomplete in auto-loop output"
  patterns_deprecated:
    - "Unclassified auto-loop fixes (all fixes must now pass classification gate)"
  files_affected:
    - "ops_protocol.py"
    - "engine_fix_phase.py"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-443-autoloop-safety`

### Phase 1: Core Classification Engine
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | Add `DeletionInfo` dataclass, `FixClassification` enum, `_check_git_deletion_history()`, and `classify_fix()` to ops_protocol.py | `ops_protocol.py` |
| 1.2 | backend | medium | Modify `engine_fix_phase.py` to call `classify_fix()` before applying fixes; gate on difficulty level; emit `migration-incomplete` reports | `engine_fix_phase.py` |

### Phase 2: Testing
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | tester | medium | Test: deleted file within 7 days with ADR ref → fix blocked as Reverting | `test_fix_classification.py` |
| 2.2 | tester | low | Test: deleted file older than 7 days → fix allowed as Structural | `test_fix_classification.py` |
| 2.3 | tester | low | Test: new file (never existed) → fix allowed | `test_fix_classification.py` |
| 2.4 | tester | medium | Test: ADR-referenced deletion → migration-incomplete report emitted | `test_fix_classification.py` |

### Completion Criteria
- [ ] All fixes pass through classification gate before application
- [ ] Reverting fixes are blocked at all difficulty levels
- [ ] migration-incomplete reports include ADR number and affected consumer
- [ ] All tests pass
- [ ] ADR status updated to Implemented
