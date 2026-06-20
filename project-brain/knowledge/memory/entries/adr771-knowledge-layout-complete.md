---
title: adr771-knowledge-layout-complete
name: adr771-knowledge-layout-complete
description: Personal vault (Au-vault) migrated to the ADR-771 knowledge/ layout on
  2026-06-10 — notes/wiki/memory/sources live under knowledge/, legacy flat names
  are retired and flagged by hygiene
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: adr771-knowledge-layout-complete.md
source_hash: c1a0fea22b93eecd
---


ADR-771 completion shipped 2026-06-10 (repo `83b379dd1`, vault `1efc437`): Au-vault content moved via git mv into `knowledge/{notes,wiki,memory,sources}` (468 renames); vault root went 33 → 27 entries, single taxonomy. Spec: `docs/superpowers/specs/2026-06-10-complete-adr771-personal-vault-knowledge-layout.md`.

**Why:** the brain carried two layouts (content in flat dirs, empty skeleton beside) — the "total mess" Gur flagged.

**How to apply:**
- Resolve vault content via helpers (`get_vault_notes_dir`, `get_wiki_dir`, `get_memory_dir`) — they now return `knowledge/*`. Never construct `vault/"notes"` etc.; the legacy flat names are retired everywhere (vault-hygiene flags them).
- `brain_write_routing` hands the BRAIN ROOT to card writers for all tiers; writers (prompt/thought/source/url cards) append `knowledge/notes` themselves.
- Long-running processes (daemon, MCP servers, other clients) hold pre-migration code until restarted — they recreate legacy dirs (`dev/` kept respawning from a deleted-worktree MCP zombie + stale daemon). After path-layer changes: restart the daemon (`launchctl unload/load com.augur.daemon`), expect a one-time "System Move Detected" healer dialog, and let hygiene loops flag stragglers. See [[gitignore-blind-spot-pollution]] and [[feedback-never-ignore-bugs]].
- `reindex_all` indexes the vault category ONLY when `vault_dir=get_vault_dir()` is passed (the CLI does; ad-hoc calls silently report `vault: 0`).
