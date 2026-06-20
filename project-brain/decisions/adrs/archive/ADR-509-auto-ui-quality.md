---
id: ADR-509
title: Auto UI Quality Nightly Autoloop
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [ui, ux, accessibility, autoloop, design-system]
related: []
---

# ADR-509: Auto UI Quality Nightly Autoloop

## Context

Dashboard pages have no automated quality checks for UI/UX issues — accessibility violations, design system inconsistencies, interaction bugs, and responsiveness problems are only caught by manual review. With ~140 pages, manual QA is unsustainable.

## Decision

Build `auto-ui-quality` skill as a nightly autoloop with progressive auto-fix:
- **d0-d1**: Static TSX analysis — check definitions in YAML registry, scored across 4 weighted dimensions (accessibility, interaction, design system, responsiveness)
- **d2**: Safe auto-fixes — code patches for known patterns (missing aria labels, incorrect CSS variables)
- **d3-d4**: LLM-assisted — Playwright screenshots + ui-ux-pro-max design intelligence for page redesigns

Page score registry persisted to runtime dir. Git safety net reverts on build failure or score regression. Maximum 3 page rewrites per d3-d4 cycle.

## Consequences

### Positive
- All 140+ pages scored nightly across 4 quality dimensions
- Safe fixes applied automatically at d2, reducing manual QA burden
- Git safety net prevents quality regressions from auto-fixes

### Negative
- d3-d4 requires Playwright + running dashboard server (infrastructure dependency)
- LLM-assisted fixes consume tokens and may produce false improvements

## References

- Plan: `docs/superpowers/plans/2026-03-24-auto-ui-quality.md`
- Spec: `docs/superpowers/specs/2026-03-24-auto-ui-quality-design.md`
