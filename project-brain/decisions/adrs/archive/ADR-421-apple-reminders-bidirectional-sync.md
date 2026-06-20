---
status: Implemented
date: 2026-03-15
deciders:
  - Gur Sannikov
related: []
hub: productivity
tags:
  - apple
  - reminders
  - sync
  - vault
superseded_by: null
---

# ADR-421: Apple Reminders Bidirectional Sync

## Context

Users capture tasks in Apple Reminders (phone, watch, Siri) but this data is invisible to Augur's vault, dashboard, and AI processing. No mechanism exists for bidirectional sync between Apple Reminders and Augur's vault data.

## Decision

Implement a universal sync framework with Apple Reminders as the first adapter:

### Sync Framework

- **SyncAdapter** — Python class per backend (Reminders, Notes, Obsidian)
- **SyncEngine** — orchestrates pull → diff → merge → push → update metadata
- **SyncRegistry** — discovers sync-enabled skills via `augur.yaml` declarations + item-level frontmatter overrides
- **SyncMetadata** — stored in vault file frontmatter (`sync_id`, `last_sync`, `sync_status`) and `_sync.yaml` per-item field snapshots

### Reminders Adapter

- Maps Apple Reminders hierarchy (List → Sections → Reminders) to vault files (directory → section files → checklist items)
- Uses forked `remindctl` CLI with PRs #27 (sections), #38 (sync metadata)
- 15-minute polling interval + on-demand via dashboard/CLI
- Field-level merge with conflict detection on per-field basis

### Conflict Resolution

Field-level 3-way merge using `_sync.yaml` item snapshots as the "last synced" anchor. Same-field conflicts flagged with both versions preserved for user resolution in dashboard.

### New MCP Tools

- `apple-sync-status` — sync state for all sync-enabled skills
- `apple-sync-now` — trigger immediate sync
- `apple-sync-resolve` — resolve a conflict

## Consequences

### Positive

- Reminders captured on any Apple device automatically appear in Augur vault
- Changes in vault push back to Apple Reminders
- Framework extensible to Notes, Obsidian, etc.

### Negative

- Depends on forked `remindctl` for full section support
- iCloud propagation delay means changes aren't instant

### Neutral

- Graceful degradation without fork (content hash fallback, no sections)

## References

- Design doc: `docs/superpowers/specs/2026-03-15-apple-reminders-sync-design.md`
- remindctl: github.com/steipete/remindctl
