---
status: Superseded
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [scoring, skills, mcp, dashboard, browse]
superseded_by: ADR-492
---

# ADR-447: Unified Skill Scorer

> **Superseded by ADR-492** (Type-Aware Skill Scoring with Behavioral Tier Gates). ADR-492 replaces the flat single-weight rubric and 4-level tier system defined here with per-type rubrics and a two-phase S/A/B+/B/C/D/F tier gate backed by behavioral evidence.

## Context

Three independent skill ranking systems exist with no alignment: (1) browse page grade from page states, (2) venture demo page with 6-dimension scores hardcoded for 44 of 134 skills (already drifting), (3) ad-hoc SKILL.md file analysis. Each measures something different, none covers all skills, and the venture page data is static and unmaintained.

## Decision

Replace all three with a single computed scorer that runs as an MCP tool (`skill-score`), covers all 134 skills, and surfaces results in both the browse page (tier badges) and a dedicated deep-dive page (breakdown + weight configuration).

Key design points:
- **4 dimensions**: instruction quality (0.30), product completeness (0.40), UI maturity (0.15), wiring integrity (0.15) -- weights configurable via vault YAML
- **Tier thresholds**: A >= 75, B >= 55, C >= 35, D >= 15, F < 15
- **MCP tool** `skill-score` with in-memory 60s TTL cache, optional `skill_name` and `hub` params
- **API route** `/api/skill-score/` with GET (scores) and POST (update weights)
- **Browse integration**: adds `qualityScore` and `qualityTier` to browse metadata, replaces old `grade` field
- **Deep-dive page**: replaces venture demo's SkillGateVisualizer with tier distribution chart, weight sliders, sortable/filterable skill table with expandable dimension breakdowns
- **All signals are file-grep based** -- no AST parsing, no runtime checks

## Consequences

### Positive

- Single source of truth for skill quality across browse, demo page, and adaptive loops
- Computed scores are always current (no stale hardcoded data)
- Weight configuration lets users tune scoring priorities

### Negative

- Walking 134 SKILL.md files + directory checks is expensive (mitigated by 60s cache)
- Replacing the venture demo's hardcoded data removes curated presentation in favor of computed scores

### Neutral

- `pages` and `customPages` browse metadata preserved (useful independently)
- Existing `tier` field on BrowseCard untouched (used for agent tier badges, not quality)

## Alternatives Considered

### Alternative 1: Fix Existing Systems Independently

Improve each of the 3 ranking systems separately. Rejected because maintaining 3 systems with different coverage and semantics is inherently inconsistent.

### Alternative 2: Single Composite Score (No Dimensions)

One number per skill with no breakdown. Rejected because dimension visibility is essential for targeted improvement (adaptive loops need to know which dimension to fix).

## References

- Design spec
