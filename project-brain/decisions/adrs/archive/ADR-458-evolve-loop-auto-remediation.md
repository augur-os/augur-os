---
status: Implemented
date: 2026-03-20
deciders:
  - gsannikov
related:
  - ADR-102
  - ADR-256
hub: null
tags:
  - adaptive-engine
  - self-improvement
  - evolve
superseded_by: null
---

# ADR-458: Evolve Loop Auto-Remediation

## Context

The adaptive loop engine has a `--evolve` flag that runs self-improvement analysis after each cycle. It correctly identifies scanners that are stuck in "report-only" mode — they find issues but their `fix()` never produces code changes. The evolve output looks like:

```
── Prioritized improvements (by issue count) ──
  1. auto-seed-data (115 issues, report-only)
     → Upgrade fix() from report-only to actual code changes
  2. auto-markers (19 issues, report-only)
     → Add auto-resolution for TODO_CLEANUP markers
```

**The problem:** This analysis is printed to stdout and discarded. There is no mechanism to act on these suggestions. The evolve loop identifies what's broken but never fixes it. A human must manually read the output, understand the scanner code, and implement the fix — which is exactly the work the evolve loop was designed to automate.

The gap is at `adaptive_loop_executor.py` line 635: after `generate_evolve_analysis()` completes, execution stops. Steps 1-3 of the self-improvement pipeline work (run → inspect → analyze). Step 4 (remediate) is missing entirely.

### Evidence

In a single session, a human fixed 6 scanners that the evolve loop had been reporting as "report-only" for weeks:
- auto-seed-data: 115 false positives → 1 real issue
- auto-markers: 19 → 0-3 actionable (reclassified stale logs)
- auto-loop-advisor: 12 → 0 actionable (suggestions → kind="manual")
- auto-command-evolution: 7 → 0 (deferred → kind="maintenance" at d0)
- auto-repo-sync: 4 → 0 (untracked-only → kind="maintenance")
- auto-test-links: 1 → 0 (created missing page stubs)

Each fix was a 5-20 line change to the scanner's `scan()` function. The evolve loop had the information to identify all 6 but no capability to implement any.

## Decision

Add auto-remediation to the evolve loop. After `generate_evolve_analysis()` identifies report-only scanners, the engine should:

1. **Persist suggestions** — Write evolve findings to `~/Library/Application Support/Augur/state/adaptive/evolve_queue.json` with scanner path, issue count, and suggested fix type
2. **Classify fix difficulty** — Map each suggestion to a fix category:
   - `reclassify` — change `kind` field on issues (trivial, safe to auto-apply)
   - `filter` — fix scanner logic to stop false positives (medium, needs code understanding)
   - `upgrade-fix` — make `fix()` actually resolve issues (hard, needs LLM agent)
3. **Auto-apply trivial fixes** — For `reclassify` type, the engine can directly modify the scanner's issue `kind` fields. The scanner source path is known via `registry[category].module.__file__`.
4. **Queue complex fixes** — For `filter` and `upgrade-fix`, write to the queue for the next interactive session. Surface in `/ops-loops review` and the "What next?" prompt.
5. **Track outcomes** — After applying a fix, re-run the scanner and compare issue counts. If the count didn't improve, revert.

### Trust gates

- At d0-d1: Only persist suggestions, no auto-fixes
- At d2-d3: Auto-apply `reclassify` fixes only
- At d4: Dispatch LLM agent for `filter` and `upgrade-fix` types (with verify + revert safety net)

## Consequences

### Positive

- The evolve loop actually evolves — issue count decreases over time without human intervention
- Report-only scanners get automatically upgraded or their issues get properly classified
- The "What next?" prompt surfaces queued improvements so humans can prioritize
- Trust gates ensure the engine earns the right to make bigger changes

### Negative

- Auto-modifying scanner source code carries risk — the verify + revert safety net is critical
- LLM-dispatched fixes at d4 are expensive and may produce incorrect code
- More moving parts in the engine to maintain

### Neutral

- Existing scanners continue to work unchanged — this only adds capability after the analysis phase
- The queue file provides audit trail of what was suggested and when

## Alternatives Considered

### Alternative 1: Fingerprint-based deduplication only

Suppress repeated findings after N cycles without fixing the scanner. Rejected because it hides problems rather than fixing them. The user explicitly requested approach A (fix the scanners) over approach B (suppress the noise).

### Alternative 2: Manual review only

Persist suggestions for human review via `/ops-loops review`. Simpler but defeats the purpose — the engine should handle trivial reclassifications autonomously. Adopted as a complement (for complex fixes) but not as the sole mechanism.

## References

- ADR-102: Adaptive command evolution
- ADR-256: Heal pipeline for loop health
- Session evidence: 2026-03-20 — 6 scanners fixed manually, each was a trivial change the engine could have made
- Code: `adaptive_loop_executor.py:628-636`, `run_inspection.py:220-437`

## Implementation Prompt

**Team name**: `adr-458-evolve-remediation`

### Phase 1: Persistence Layer
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | Create `evolve_queue.py` — write/read/clear queue with fix classification | `.claude/skills/daemon/scripts/adaptive/evolve_queue.py` |
| 1.2 | backend | low | Add queue write call after `generate_evolve_analysis()` | `.claude/skills/daemon/scripts/adaptive_loop_executor.py` |

### Phase 2: Auto-Reclassify
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | high | Implement `apply_reclassify()` — read scanner source, modify issue `kind` fields, verify, commit or revert | `.claude/skills/daemon/scripts/adaptive/evolve_remediate.py` |
| 2.2 | backend | medium | Wire into executor at d2+ with trust gate | `.claude/skills/daemon/scripts/adaptive_loop_executor.py` |

### Phase 3: Queue Surface
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | backend | low | Add `pending` sub-command to show queued evolve improvements | `.claude/skills/dev-loops/SKILL.md` |
| 3.2 | backend | low | Surface queued items in "What next?" prompt generation | `.claude/skills/daemon/scripts/adaptive/reporting.py` |

### Completion Criteria
- [ ] Evolve findings persisted to queue file after each `--evolve` run
- [ ] `reclassify` fixes auto-applied at d2+ with verify + revert
- [ ] Complex fixes surfaced in `/ops-loops review` and "What next?"
- [ ] Re-run after auto-fix shows reduced issue count
