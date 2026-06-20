---
id: ADR-511
title: Page Cleanup and Grouped Navigation Design
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [dashboard, navigation, tabs, cleanup]
related: [ADR-507, ADR-128, ADR-218, ADR-177, ADR-136]
---

# ADR-511: Page Cleanup and Grouped Navigation Design

## Context

Design spec for the grouped navigation feature (implemented as ADR-507). Analyzed 140 page.tsx files and 188 tab registry entries across 6 hubs, identifying that skill sub-pages were incorrectly flattened into top-level tabs.

## Decision

Spec defined:
- **Grouping logic**: Tabs with the same `skillId` and 2+ entries merge into dropdown groups
- **Expected results per hub**: Command 9->4 tabs, Life 9->5 tabs, Career 9->5 tabs
- **Phase 1**: Grouped navigation in tab bar with `GroupedTab` type
- **Phase 2**: Hidden dev-mode hub for templates
- No page deletions — problem was purely navigational

Design builds on ADR-136 (nested skills with `children` arrays) as the reusable pattern for tab grouping.

## Consequences

### Positive
- Clear analysis of per-hub tab counts before and after grouping
- Design reuses existing ADR-136 pattern rather than inventing new approach

### Negative
- None — this is a design document, not an implementation decision

## References

- Spec: `docs/superpowers/specs/2026-03-22-page-cleanup-grouped-nav-design.md`
- Implementation: ADR-507
