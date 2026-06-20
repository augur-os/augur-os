---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- commands
- skills
- migration
superseded_by: null
---

# ADR-252: Commands-to-Skills Migration

**Related ADRs:** ADR-098 (Unify Commands and Skills), ADR-163 (Config Decentralization), ADR-178 (Decentralized Slash Command Discovery), ADR-186 (Sync Agents Refactor), ADR-219 (IDE Integration Lifecycle), ADR-251 (Command Registry Parity)

---

## Context

Augur has 73 slash commands defined in plugin `augur.yaml` files under `contributions.commands`. These commands require `sync_agents.py` to discover, transform, and export them as `.claude/skills/*/SKILL.md` files for Claude Code and equivalent formats for 10 other IDE adapters. This creates several problems:

1. **Sync overhead** — Every command change requires running sync_agents.py to regenerate ~73 SKILL.md exports plus CLAUDE.md, CODEX.md, and 9 other IDE rule files.
2. **Source-of-truth confusion** — Commands are defined in augur.yaml, content lives in `commands/*.md`, but the consumable artifact is a generated file in `.claude/skills/`. Three locations for one concept.
3. **Concept fragmentation** — "Commands", "tools", and "skills" are separate concepts with separate discovery paths when they should be one thing. The adaptive loop engine reads `contributions.commands` from augur.yaml. MCP reads `scripts/` from skill directories. Claude Code reads `.claude/skills/`. Three discovery mechanisms for overlapping purposes.
4. **Code bloat** — sync_agents.py contains ~1800 lines of command discovery, export, and validation logic (out of ~2800 total).
5. **Overlap** — 13 commands are duplicates or near-duplicates that accumulated because the command registry lacks consolidation pressure.

Meanwhile, MCP already auto-discovers skills via `skill_registry.py` (finds `SKILL.md` files) and `dynamic_registry.py` (registers `scripts/` as tools). The infrastructure for self-describing skills already exists.

## Decision

### 1. Every command becomes a standalone skill

Each slash command becomes its own skill directory with `SKILL.md` + `augur.yaml` under its natural plugin bundle. The `SKILL.md` frontmatter carries all metadata via `x-augur-*` extension fields:

```yaml
---
name: auto-lint
description: Run ESLint auto-fix and AI-assisted lint error resolution
x-augur-visibility: auto
x-augur-loop:
  name: code-quality
  tier: 1
  trigger: nightly
x-augur-alias: lint
x-augur-group: code-quality
---
```

- `x-augur-visibility` — present = command-skill, absent = regular skill. Values: `core`, `dev`, `ops`, `test`, `app`, `auto`.
- `x-augur-loop` — present = adaptive loop command with scan-fix protocol.
- No `contributions.commands` in augur.yaml needed — the skill IS the command.

### 2. Single discovery function replaces all command scanning

A new `src/plugins/command_discovery.py` provides `discover_commands()` that reads `x-augur-visibility` from SKILL.md frontmatter via `skill_registry.py`. All consumers use this one function:

- Claude Code — reads SKILL.md directly from plugin paths
- MCP tools — `dynamic_registry.py` registers `scripts/` (unchanged)
- Adaptive loop engine — reads `x-augur-loop` from frontmatter
- `/commands` help — calls `discover_commands()` to render grouped listing
- Dashboard help page — API route calls same function
- sync_agents.py — generates command reference table for non-Claude-Code IDEs

### 3. New `autoloop` plugin consolidates all auto-commands

All 32 auto-commands (after merges) move to `plugins/admin/skills/` as sibling skills alongside a new `autoloop` parent skill that documents the adaptive loop engine. This makes the loop system self-contained and independently exportable.

### 4. Command consolidation eliminates 13 duplicates

| Keep | Absorb | Reasoning |
|------|--------|-----------|
| `kill-augur` | `ops-kill` | Identical |
| `rollback-recovery` | `ops-rollback` | Identical |
| `learn` | `ops-learn` | Identical |
| `debug-protocol` | `dev-debug` | Identical 6-phase protocol |
| `auto-markers` | `auto-tidy` | Both scan/cleanup TODO markers |
| `auto-test-coverage` | `auto-coverage-check` | Both flag low-coverage modules |
| `auto-doc-freshness` | `auto-docs` | Both maintain doc freshness |
| `auto-code-health` | `fix-build` | Both fix build errors |
| `auto-perf-profile` | `performance-profiling` | Auto subsumes manual guide |
| `nightly` | `test-nightly` | Same CI cycle |
| `tech-debt-triage` | `auto-debt`, `auto-debt-scan` | All three about tech debt |

Result: 73 commands become 53 standalone skills.

### 5. sync_agents.py gutted to rules-only

Remove all command discovery/export logic (~1800 lines). Keep:
- Global agent rules sync (agent-rules.md to CLAUDE.md, CODEX.md, etc.)
- IDE adapter generation (11 adapters)
- Topic doc syncing
- `.agent/ide-manifest.json` generation
- MCP config generation

CLAUDE.md template replaces the command listing with "Run /commands for available commands."

### 6. Claude Code reads skills directly from plugins/

Claude Code plugin registration points at `plugins/*/skills/` directories. Skills are read natively — no export to `.claude/skills/` needed. Other IDEs continue using sync_agents.py for their format-specific files.

### 7. Commands help page with three groups

A new `/commands` skill and dashboard page displays:
1. **Slash Commands** — grouped by visibility (CORE, DEV, OPS, TEST, APP)
2. **Auto Loop Commands** — grouped by loop name (code-quality, hardening, system-health, knowledge, maintenance, sync)
3. **Skills** — browsable list of all non-command skills

## Consequences

### Positive

- **Zero sync for commands** — Edit a SKILL.md, it's immediately available. No sync step.
- **One concept** — Skills are the universal unit. No more commands vs tools vs skills.
- **~1800 lines removed** from sync_agents.py. Simpler codebase.
- **13 duplicate commands eliminated** — cleaner command surface.
- **Auto-loop system self-contained** — `autoloop` plugin is independently exportable.
- **Open-source aligned** — Skill directory structure matches Claude Code's native plugin format.
- **Better discoverability** — Help page with grouped display replaces flat command table.

### Negative

- **Large migration** — 53 new skill directories to create, 73 old command entries to remove.
- **MCP tool name changes** — `dynamic_registry.py` uses `{skill_id}_{script}` for tool names. Moving scripts changes tool names. Dashboard actions referencing old names need updating.
- **Adaptive loop engine change** — Must read frontmatter instead of augur.yaml `contributions.commands`. Dual-read during migration.
- **Claude Code plugin registration** — Depends on Claude Code's plugin system supporting multi-directory registration. Fallback: symlinks.

### Neutral

- Other IDE adapters unchanged — sync_agents.py still generates their files, just without the command export overhead.
- Existing `skill_registry.py` and `dynamic_registry.py` need minimal changes (4 new fields on SkillMetadata).

## Implementation Order

### Phase 0: Preparation (prerequisite for all phases)

1. Add `x-augur-*` fields to `SkillMetadata` in `skill_registry.py`
2. Create `src/plugins/command_discovery.py` with `discover_commands()`
3. Update adaptive loop discovery to dual-read (augur.yaml + SKILL.md frontmatter)
4. Create `plugins/admin/skills/autoloop/` parent skill
5. Write migration script `scripts/migrate_commands_to_skills.py`

### Phase 1: Auto commands to autoloop (32 skills) — after Phase 0

1. Run migration script Phase 1 (create 32 skill directories under `plugins/admin/skills/`)
2. Execute 7 command merges (tidy→markers, coverage-check→test-coverage, docs→doc-freshness, debt→tech-debt-triage, fix-build→code-health, performance-profiling→perf-profile, auto-docs→doc-freshness)
3. Move callable scripts from parent skills
4. Remove `contributions.commands` entries from devops, daemon, ai_bridge augur.yaml
5. Delete old command .md files

### Phase 2: OPS + DEV + TEST (11 skills) — after Phase 0, parallel with Phase 1

1. Run migration script Phase 2
2. Execute merges (ops-kill→kill-augur, ops-rollback→rollback-recovery, dev-debug→debug-protocol, test-nightly→nightly)
3. Clean up parent augur.yaml files

### Phase 3: CORE + APP (10 skills) — after Phase 0, parallel with Phases 1-2

1. Run migration script Phase 3
2. Execute merges (ops-learn→learn)
3. Clean up parent augur.yaml files

### Phase 4: sync_agents.py cleanup — after Phases 1-3

1. Remove command discovery/export functions from discovery.py (~150 lines)
2. Remove `{{SKILLS_TABLE}}` from templates.py
3. Remove `--skills`/`--workflows` CLI flags from __init__.py
4. Remove `CLAUDE_SKILLS_EXPORT_DIR` and `EXPORT_HEADER` from constants.py
5. Remove `export_augur_skills()` call from engine.py `sync_all()`
6. Update CLAUDE.md template (agent-rules.md)
7. Delete `.claude/skills/` generated files

### Phase 5: Claude Code plugin registration — after Phase 4

1. Configure Claude Code to read skills from `plugins/*/skills/` directly
2. Verify end-to-end `/command` invocation

### Phase 6: Commands help page — after Phase 1

1. Create `/commands` skill with `render_commands.py` script
2. Create dashboard API route `/api/commands`
3. Create dashboard commands page with grouped display

## Alternatives Considered

### Alternative 1: Keep commands in augur.yaml, just improve sync

Continue using `contributions.commands` in augur.yaml but make sync faster/incremental. Rejected because it preserves the concept fragmentation (three discovery paths) and doesn't reduce code complexity.

### Alternative 2: Nested sub-skills (commands/ becomes skills/)

Keep commands grouped under parent skills but rename `commands/` to `skills/` for recursive discovery. Rejected because nested skills is a non-standard concept in Claude Code's plugin model, reducing open-source alignment.

### Alternative 3: MCP-only (no slash command UX)

Eliminate slash commands entirely — everything is an MCP tool. Rejected because the `/command` UX in Claude Code provides a natural invocation mechanism with prompt injection that MCP tools cannot replicate (MCP tools return data, slash commands inject instructions).

## References

- Design doc: `docs/plans/2026-03-06-commands-to-skills-migration-design.md`
- Implementation plan: `docs/plans/2026-03-06-commands-to-skills-migration-plan.md`
- ADR-098: Unify Commands and Skills (prior art)
- ADR-163: Config Decentralization (architectural principle)
- ADR-178: Decentralized Slash Command Discovery (current system being replaced)
- ADR-186: Sync Agents Refactor (code being simplified)

## Impact Manifest

```yaml
paths_renamed:
  - from: "plugins/*/skills/*/commands/*.md"
    to: "plugins/*/skills/*/SKILL.md (standalone skill directories)"
  - from: ".claude/skills/*/SKILL.md (generated)"
    to: "DELETED (read from plugins/ directly)"

apis_changed:
  - name: "discover_commands()"
    location: "src/plugins/command_discovery.py"
    change: "NEW — replaces scan_distributed_commands() from discovery.py"
  - name: "SkillMetadata"
    location: "src/plugins/skill_registry.py"
    change: "ADDED fields: visibility, loop_config, alias, group"
  - name: "discover_auto_commands()"
    location: "plugins/observability/skills/daemon/scripts/adaptive/discovery.py"
    change: "MODIFIED — dual-read from augur.yaml + SKILL.md frontmatter"

patterns_deprecated:
  - pattern: "contributions.commands in augur.yaml"
    replacement: "x-augur-visibility in SKILL.md frontmatter"
  - pattern: "sync_agents --skills / --workflows"
    replacement: "Skills auto-discovered, no sync needed"
  - pattern: ".claude/skills/ generated exports"
    replacement: "Claude Code reads from plugins/ directly"

files_affected:
  - "src/plugins/skill_registry.py"
  - "src/plugins/command_discovery.py (NEW)"
  - "plugins/observability/skills/daemon/scripts/adaptive/discovery.py"
  - "plugins/ai/skills/ai_bridge/scripts/sync_agents/ (gutted)"
  - "plugins/admin/skills/autoloop/ (NEW)"
  - "plugins/admin/skills/auto-*/ (32 NEW)"
  - "plugins/dev/skills/dev-build/ (NEW)"
  - "plugins/dev/skills/dev-merge/ (NEW)"
  - "plugins/dev/skills/debug-protocol/ (NEW)"
  - "plugins/observability/skills/kill-augur/ (NEW)"
  - "plugins/ai/skills/ask/ (NEW)"
  - "plugins/ai/skills/commands/ (NEW)"
  - "53 total new skill directories"
```
