---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [adaptive, skill-quality, automation, scoring]
---

# ADR-443: Auto Skill Quality Loop

## Context

130 skills scored -- 80 at tier D, 32 at C, 17 at B, 1 at F, 0 at A. Most skills have thin SKILL.md instructions, missing product scaffolding, empty data directories, and broken or missing wiring. No automated process exists to systematically improve skill quality toward tier A across all dimensions while considering user experience.

## Decision

Introduce a new adaptive loop `skill-quality` that runs nightly, scores skills via the unified scorer, picks the lowest-scoring skills, and improves them across all 4 dimensions (instruction, product, UI, wiring). Every fix is user-journey-aware: the loop reasons about what problem each skill solves, how the user consumes the data, and whether the dashboard page actually serves that purpose. Git revert on build failure or score regression.

Key design points:
- **Scan phase** imports `score_all_skills()` from the unified scorer, targets the N worst skills per cycle (default 5)
- **Fix phase** operates per-dimension at increasing difficulty levels: d1 instruction, d2 product, d3 UI, d4 wiring
- **Safety** via git commit before fix, build verify after, revert on regression or build failure
- **Seed generation** reads page components and SKILL.md to infer data shape and generate realistic seed files
- **Evolution gaps** reported when all skills reach tier A, recommending threshold increase

## Consequences

### Positive

- Systematic, automated path from tier D/C to tier A across all skills
- User-journey reasoning ensures fixes improve actual user experience, not just scores
- Git revert safety net prevents regressions from propagating

### Negative

- Nightly budget (15 actions/cycle) limits throughput to ~5 skills per night
- Generated seed data and descriptions may not perfectly match domain nuance

### Neutral

- Complements existing `skill-standards` (structural hygiene) and `auto-seed-data` (mechanical copy) loops
- Requires the unified scorer (ADR-447) as a prerequisite

## Alternatives Considered

### Alternative 1: Manual Skill Improvement

Manually audit and fix each skill. Rejected because 130 skills at low tiers makes manual improvement impractical and inconsistent.

### Alternative 2: Score-Only Loop (No Auto-Fix)

Report scores nightly but require manual fixes. Rejected because the gap between reporting and action means skills would remain at low tiers indefinitely.

## References

- Design spec
