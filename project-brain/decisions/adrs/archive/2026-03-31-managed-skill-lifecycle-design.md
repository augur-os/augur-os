# Managed Skill Lifecycle — Design Spec

**Date**: 2026-03-31
**Status**: Draft
**Scope**: Skill management across Augur project (`skills/`) and AI client folders (Claude Code, Codex)

## Problem

Today, all 195 skills live in `skills/` as the single source of truth. AI client folders (`.claude/skills/`, `.codex/prompts/`) receive read-only stubs via one-way sync. This creates friction:

- Skills available as platform plugins (e.g., Claude Code third-party skills) are duplicated in `skills/` even when unmodified
- No distinction between "I customized this" and "I'm using this as-is"
- Platform updates don't flow to skills that haven't been modified
- No unified view of all skills across both locations

## Design

### Skill Lifecycle States

A skill exists in one of three states, determined by its location:

| State | Location | Source tag | Who updates it |
|-------|----------|-----------|----------------|
| **Augur** | `skills/` | `source: augur` | User edits freely |
| **Platform Local** | `.claude/skills/` or `.codex/prompts/` (project-level) | `source: claude-local` / `source: codex-local` | Platform auto-updates |
| **Platform Global** | `~/.claude/skills/` or `~/.codex/prompts/` (user-level) | `source: claude-global` / `source: codex-global` | Platform auto-updates |

Augur skills that originated from a platform track their upstream in SKILL.md frontmatter:

```yaml
---
name: ui-ux-pro-max
x-augur-upstream: claude-local
x-augur-upstream-version: 2.1.0
---
```

### Source Tag Convention

The `source` field in frontmatter is the single marker that distinguishes skill provenance:

- `source: augur` — stub generated from `skills/`, managed by Augur sync
- `source: claude-local` — project-level Claude Code skill, no Augur presence
- `source: claude-global` — user-level Claude Code skill, no Augur presence
- `source: codex-local` — project-level Codex skill
- `source: codex-global` — user-level Codex skill

A skill name can only have ONE authoritative location. If the same name exists in `skills/` and a client folder, `skills/` wins — the client stub gets `source: augur`.

### Skill Sources

Skills enter the system from three sources (hybrid model):

1. **Bundled with Augur** — ship with the project, start in `skills/`
2. **External registry** — installed via `/skillstore` or platform plugin store, land in client folders
3. **User-created** — authored directly in either location

All follow the same lifecycle regardless of origin.

### State Transitions

```
Platform-Managed ──(/skill eject)──→ Augur (ejected)
                                        │
Augur (ejected) ──(/skill reset)──→ Removed + notify user to install via platform
```

**Ejection** (`/skill eject <name>`):

1. Skill must exist in a client folder without `source: augur`
2. Copy full content to `skills/<name>/`
3. Add `x-augur-upstream` and `x-augur-upstream-version` to SKILL.md frontmatter
4. Next sync generates client stub with `source: augur`
5. Discovery invalidates — skill now shows as Augur-sourced

For Claude: copy directory. For Codex: scaffold `skills/<name>/SKILL.md` from flat `.md` file.

**Ejecting a global skill**: The global copy (`~/.claude/skills/<name>/`) is not modified — it stays available to other projects. The ejected copy in `skills/` is project-local. The project-level client stub gets `source: augur`, shadowing the global version for this project only.

**Reset** (`/skill reset <name>`):

1. Skill must be in `skills/` with `x-augur-upstream` set (tracks original platform source)
2. Delete `skills/<name>/`
3. Remove generated stub from client folder
4. Notify user: "Skill removed from Augur. Install the platform version via your AI client."
5. Git history is the safety net for recovering customizations

If no `x-augur-upstream`: reset refuses — skill was born in Augur, nothing to reset to.

### Update Notifications

Ejected skills (in `skills/` with `x-augur-upstream`) are never auto-updated. When discovery detects a version mismatch between `x-augur-upstream-version` and the latest catalog/registry version:

- MCP tool response includes `update_available: true`
- Browse page shows "Update available" badge
- User decides whether to manually pull changes

### Migration Strategy

Gradual opt-in. Existing 195 skills remain in `skills/`. Users migrate individual skills to platform-managed via `/skill reset <name>` at their own pace. New skills installed from platforms start as platform-managed by default.

## Data Layer

### Discovery (Single Source of Truth)

Extend `discover_all_skills()` in `src/plugins/skill_discovery.py` to scan all locations:

| Location | Source tag |
|----------|-----------|
| `skills/` | `augur` |
| `.claude/skills/` (project) | `claude-local` |
| `~/.claude/skills/` (user) | `claude-global` |
| `.codex/prompts/` (project) | `codex-local` |
| `~/.codex/prompts/` (user) | `codex-global` |

Each discovered skill gets a `source` field in its SkillRecord. Deduplication: `skills/` wins on name collision.

### RAG Integration

Extend the RAG skill indexer to include the `source` field in frontmatter when indexing skills. This enables RAG queries to filter by source. No separate registry cache — discovery + RAG is the data layer.

### MCP Tool

`list-skills` MCP tool reads from the discovery module with optional `source` filter parameter. Returns all skills with metadata including source, version, update availability.

## Dashboard Integration

### Browse Page

Shows ALL skills from all sources. Filter buttons:

| Filter | Shows |
|--------|-------|
| All | Everything |
| Augur | `source: augur` |
| Platform Local | `source: claude-local`, `source: codex-local` |
| Platform Global | `source: claude-global`, `source: codex-global` |

### Adaptive Skill Page

Every skill gets the same URL pattern: `/{hub}/skills/{name}`

One page component with progressive disclosure. Sections render only when data exists:

| Section | Augur skill | Platform skill |
|---------|-------------|----------------|
| Header (name, description, source badge) | Yes | Yes |
| SKILL.md content (rendered markdown) | Yes | Yes |
| MCP tools documentation | Yes (from tool registry) | No |
| Actions | Yes | No |
| Dashboard blocks (stats, tables) | Yes (from `augur/` pages) | No |
| Related skills | Yes | Yes (from tags) |
| "Eject to customize" CTA | No | Yes (prominent) |
| "Open full page" link | Yes (if has dedicated `augur/` page) | No |

The page grows richer as the user ejects and adds `augur/` content — no URL change needed.

### Hub Tab Navigation

Only Augur skills with dedicated dashboard pages (`augur/dashboard/` content) appear as hub tabs. Platform skills never appear in tabs.

## Commands

| Command | Action |
|---------|--------|
| `/skill eject <name>` | Copy platform skill to `skills/`, generate Augur stub |
| `/skill reset <name>` | Delete from `skills/`, remove stub, notify user to install via platform |
| `/skill refresh` | Force discovery rescan of all locations |
| `/skill status <name>` | Show skill state: source, location, update availability |

## Target Clients

Initial implementation covers Claude Code and Codex:

- **Claude Code**: `.claude/skills/` (local), `~/.claude/skills/` (global) — directory-based
- **Codex**: `.codex/prompts/` (local), `~/.codex/prompts/` (global) — flat file-based

Other clients (Gemini, Cursor, Copilot, OpenCode) can be added later using the same pattern.

## Non-Goals

- Auto-installing platform skills (user runs platform install commands themselves)
- Merge/conflict resolution for ejected skill updates (notify only)
- Migrating all 195 existing skills at once (gradual opt-in)
- Publishing Augur skills to platform registries (separate concern)
