---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-426
  - ADR-057
  - ADR-164
  - ADR-404
  - ADR-270
hub: adaptive
tags:
  - memory
  - multi-client
  - sync
  - architecture
superseded_by: null
---

# ADR-429: Multi-Client Memory System

## Context

The memory system was centralized and single-writer. A canonical `docs/memory/MEMORY.md` (210 lines, flat dump) fanned out to all AI clients as read-only copies. Only Claude Code wrote memories, but the sync pipeline treated it as a downstream consumer — overwriting its curated index with the flat canonical format on every sync run. Archives were 98.4% duplicates (patterns-archive: 5165 lines → 27 unique), daily logs were abandoned, and no runtime integration existed.

With Gemini, Codex, and future agents needing to write memories, the system needed the same treatment skills got with ADR-426: client-native ownership with assembled views.

## Decision

### Client-Owned Entries

Each memory entry is an individual `.md` file with YAML frontmatter (ADR-404 compliant). A `written-by` field declares the owning client (`claude-code`, `gemini`, `codex`, `augur-system`). Only the originating client can update its entries. Other clients read all entries via the assembled view.

### Client-Native Dirs as Master + Vault as Assembled View

Each client writes to its native memory directory. A `memory_assembler.py` scans all client dirs, quality-gates entries (dedup, noise filter), and produces:
- Vault `entries/` — all entries from all clients, prefixed with `{client_id}_`
- Per-client adapted indexes (Claude: linked, Gemini: `@` imports, Codex: flat, Vault: table)

### Cross-Client Memory Learning Loop

Nightly `auto-memory-sync` runs the assembler, which discovers new entries from any client and distributes adapted indexes to all others. A pattern discovered in Gemini appears in Claude Code's index at next session.

### augur-system as a Writer

Hooks and `/dev-learn` write entries as `written-by: augur-system` to vault `system/` dir. The daily logs pipeline (`curate_daily_logs()`) is deleted.

### Memory Tiers

- **Long-term**: individual `.md` files in client dirs and vault `entries/` — curated, persistent
- **Short-term**: runtime state at `$AUGUR_STATE/memory/` — session-scoped, ephemeral

## Migration

- Split `patterns.md` (145 entries), `decisions.md`, `preferences.md` into individual files
- Extracted 27 unique from patterns-archive (98.9% duplicates discarded)
- Extracted 92 valuable from decisions-archive (11K+ duplicates/noise filtered)
- Migrated 257 entries from 30 daily logs to vault `system/`
- Deleted legacy: archives, daily dir, HUMAN_API.md, empty stubs, 89 vault junk JSON files
- Total: 554 entry files created, 220 pass quality gate and are indexed

## Consequences

### Positive

- Any AI client can write memories that automatically reach all other clients
- Quality gate prevents the 114x duplication bug from recurring
- Vault is browsable in Obsidian with full metadata (date, client, type)
- Legacy pipeline (672 lines) reduced to utility functions (170 lines)
- Follows proven ADR-426 pattern — no new infrastructure concepts

### Negative

- Migration is one-time but non-trivial (554 files created)
- Gemini `@` import support is new code (not just a redirect)

### Neutral

- Short-term to long-term promotion deferred to follow-on work
- Codex memory writing requires future MCP tool (read-only for now)

## References

- Design doc: `docs/superpowers/specs/2026-03-17-multi-client-memory-system-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-17-multi-client-memory-system.md`
- ADR-426: Client-Native Skill Mastering (pattern source)
- ADR-057: Memory System Alignment with Claude Native
- ADR-164: Context Optimization and Memory Retention
