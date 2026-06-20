---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: adaptive
tags:
  - adaptive-loop
  - skill-quality
  - nightly
superseded_by: null
---

# ADR-467: Auto Skill Quality Loop

## Context

Augur has 134+ skills but many score below tier A across the four quality dimensions (instruction, product, UI, wiring). Manual improvement is infeasible at scale. A systematic approach is needed to continuously raise skill quality with safety guarantees against regressions.

## Decision

Create an adaptive nightly loop (`skill-quality`) registered in `adaptive_loops.yaml`, implemented as an OpsCommand module (`scan` + `fix`) in `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`. The loop:

1. Scans all skills via the unified scorer, reporting tier distribution and worst performers
2. Applies dimension-specific fixes gated by difficulty level: d0=report only, d1=instruction rewrites, d2=+product scaffolding, d3=+UI promotion, d4=+wiring fixes
3. Commits each fix individually, verifies build passes, re-scores, and reverts on failure or regression
4. Limits to 5 skills per cycle to bound runtime and risk
5. Uses user-journey awareness -- reads the skill's purpose and dashboard consumption pattern before fixing

## Consequences

### Positive
- Continuous automated quality improvement across all skills
- Safe iteration with git revert on build failure or score regression
- Difficulty-gated progression prevents premature changes

### Negative
- Nightly loop adds compute cost and git history noise
- Automated fixes may produce technically valid but shallow improvements

### Neutral
- Depends on the unified skill scorer (ADR-470) for scoring data

## Alternatives Considered

### Alternative 1: Manual skill improvement sprints
Rejected because manual intervention does not scale to 134+ skills and cannot maintain continuous quality pressure.

## References
- Plan: `docs/superpowers/plans/2026-03-18-auto-skill-quality-loop.md`
- Spec: `docs/superpowers/specs/2026-03-18-auto-skill-quality-loop-design.md`
