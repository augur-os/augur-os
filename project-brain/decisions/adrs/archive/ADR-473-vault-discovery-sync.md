---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: life
tags:
  - vault
  - sync
  - apple-notes
  - apple-reminders
  - discovery
superseded_by: null
---

# ADR-473: Vault Discovery and Unified Sync

## Context

The Apple sync system (notes, reminders) uses path-based discovery to find syncable files. Files must live in specific directories to be discovered, and the `sync_to_apple: true` boolean field in frontmatter acts as a second gate. This means moving vault files to different directories breaks sync, and the dual gating (path + boolean) is redundant and confusing.

## Decision

Replace path-based sync discovery with content-based `rg` (ripgrep) discovery:

1. Create `sync_discover.py` scanner that greps the entire vault for `sync_target:` in YAML frontmatter, returning typed `SyncItem` objects with path, target, title, and optional fields (sync_folder, sync_list, sync_id)
2. Known targets: `notes` and `reminders`
3. Rewire `note_sync.py`, `auto_sync.py`, and `auto_notes_sync.py` to call the scanner instead of path-based directory iteration
4. Delete `discover_all_notes_dirs()` from `notes_lib.py`
5. Replace `sync_to_apple: bool` with `sync_target: string` in MCP tools and API routes
6. Migrate existing vault frontmatter: `sync_to_apple: true` becomes `sync_target: notes`
7. Falls back to `grep` when ripgrep is not available

## Consequences

### Positive
- Files stay syncable regardless of directory moves
- Single discovery mechanism for all sync targets
- Eliminates the confusing `sync_to_apple` boolean

### Negative
- Migration required for existing vault files with `sync_to_apple` frontmatter
- Ripgrep dependency (with grep fallback) for discovery performance

### Neutral
- `SyncItem` dataclass provides a typed contract between discovery and sync engines
- Scanner has CLI mode for manual verification

## Alternatives Considered

### Alternative 1: Index-based discovery with a sync registry file
Maintain a central YAML file listing all syncable files. Rejected because it requires manual maintenance and falls out of sync when files are added or moved.

## References
- Plan: `docs/superpowers/plans/2026-03-19-vault-discovery-sync.md`
- Spec: `docs/superpowers/specs/2026-03-19-vault-discovery-sync-design.md`
