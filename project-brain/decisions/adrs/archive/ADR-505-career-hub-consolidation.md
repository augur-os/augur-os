---
id: ADR-505
title: Career Hub Page Consolidation
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [dashboard, career, consolidation, navigation]
related: []
---

# ADR-505: Career Hub Page Consolidation

## Context

The career hub had 28 pages across scattered routes with nav-only pages, duplicates, and AI fluff cards. Users encountered a cluttered tab bar with many pages that added no real functionality (static text, generic "AI can help" cards, navigation-only sections).

## Decision

Consolidate 28 career hub pages into 6 focused tabs:
- **pipeline** — Full-page job pipeline + status card (from career/career/)
- **resume** — Resume management without fluff cards (from career/career/resume/)
- **interview** — Merged interview projects + STAR stories + knowledge topics
- **learning** — Merged courses + knowledge + guard + habits + hardening
- **gtm** — Merged marketing + content + social + community
- **venture-augur** — Cleaned up, compact links bar replacing VentureNavSection

Components relocated alongside their new pages. Fluff removed: StarFrameworkGuide, ResumeTipsCard, AIInterviewPrepCard, ResumeAIToolsCard, nav-only sections, Cross-Hub Links footers.

## Consequences

### Positive
- 28 pages reduced to 6 — each tab has real interactive content
- Users find career tools faster with fewer navigation layers
- Component colocation simplifies import paths

### Negative
- Users with bookmarks to old routes will get 404s (no redirect shims per Rule 14)

## References

- Plan: `docs/superpowers/plans/2026-03-20-career-hub-consolidation.md`
