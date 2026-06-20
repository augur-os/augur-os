---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: [ADR-158, ADR-404, ADR-451]
hub: null
tags: [vault, sync, discovery, apple-notes, apple-reminders, frontmatter]
superseded_by: null
---

# ADR-452: Content-Based Vault Discovery for Sync

## Context

Vault sync discovery relied on hardcoded path traversal: `discover_all_notes_dirs()` walked `plugins/*/skills/*/` directory trees, and reminders sync scanned `~/Vault/Augur/augur-life/apple/reminders/`. When hubs renamed, skills moved, or directories reorganized, sync broke silently. Quick notes for `venture-augur` were already orphaned.

Two separate notes sync systems existed (legacy `note_sync.py` checking `sync_to_apple: true`, and new `sync/` engine checking `sync_target`), creating inconsistent field usage across the vault.

## Decision

Replace all path-based sync discovery with content-based discovery. A single scanner (`sync_discover.py`) greps the vault for `sync_target:` in YAML frontmatter using ripgrep (~50ms on 3,534 files). All sync systems receive file lists from the scanner instead of discovering files themselves.

### Key changes

1. **New `sync_discover.py`** — `discover(vault_root)` and `discover_by_target(target)` return typed `SyncItem` lists
2. **`sync_to_apple` field eliminated** — replaced by `sync_target: notes` (one field, one source of truth)
3. **`discover_all_notes_dirs()` deleted** — per rule #14, no backward-compat shims
4. **Three sync systems rewired**: `note_sync.py`, `auto_sync.py` (reminders), `auto_notes_sync.py`
5. **MCP tools and API route updated**: `sync_to_apple: bool` -> `sync_target: str`

### Frontmatter contract

```yaml
# Required — triggers discovery
sync_target: notes          # notes | reminders | google (future)

# Optional — target-specific
sync_folder: "🔄 Augur Sync"  # notes: Apple Notes folder
sync_list: "Shopping"           # reminders: list name
sync_section: "Groceries"       # reminders: section name
sync_id: "unique-id"            # update-in-place identifier
```

### Enables ADR B (future)

This scanner establishes the pattern for dashboard data discovery — same rgrep-based approach, different frontmatter fields. Dashboard API routes will query vault files by frontmatter content instead of hardcoded paths, eliminating the same class of path-coupling bugs.

## Consequences

### Positive

- Files stay syncable regardless of where they move in the vault
- Single discovery mechanism for all sync targets (notes, reminders, future)
- Single frontmatter field (`sync_target`) instead of split (`sync_to_apple` + `sync_target`)
- ~50ms discovery time on 3,534 files — negligible overhead
- Pattern reusable for dashboard data discovery (ADR B)

### Negative

- Requires ripgrep installed (falls back to grep, slower)
- Full vault scan on every discovery call (vs previous targeted dir scan) — but benchmarks show this is still faster than the old approach

### Neutral

- Transport logic unchanged — AppleScript execution, remindctl CLI, conflict resolution all stay the same
- Sync scheduling unchanged (15-minute daemon interval)

## Alternatives Considered

### Alternative 1: Filename convention (sync_*.md)

Files named `sync_*.md` get discovered by `find`. 30ms vs 50ms. Rejected: requires renaming files, redundant when frontmatter already declares intent.

### Alternative 2: Enhance existing note_sync.py --all

Make it the universal scanner. Rejected: mixes discovery with transport, harder to test and reuse.

## References

- Design spec: `docs/superpowers/specs/2026-03-19-vault-discovery-sync-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-19-vault-discovery-sync.md`
- ADR-158: Apple Notes seamless editing integration
- ADR-404: Frontmatter format standard
- ADR-451: Ideas vault cleanup (first consumer of this sync pattern)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "note_create_local MCP tool: sync_to_apple:bool -> sync_target:str"
    - "NoteEntry TypeScript interface: sync_to_apple:boolean -> sync_target:string"
  patterns_deprecated:
    - "sync_to_apple frontmatter field -> use sync_target instead"
    - "discover_all_notes_dirs() -> use sync_discover.discover()"
    - "path-based sync discovery -> content-based rgrep discovery"
  files_affected:
    - ".claude/skills/apple/scripts/sync_discover.py (NEW)"
    - ".claude/skills/apple/scripts/note_sync.py"
    - ".claude/skills/apple/scripts/notes_lib.py"
    - ".claude/skills/apple/scripts/sync/auto_sync.py"
    - ".claude/skills/apple/scripts/sync/auto_notes_sync.py"
    - ".claude/skills/apple/scripts/mcp/tools_notes.py"
    - ".claude/skills/apple/augur/api/notes/route.ts"
    - "tests/skills/apple/test_sync_discover.py (NEW)"
```
