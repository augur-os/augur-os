---
id: ADR-508
title: Skill Quality and Rank System
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [skill-quality, scoring, tiers, evals, feedback]
related: [ADR-492]
---

# ADR-508: Skill Quality and Rank System

## Context

The skill quality system scored all skills with the same rubric regardless of type (autoloop vs command vs integration). This produced misleading scores — autoloops scored low for missing dashboard pages they don't need. ADR-492 specified type-aware scoring; this plan implemented it along with behavioral tier gates, seed eval generation, user feedback hooks, and import metadata.

## Decision

Extend the quality system with:
- **Type-aware rubrics** — Per-type scoring weights in `skill_scorer.py` (autoloop, command, integration, etc.)
- **Two-phase tier computation** — Structural score (static analysis) + behavioral gate (eval results)
- **Seed eval generation** — At d2+, auto-generate evals per skill type in `evals/` directory
- **rank.json sidecar** — Per-skill quality rank written alongside SKILL.md
- **Feedback hook** — `feedback_hook.py` collects post-execution user signals via PostToolUse CLI
- **Import metadata** — `stamp_import_metadata()` in `frontmatter_utils.py` marks imported skills with source, date, version

## Consequences

### Positive
- Autoloops no longer penalized for missing pages they don't need
- Behavioral gate prevents high structural score from masking runtime failures
- User feedback feeds back into scoring and eval quality

### Negative
- Type rubric maintenance — new skill types need rubric definitions

## References

- Plan: `docs/superpowers/plans/2026-03-23-skill-quality-rank-system.md`
- Spec: `docs/superpowers/specs/2026-03-23-skill-quality-rank-system-design.md`
- Parent ADR: ADR-492 in `Au-vault/dev/adrs/`
