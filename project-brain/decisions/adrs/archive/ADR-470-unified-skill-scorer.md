---
status: Superseded
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: adaptive
tags:
  - skill-quality
  - scoring
  - mcp-tool
superseded_by: ADR-492
---

# ADR-470: Unified Skill Scorer

> **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates). ADR-492 replaces the flat single-weight rubric and 4-level tier system defined here with per-type rubrics and a two-phase S/A/B+/B/C/D/F tier gate backed by behavioral evidence.

## Context

Three divergent skill ranking systems exist in the codebase, each with different criteria and outputs. This makes it impossible to get a consistent quality signal across all 134 skills. The browse page uses a letter grade, the demo page has custom quality gates, and the adaptive loops have no scoring at all.

## Decision

Replace all three systems with a single computed MCP tool (`skill-score`) that scores every skill across 4 dimensions with configurable weights:

- **Instruction** (30%): SKILL.md quality -- description length, body sections, examples
- **Product** (40%): file presence -- scripts, data, seed files, MCP tools
- **UI** (15%): dashboard pages -- page state (mock/dev/mature), contributions declared
- **Wiring** (15%): API route integrity -- toolName matches, no fs bypasses, correct transforms

Scores map to tiers (A >= 75, B >= 55, C >= 35, D >= 15, F < 15). Weights are user-configurable via vault config at `~/Vault/Augur/config/skill-score-weights.yaml`. Results flow to the browse page as `qualityTier`/`qualityScore` badges and to a dedicated deep-dive page with score breakdown and weight sliders.

Caching (60s TTL) prevents redundant filesystem walks on repeated calls.

## Consequences

### Positive
- Single source of truth for skill quality across dashboard, loops, and CLI
- User-configurable weights allow personalized quality priorities
- MCP tool makes scores accessible to any consumer (dashboard, loops, agents)

### Negative
- Initial scoring may surface uncomfortable truth about skill quality distribution
- Filesystem walk across 134 skills adds latency on cold cache

### Neutral
- Replaces the `grade` field in browse with `qualityTier`/`qualityScore`
- Default thresholds are conservative; can be tuned over time

## Alternatives Considered

### Alternative 1: Keep separate scoring systems
Rejected because divergent criteria produce conflicting quality signals and make automated improvement loops unreliable.

## References
- Plan: `docs/superpowers/plans/2026-03-18-unified-skill-scorer.md`
- Spec: `docs/superpowers/specs/2026-03-18-unified-skill-scorer-design.md`
