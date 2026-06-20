---
id: ADR-507
title: Grouped Tab Navigation and Hidden Dev-Mode Hub
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [dashboard, navigation, tabs, grouping, dev-mode]
related: [ADR-128, ADR-218, ADR-177, ADR-136]
---

# ADR-507: Grouped Tab Navigation and Hidden Dev-Mode Hub

## Context

The dashboard had ~140 page.tsx files and 188 tab registry entries. Skill sub-pages were flattened into the hub tab bar as top-level tabs, making navigation cluttered. For example, Command hub showed Daemon, Health, Jobs, Loops, Notifications, Services as 6 separate top-level tabs when they should be grouped under Daemon.

## Decision

Two changes:
1. **Grouped navigation** — Tab generator adds a grouping pass that merges tabs sharing a `skillId` into a `GroupedTab` with `children`. Skills with 1 tab render flat (current behavior). Skills with 2+ tabs render as dropdown groups. `HubTabBar` renders groups as dropdown buttons.
2. **Hidden dev-mode hub** — Templates hub entry added to sidebar with `category: "dev"`, only visible when dev mode is enabled.

New files: `tab-grouping.ts` (groupBySkillId, isGroupedTab), `GroupDropdown.tsx` component. Type additions: `GroupedTab`, `TabEntry` union type.

## Consequences

### Positive
- Command hub: 9 tabs -> 4 primary (Daemon group collapses 6 into 1)
- Life hub: Voice Memos, Scenes, Lighting cluster under their parent skills
- Tab bar is scannable at a glance

### Negative
- Dropdown requires an extra click to reach sub-pages

## References

- Plan: `docs/superpowers/plans/2026-03-22-grouped-nav-hidden-devmode.md`
- Spec: `docs/superpowers/specs/2026-03-22-page-cleanup-grouped-nav-design.md`
