---
status: Implemented
date: 2026-03-16
deciders:
  - Gur Sannikov
related:
  - ADR-421
hub: productivity
tags:
  - apple
  - notes
  - sync
  - vault
superseded_by: null
---

# ADR-424: Apple Notes Bidirectional Sync Adapter

## Context

9 vault skills contain knowledge, documents, and reference material that should be accessible in Apple Notes for reading on iPhone/iPad. The sync framework (engine, models, differ) exists from the Reminders implementation (ADR-421). This adds the Notes adapter using `macnotesapp` CLI.

## Decision

Implement `NotesSyncAdapter` extending the existing sync framework:

### Adapter Design

- Uses `macnotesapp` CLI (`notes list`, `notes cat`, `notes add`, `notes edit`, `notes delete`, `notes mkdir`)
- **Individual file mode** — each vault `.md` file maps 1:1 to one Apple Note (unlike Reminders' section-file mode with multiple checklist items)
- Engine gets `sync_notes()` method alongside existing `sync()`, detected via `_sync.yaml` `sync_target` field
- Reuses `SyncItem` dataclass — `notes` field holds full markdown body for Notes adapter

### Approved Sync Mapping

12 vault paths → 12 Apple Notes folders, totaling 652 files. Per-folder enable via `apple-notes-sync-enable(vault_path=...)` to prevent bulk push.

### Integration

- New `NotesSyncAdapter` in `scripts/sync/adapter_notes.py`
- New MCP tools: `apple-notes-sync-enable`, `apple-notes-sync-now`, `apple-notes-sync-status`
- Replaces existing one-way `note_sync.py` (AppleScript push) with bidirectional sync via `macnotesapp`
- New `auto-notes-sync` auto-command alongside `auto-reminders-sync`

## Consequences

### Positive

- 652 vault files accessible on iPhone/iPad via Apple Notes
- Bidirectional — edits in Apple Notes flow back to vault
- Leverages existing sync framework — minimal new code

### Negative

- Requires `macnotesapp` CLI installation (`brew install macnotesapp`)
- No graceful degradation — sync disabled without `macnotesapp` (clear message shown)

### Neutral

- Existing `apple_notes.py` AppleScript layer remains for non-sync one-way tools

## References

- Design doc: `docs/superpowers/specs/2026-03-16-apple-notes-sync-design.md`
- ADR-421: Apple Reminders Bidirectional Sync (sync framework)
