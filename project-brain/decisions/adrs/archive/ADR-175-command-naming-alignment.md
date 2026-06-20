---
status: Implemented
date: '2026-02-27'
deciders:
- Project team
related:
- ADR-174 (Skill & Command Consolidation)
- ADR-053 (Slash Command Restructure)
- ADR-097 (Command Consolidation)
hub: null
tags:
- command
- naming
- alignment
superseded_by: null
---

# ADR-175: Command Naming Alignment

## Context

After ADR-174 consolidated 54 commands down to 37, the remaining set has inconsistent naming:

1. **Orphan names**: `retrospective`, `memory-sync`, `onboarding` sit in prefixed groups (Dev, Ops, Core) but lack their group prefix — the only unprefixed commands outside Core
2. **Cryptic abbreviations**: `app-dd` means "Danit Design content pipeline" but reads as a generic abbreviation
3. **Verbose names**: `guide-task-lifecycle` (21 chars), `dev-cowork-export` (17 chars), `orch-context-audit` (18 chars) are longer than they need to be
4. **Inconsistent noun-verb**: `context-save` (noun-verb) vs `dev-build` (group-verb) — mixed patterns

These issues hurt discoverability and type-speed. CLI best practices (git, docker, kubectl) show that:
- **High-frequency commands should be short** (git add, git log)
- **Grouped commands should carry consistent prefixes** (kubectl get, kubectl apply)
- **Names should be self-describing** — no abbreviations that require documentation

## Decision

Rename 11 of 37 commands following two principles:
1. **Core commands (no prefix) = short and memorable** — typed daily
2. **Group commands (prefixed) = consistent category prefix** — no orphans

### Rename Map

| Current | New | Rationale |
|---------|-----|-----------|
| `app-dd` | `danit` | Brand name, not a generic concept — name it directly |
| `app-post` | `post` | Drop `app-` prefix — "post" is unambiguous in core |
| `context-save` | `save` | Session context is implied — shorter |
| `guide-task-lifecycle` | `guide` | 21 chars → 5 chars — "guide" captures the intent |
| `onboarding` | `onboard` | Verb form, shorter, matches action pattern |
| `dev-cowork-export` | `dev-export` | Only one export target (Cowork) — implied |
| `retrospective` | `dev-retro` | Gets its `dev-` prefix + shortened |
| `orch-context-audit` | `orch-audit` | "context" redundant — orchestration IS about context |
| `test-self-heal` | `test-heal` | Shorter, "self" is implied |
| `memory-sync` | `ops-memory` | Gets its `ops-` prefix — it's an operational action |

### File Operations Per Command

Each rename requires:
1. **Rename source workflow**: `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/{old}.md` → `{new}.md`
2. **Update internal heading**: `# /{old}` → `# /{new}` inside the .md
3. **Update registry.yaml**: Change the entry name in `plugins/ai/skills/ai_bridge/augur/data/ide-integration/registry.yaml`
4. **Update cross-references**: Any workflow that references `/{old}` in its body
5. **Regenerate**: `sync_agents.py --all` propagates to all 11 IDE adapters and CLAUDE.md

### What Does NOT Change

- **API routes** stay the same (`/api/agents/onboarding/` — this is an API concept, not a command name)
- **Python modules** stay the same (`retrospective.py`, `memory_sync.py` — these are library names)
- **ADR references** in `docs/decisions/` are historical and not updated
- **Concepts** in docs that use the word "onboarding" or "retrospective" generically

### Post-Rename Command Listing

**Core** (10): `/adr`, `/ask`, `/danit`, `/focus`, `/guide`, `/learn`, `/onboard`, `/post`, `/rag`, `/save`

**Dev** (8): `/dev-build`, `/dev-debug`, `/dev-export`, `/dev-fix`, `/dev-merge`, `/dev-retro`, `/dev-review`, `/dev-tidy`

**Orch** (2): `/orch-audit`, `/orch-dispatch`

**Test** (5): `/test-client`, `/test-coverage`, `/test-heal`, `/test-nightly`, `/test-ui`

**Ops** (12): `/ops-audit`, `/ops-daemon`, `/ops-debt`, `/ops-docs`, `/ops-hygiene`, `/ops-inspect`, `/ops-kill`, `/ops-memory`, `/ops-perf`, `/ops-refactor`, `/ops-rollback`, `/ops-sync`

## Consequences

**Positive**:
- Zero orphan commands — every grouped command carries its prefix
- Core commands are all 3-6 chars — fast to type
- Self-describing names — no need to look up what `app-dd` means
- Consistent pattern makes new commands easy to name

**Negative**:
- Muscle memory disruption for 11 commands (mitigated: underscore aliases auto-generated)
- Stale references in docs, memory, RAG indices need sweep

**Neutral**:
- Total count stays at 37 — no commands added or removed
- Category distribution unchanged

## Implementation Order

```
Phase 1: Rename Workflow Files (PARALLEL)
├── Rename all 11 .md files in agent-workflows/
├── Update internal headings and usage sections
└── Update registry.yaml entries

Phase 2: Fix Cross-References (PARALLEL)
├── Update topic docs (WORKFLOWS.md, CONTEXT.md, AGENTS.md)
├── Update cross-referencing workflows that mention renamed commands
├── Update .clinerules, demo playbooks, insights.yaml
└── Update any dashboard code dispatching by command name

Phase 3: Regenerate & Verify (PIPELINE)
├── Run sync_agents.py --all
├── Verify CLAUDE.md shows correct names
├── Grep for all 11 old names — zero active-code hits
└── Update ADR status to Implemented
```

## Alternatives Considered

### A: Prefix Everything (including Core)
Add `core-` prefix to all core commands: `/core-adr`, `/core-ask`, `/core-save`.

**Rejected**: Adds 5-6 chars to the most frequently typed commands. Git doesn't prefix `add`, `commit`, `log` — high-frequency commands earn the right to be short.

### B: Verb-Noun Restructure
Rename everything to verb-first: `/build`, `/debug`, `/audit`, `/sync`.

**Rejected**: Massive rename (all 37 commands), loses category grouping, creates collision risk (`/sync` — memory or ops?), destroys all muscle memory.

## References

- ADR-174: Skill & Command Consolidation (just implemented — reduced 54 → 37)
- ADR-053: Slash Command Restructure (original category system)
- ADR-097: Command Consolidation (first consolidation pass)
- [CLI naming conventions](https://clig.dev/#naming) — Command Line Interface Guidelines

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "app-dd"
      to: "danit"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "app-post"
      to: "post"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "context-save"
      to: "save"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "guide-task-lifecycle"
      to: "guide"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "dev-cowork-export"
      to: "dev-export"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "dev-retro"
      to: "dev-retro"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "orch-context-audit"
      to: "orch-audit"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "test-self-heal"
      to: "test-heal"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
    - from: "memory-sync"
      to: "ops-memory"
      scope: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/"
  patterns_deprecated:
    - grep: "/app-dd"
      replacement: "/danit"
    - grep: "/app-post"
      replacement: "/post"
    - grep: "/context-save"
      replacement: "/save"
    - grep: "/guide-task-lifecycle"
      replacement: "/guide"
    - grep: "/onboarding"
      replacement: "/onboard"
    - grep: "/dev-cowork-export"
      replacement: "/dev-export"
    - grep: "/retrospective"
      replacement: "/dev-retro"
    - grep: "/orch-context-audit"
      replacement: "/orch-audit"
    - grep: "/test-self-heal"
      replacement: "/test-heal"
    - grep: "/memory-sync"
      replacement: "/ops-memory"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-175: Command Naming Alignment**.

Read the full ADR: `docs/decisions/ADR-175-command-naming-alignment.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-175-naming", description="Implementing ADR-175: Command Naming Alignment")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-175-naming", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-175 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-175-naming`

#### Phase 1: Rename Workflow Files
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Rename `app-dd.md` → `danit.md`, update heading to `# /danit` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/danit.md` |
| 1.2 | developer | low | Rename `app-post.md` → `post.md`, update heading to `# /post` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/post.md` |
| 1.3 | developer | low | Rename `context-save.md` → `save.md`, update heading to `# /save` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/save.md` |
| 1.4 | developer | low | Rename `guide-task-lifecycle.md` → `guide.md`, update heading to `# /guide` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/guide.md` |
| 1.5 | developer | low | Rename `onboarding.md` → `onboard.md`, update heading to `# /onboard` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/onboard.md` |
| 1.6 | developer | low | Rename `dev-cowork-export.md` → `dev-export.md`, update heading to `# /dev-export` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/dev-export.md` |
| 1.7 | developer | low | Rename `retrospective.md` → `dev-retro.md`, update heading to `# /dev-retro`, update visibility to `dev` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/dev-retro.md` |
| 1.8 | developer | low | Rename `orch-context-audit.md` → `orch-audit.md`, update heading to `# /orch-audit` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/orch-audit.md` |
| 1.9 | developer | low | Rename `test-self-heal.md` → `test-heal.md`, update heading to `# /test-heal` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/test-heal.md` |
| 1.10 | developer | low | Rename `memory-sync.md` → `ops-memory.md`, update heading to `# /ops-memory` | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-memory.md` |
| 1.11 | devops | low | Update all 11 entries in `registry.yaml` | `plugins/ai/skills/ai_bridge/augur/data/ide-integration/registry.yaml` |

#### Phase 2: Fix Cross-References
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update topic docs: replace all `/old-name` → `/new-name` references | `plugins/ai/skills/ai_bridge/augur/data/agent-topics/WORKFLOWS.md`, `CONTEXT.md`, `AGENTS.md` |
| 2.2 | developer | medium | Update cross-referencing workflows that mention renamed commands | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/*.md` (grep for old names) |
| 2.3 | developer | low | Update `.clinerules/ai-bridge-skills.md`, `.clinerules/augur-rules.md` | `.clinerules/*.md` |
| 2.4 | developer | low | Update demo playbooks referencing old command names | `plugins/ai/skills/ai_bridge/augur/data/demo/playbooks/*.yaml` |
| 2.5 | developer | low | Update insights.yaml if referencing old names | `plugins/observability/skills/daemon/augur/data/insights/insights.yaml` |
| 2.6 | developer | medium | Update any dashboard code dispatching commands by name | `src/dashboard/hooks/useCliChat.ts`, `src/dashboard/hooks/useSessionLifecycle.ts`, `plugins/*/skills/*/augur/dashboard/*.tsx` |
| 2.7 | developer | low | Rename SKILL.md directories if they exist | `.claude/skills/test-self-heal/` → `.claude/skills/test-heal/`, `plugins/ai/skills/ai_bridge/augur/data/skills/orch-context-audit/` → `orch-audit/` |
| 2.8 | developer | low | Update `generate_registry.py` and `export_cowork_plugin.py` | `src/dashboard/scripts/generate_registry.py`, `plugins/ai/skills/ai_bridge/scripts/export_cowork_plugin.py` |

#### Phase 3: Regenerate & Verify
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | devops | low | Run `sync_agents.py --all` to regenerate all IDE adapters |
| 3.2 | validator | low | Verify CLAUDE.md shows all 37 correct names in correct categories |
| 3.3 | validator | low | Grep for all 11 old command names — zero hits in active code (exclude docs/decisions/) |
| 3.4 | devops | low | Run `python3 .github/scripts/scan_stale_paths.py --ci` for stale path check |
| 3.5 | devops | low | Update ADR-175 status to Implemented |

### Completion Criteria
- [ ] All 11 workflow files renamed with updated headings
- [ ] registry.yaml updated with new names
- [ ] Zero stale `/old-name` references in active code
- [ ] `sync_agents.py --all` regenerates cleanly
- [ ] CLAUDE.md shows correct 37-command listing
- [ ] Stale path scanner clean
- [ ] ADR status updated to Implemented

### How to Run
```
/implement-adr docs/decisions/ADR-175-command-naming-alignment.md
```
