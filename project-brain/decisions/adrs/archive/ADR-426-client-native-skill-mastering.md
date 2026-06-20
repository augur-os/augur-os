---
status: Implemented
date: 2026-03-16
deciders:
  - Gur Sannikov
related:
  - ADR-235
  - ADR-275
hub: dev
tags:
  - skills
  - sync
  - client-native
  - architecture
superseded_by: null
---

# ADR-426: Client-Native Skill Mastering

## Context

The current skills sync model is centralized fan-out: all skills live in `plugins/{bundle}/skills/{skill}/` and are synced outward to AI clients (Claude Code, Codex, Gemini, Cursor, etc.) via adapters. This makes skills feel foreign to every client — they're Augur artifacts, not native to any platform.

## Decision

Flip the ownership model: each skill is owned ("mastered") by a specific AI client and lives natively in that client's project directory. Other clients receive adapted copies.

### Master Client Data Model

`x-augur-master` in SKILL.md frontmatter declares the owning client. Valid values: `augur`, `claude-code`, `codex`, `gemini`, `cursor`, `copilot`, `windsurf`, `cline`, etc.

### Client Directory Structure

Master skills live in client-native dirs with full Augur plugin structure:
```
.claude/skills/eisenhower/
├── SKILL.md
├── augur/augur.yaml
├── scripts/mcp/
└── data/seeds/
```

Non-master clients receive adapted copies in their native format.

### Mount-Plugins Changes

Scans all client skill directories alongside `plugins/`. Hub assignment from skill metadata (`x-augur-hub`/`contributes_to`), not directory path. Deduplication by `x-augur-master` — only masters get mounted.

### Sync Engine Direction Flip

Reads from master client's directory, adapts to all other enabled client directories. Adapted copies include `AUGUR-ADAPTED-COPY` marker. Orphan cleanup only deletes adapted copies, never master directories.

### Implementation Phases

1. **Phase 1** — Infrastructure: `x-augur-master` support, client dir scanning, sync direction flip
2. **Phase 2** — New skills installed natively in master client dir
3. **Phase 3** — Gradual migration from `plugins/` to client dirs, per hub batch
4. **Phase 4** — Remove `plugins/` scanning, delete empty `plugins/`

## Consequences

### Positive

- Skills feel native to the platform that created them
- Any client can create skills that automatically sync to others
- Per-skill rollback by moving back to `plugins/`

### Negative

- Migration is multi-phase, non-trivial
- Gitignore changes needed (client skill dirs become source-controlled)

### Neutral

- `x-augur-master: augur` provides full backward compatibility during migration

## References

- Design doc: `docs/superpowers/specs/2026-03-16-client-native-skill-mastering-design.md`
- ADR-235: Plugin Architecture Integrity
- ADR-275: Skill Import-Export Consolidation
