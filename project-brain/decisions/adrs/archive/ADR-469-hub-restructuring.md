---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - hub-taxonomy
  - navigation
  - plugin-architecture
superseded_by: null
---

# ADR-469: Hub Restructuring (15 to 5 Apps)

## Context

The dashboard has 15 UI hubs, many with only 1-2 skills each. This creates a fragmented sidebar and dilutes the user experience. Skills are scattered across hubs like admin, ai, consulting, core, enterprise, finance, health, home, lifestyle, observability, productivity, and professional -- with no clear mental model for the user.

## Decision

Restructure 15 hubs into 5 demo-focused apps: **Brain** (AI second brain), **Career** (hiring and growth), **Life** (personal management), **Studio** (build and ship), **Command** (infrastructure). Each app gets 2-3 consolidated tab pages that compose sections from multiple skills.

Implementation approach:
1. Write a one-time migration script to update `x-augur-hub` and add `x-augur-tab` in all SKILL.md frontmatter files
2. Designate hub owner skills (knowledge=Brain, career=Career, attention=Life, advisor=Studio, daemon=Command)
3. Delete old hub directories, run mount-plugins to rebuild with new structure
4. Write 13 consolidated tab pages that combine related skills into coherent views
5. Update `PLUGIN_BUNDLES` in `paths.py` and `CLAUDE.md`

Hidden client templates (consulting, SMB, terminal) remain accessible by direct URL but are not shown in sidebar.

## Consequences

### Positive
- Clear 5-app mental model replaces 15 fragmented hubs
- Consolidated tabs reduce navigation overhead
- Each app has a coherent purpose users can understand

### Negative
- Breaking change to all skill frontmatter (130+ files)
- Consolidated pages require rewriting 13 tab host pages
- Existing bookmarks and documentation referencing old hub URLs break

### Neutral
- Adaptive hub and its 70+ auto-loops are unchanged
- Hidden hub remains for business templates

## Alternatives Considered

### Alternative 1: Gradual hub merging
Merge hubs one at a time over weeks. Rejected because it creates an inconsistent taxonomy during the transition and doubles the migration effort.

## References
- Plan: `docs/superpowers/plans/2026-03-18-hub-restructuring.md`
- Spec: `docs/superpowers/specs/2026-03-18-hub-restructuring-design.md`
