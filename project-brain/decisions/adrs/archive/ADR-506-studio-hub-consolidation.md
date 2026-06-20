---
id: ADR-506
title: Studio Hub Page Consolidation
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [dashboard, studio, consolidation, navigation]
related: []
---

# ADR-506: Studio Hub Page Consolidation

## Context

The Studio hub had 18 routes, many of which were duplicates, thin stubs, or empty SkillAutoPage scaffolds. The advisor, developer, devops, frontend, and mcp-app-factory pages overlapped significantly.

## Decision

Reduce Studio hub from 18 routes to 5 focused pages:
- **workbench** — Re-export of advisor page with fluff removed, absorbs developer and devops
- **design** — Re-export of frontend page, absorbs renderer
- **factory** — Re-export of mcp-app-factory with inline tabs, absorbs 5 sub-stubs
- **terminal** — Re-export of terminal-automation-template
- **page-builder** — Kept as-is (full-screen canvas editor)

13 routes deleted. All pages made full-width by default. Decorative fluff (cross-hub navigation cards, static descriptions) stripped.

## Consequences

### Positive
- 18 routes reduced to 5 — clean, focused tab bar
- Full-width layout eliminates wasted horizontal space
- Each remaining page has actionable content

### Negative
- Old bookmarks to deleted routes will break

## References

- Plan: `docs/superpowers/plans/2026-03-20-studio-consolidation.md`
