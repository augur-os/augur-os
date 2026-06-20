---
status: Implemented
date: '2026-02-27'
deciders:
- Project team
related:
- ADR-171 (Bidirectional Plugin Sync)
- ADR-130 (Action Dispatch Modes)
- ADR-162 (Action Type Consolidation)
hub: null
tags:
- skill
- command
- consolidation
superseded_by: null
---

# ADR-174: Skill & Command Consolidation

## Context

The Augur system has grown to **118 unique skills/commands** across three layers:

| Layer | Count | Source |
|-------|-------|--------|
| Augur slash commands (workflows) | 54 | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/` |
| Augur skills (augur.yaml actions) | 62 | 17 hubs, 36 plugins |
| Claude plugins | 11 | superpowers (14 sub-skills), feature-dev (3 agents), + 8 others |

**Problems:**

1. **Direct duplicates** — 4 commands duplicate functionality already provided by Claude plugins (e.g., `/dev-review` vs `feature-dev:code-reviewer`)
2. **Thin wrappers** — 11 commands are under 50 lines, many wrapping a single shell operation or forwarding to another command
3. **Category imbalance** — Ops has 15 commands (27% of total), many doing overlapping cleanup tasks
4. **Deprecated residue** — 7 workflows reference deprecated/vestigial patterns but haven't been removed or updated
5. **Hidden commands without clear rationale** — 8 hidden commands, some of which should be visible (e.g., `/onboarding`) and others that should be deleted (e.g., `/ai-bridge-update`)
6. **Growing context cost** — Every command is registered in the agent prompt; 54 commands consume tokens even when unused

The root cause is organic growth without periodic pruning. Each ADR adds commands but none removes them. ADR-171 introduced bidirectional plugin sync, making Claude plugin overlap more visible and actionable.

## Decision

### Phase 1: Remove Dead Commands (8 commands → 0)

Delete workflows that are deprecated, obsolete, or have no active callers.

| Command | Lines | Reason | Action |
|---------|-------|--------|--------|
| `/orch-chain` | 41 | Chain module is vestigial (Memory: 2026-02-22) | Delete workflow |
| `/ai-bridge-update` | 40 | Replaced by `/ops-sync` | Delete workflow |
| `/git-guidelines` | 58 | Reference content, not a command | Move to `docs/references/git-guidelines.md` |
| `/gitignore-inspect` | 22 | Thin wrapper around `git check-ignore` | Delete workflow |
| `/commands` | 10 | Meta-listing — CLAUDE.md already lists all | Delete workflow |
| `/start` | 33 | Subset of `/onboarding` | Delete workflow |
| `/demo` | varies | One-shot demo, not recurring | Move to `docs/guides/demo.md` |
| `/thread-hardening` | 96 | Niche, rarely invoked | Move to `docs/references/thread-hardening.md` |

**Files:**
- Delete: `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/{orch-chain,ai-bridge-update,gitignore-inspect,commands,start}.md`
- Move to docs: `{git-guidelines,demo,thread-hardening}.md` → `docs/references/` or `docs/guides/`
- Update: `plugins/ai/skills/ai_bridge/augur/data/ide-integration/registry.yaml` — remove entries

### Phase 2: Merge Thin Wrappers into Parent Commands (5 merges)

Consolidate commands that are subsets of larger commands into parameterized modes.

| Absorbed | Into | Mechanism |
|----------|------|-----------|
| `/dev-reload` (41 lines) | `/dev-build` | Add `--watch` flag for HMR restart |
| `/dev-deploy` | `/dev-merge` | Add `--push` flag for remote push + cleanup |
| `/orch-offloads` (49 lines) | `/orch-dispatch` | Add `--offload` flag |
| `/orch-swarm` (12 lines) | `/orch-dispatch` | Add `--swarm` flag (default when team detected) |
| `/test-check` (36 lines) | `/test-coverage` | Add `--quick` flag for fast pre-commit check |

**Files:**
- Modify: `dev-build.md` — add `--watch` section from dev-reload
- Modify: `dev-merge.md` — add `--push` section from dev-deploy
- Modify: `orch-dispatch.md` — absorb offloads + swarm modes
- Modify: `test-coverage.md` — add `--quick` mode from test-check
- Delete: `dev-reload.md`, `dev-deploy.md`, `orch-offloads.md`, `orch-swarm.md`, `test-check.md`
- Update: `registry.yaml` — remove absorbed entries, update parent descriptions

### Phase 3: Consolidate Ops Cluster (15 → 10)

The ops category has 15 commands. Merge related cleanup commands into composite workflows.

| Group | Commands | Merged Into | Rationale |
|-------|----------|-------------|-----------|
| Hygiene | `/ops-cleanup`, `/ops-plugin-lint`, `/ops-stale-paths` | `/ops-hygiene` | All do structural validation of plugins/paths |
| Inspection | `/ops-inspect`, `/ops-context` | `/ops-inspect` | Both examine runtime state |
| Performance | `/ops-perf`, `/ops-optimize` | `/ops-perf` | Optimize is a subset of perf analysis |

**Surviving ops commands (10):** `/ops-audit`, `/ops-daemon`, `/ops-debt`, `/ops-docs`, `/ops-hygiene`, `/ops-inspect`, `/ops-kill`, `/ops-perf`, `/ops-rollback`, `/ops-sync`

**Files:**
- Create: `ops-hygiene.md` — combine cleanup + lint + stale-paths
- Modify: `ops-inspect.md` — absorb context inspection
- Modify: `ops-perf.md` — absorb optimize
- Delete: `ops-cleanup.md`, `ops-plugin-lint.md`, `ops-stale-paths.md`, `ops-context.md`, `ops-optimize.md`
- Update: `registry.yaml`

### Phase 4: Resolve Claude Plugin Overlaps (4 pairs)

With ADR-171's bidirectional sync active, declare explicit overlap resolution in augur.yaml files.

| Augur Command | Claude Plugin | Resolution | augur.yaml Declaration |
|---------------|--------------|------------|----------------------|
| `/dev-review` | `feature-dev:code-reviewer` | Keep `/dev-review` — wired to dispatch system | `merge: ignore` on code-reviewer import |
| `/ops-refactor` | `code-simplifier` | Keep both — different scopes (strategic vs tactical) | No change needed — audit confirmed minimal overlap |
| `/dev-debug` | `superpowers:systematic-debugging` | Merge: `/dev-debug` wraps systematic-debugging + adds swarm/offload | `merge: augment` — dev-debug references superpowers skill |
| `/memory-sync` | `claude-md-management:revise-claude-md` | Keep `/memory-sync` — drives full pipeline | `merge: ignore` on revise-claude-md |

**Files:**
- Modify: `plugins/dev/skills/developer/augur.yaml` — add `merge: ignore` for code-reviewer overlap
- Modify: `dev-debug.md` — add reference header to superpowers:systematic-debugging as canonical methodology
- No deletion — both sides preserved with clear ownership

### Phase 5: Reclassify Hidden Commands (8 → 5 hidden)

| Command | Current | Proposed | Rationale |
|---------|---------|----------|-----------|
| `/onboarding` | Hidden | Core | Primary entry point for new sessions |
| `/retrospective` | Hidden | Dev | Valuable development practice |
| `/guide-task-lifecycle` | Hidden | Core | Task management guidance |
| `/memory-sync` | Hidden | Ops | Active tool, no reason to hide |
| `/ai-bridge-update` | Hidden | **Deleted** (Phase 1) | — |
| `/git-guidelines` | Hidden | **Moved to docs** (Phase 1) | — |
| `/gitignore-inspect` | Hidden | **Deleted** (Phase 1) | — |
| `/thread-hardening` | Hidden | **Moved to docs** (Phase 1) | — |

**Remaining hidden (1):** None of the original hidden commands survive as hidden. If any new commands need hidden status, they must justify it in their workflow frontmatter.

**Files:**
- Modify: `registry.yaml` — update category for onboarding (→core), retrospective (→dev), guide-task-lifecycle (→core), memory-sync (→ops)

### Phase 6: Update CLAUDE.md Command Listing

After all changes, the command listing in `agent-rules.md` (which generates CLAUDE.md) must reflect:

| Category | Before | After |
|----------|--------|-------|
| Core | 11 | 12 (+onboarding, +guide-task-lifecycle, −commands, −demo, −start) |
| Dev | 9 | 7 (−dev-reload, −dev-deploy, +retrospective) |
| Orch | 5 | 2 (−orch-chain, −orch-offloads, −orch-swarm) |
| Test | 6 | 5 (−test-check) |
| Ops | 15 | 11 (−5 merged, +ops-hygiene, +memory-sync) |
| Hidden | 8 | 0 |
| **Total** | **54** | **37** |

**Net reduction: 17 commands (−31%)**

Run `sync_agents.py --all` to regenerate CLAUDE.md and distribute to all IDE adapters.

## Consequences

### Positive

- **31% fewer commands** — 54 → 37 reduces cognitive load and prompt token cost
- **Zero hidden commands** — every command is discoverable or deleted
- **Clearer categories** — ops drops from 15 to 11, orch from 5 to 2
- **Plugin overlap resolved** — explicit merge declarations prevent ADR-171 from creating confusion
- **Reference content separated** — git-guidelines, thread-hardening moved to docs where they belong

### Negative

- **Breaking muscle memory** — users typing `/dev-reload` will need `/dev-build --watch`
- **Migration effort** — 17 workflow files touched, registry.yaml rewritten
- **Merged commands are larger** — `/ops-hygiene` and `/orch-dispatch` grow in complexity

### Neutral

- All 62 augur.yaml skill actions are untouched — this ADR only consolidates workflow commands
- Claude plugin imports via ADR-171 are unaffected — only the overlap resolution declarations change
- Test commands remain mostly stable (only `/test-check` absorbed)

## Implementation Order

```
Phase 1: Remove Dead Commands
├── Step 1.1: Delete 5 workflow files (orch-chain, ai-bridge-update, gitignore-inspect, commands, start)
├── Step 1.2: Move 3 workflows to docs/ (git-guidelines, demo, thread-hardening)
└── Step 1.3: Remove entries from registry.yaml

Phase 2: Merge Thin Wrappers (depends on Phase 1)
├── Step 2.1: Merge dev-reload into dev-build (--watch flag)
├── Step 2.2: Merge dev-deploy into dev-merge (--push flag)
├── Step 2.3: Merge orch-offloads + orch-swarm into orch-dispatch
├── Step 2.4: Merge test-check into test-coverage (--quick flag)
└── Step 2.5: Delete absorbed workflow files + update registry.yaml

Phase 3: Consolidate Ops Cluster (depends on Phase 1)
├── Step 3.1: Create ops-hygiene.md from cleanup + plugin-lint + stale-paths
├── Step 3.2: Merge ops-context into ops-inspect
├── Step 3.3: Merge ops-optimize into ops-perf
└── Step 3.4: Delete absorbed workflow files + update registry.yaml

Phase 4: Resolve Plugin Overlaps (independent)
├── Step 4.1: Add merge:ignore for code-reviewer in developer augur.yaml
└── Step 4.2: Add superpowers:systematic-debugging reference to dev-debug.md

Phase 5: Reclassify Hidden Commands (depends on Phase 1)
└── Step 5.1: Update registry.yaml categories for onboarding, retrospective, guide-task-lifecycle, memory-sync

Phase 6: Regenerate (depends on all phases)
├── Step 6.1: Run sync_agents.py --all
├── Step 6.2: Verify CLAUDE.md command listing
└── Step 6.3: Run test suite for regressions
```

## Alternatives Considered

### Alternative A: No Consolidation — Status Quo

Keep all 54 commands as-is. Let ADR-171 imports create natural competition.

**Rejected**: Organic growth without pruning is how we reached 118 items. The overlap will only increase as more Claude plugins are installed.

### Alternative B: Aggressive Consolidation — Single `/augur` Command

Replace all commands with `augur <verb> <noun>` subcommand pattern (e.g., `augur test coverage`, `augur ops sync`).

**Rejected**: Too disruptive. Breaks all existing muscle memory and IDE adapter configurations simultaneously. The slash command pattern is standard across Claude Code, Cursor, and Windsurf.

### Alternative C: Plugin-Only — Migrate All Workflows to Claude Plugin Skills

Convert every Augur workflow into a Claude plugin skill and rely entirely on the Claude ecosystem.

**Rejected**: Augur commands run across 11 IDE adapters via sync_agents.py. Claude plugin skills only work in Claude Code. This would break Cursor, Windsurf, OpenCode, Copilot, and Gemini support.

## References

- ADR-171: Bidirectional Claude Plugin Sync — provides the `merge` declaration mechanism used in Phase 4
- ADR-130: Action Dispatch Modes — defines the `fire/oneshot/ide/chat/modal` dispatch used by augur.yaml actions (unaffected)
- ADR-162: Action Type Consolidation — prior consolidation effort focused on dispatch types, not command count
- Memory (2026-02-22): `/orch-chain` chain module is vestigial
- Memory (2026-02-22): Canonical two-layer pattern is SKILL.md + action YAML

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "agent-workflows/orch-chain.md"
      to: "(deleted)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ai-bridge-update.md"
      to: "(deleted)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/commands.md"
      to: "(deleted)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/start.md"
      to: "(deleted)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/gitignore-inspect.md"
      to: "(deleted)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/dev-reload.md"
      to: "(deleted – merged into dev-build.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/dev-deploy.md"
      to: "(deleted – merged into dev-merge.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/orch-offloads.md"
      to: "(deleted – merged into orch-dispatch.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/orch-swarm.md"
      to: "(deleted – merged into orch-dispatch.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/test-check.md"
      to: "(deleted – merged into test-coverage.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ops-cleanup.md"
      to: "(deleted – merged into ops-hygiene.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ops-plugin-lint.md"
      to: "(deleted – merged into ops-hygiene.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ops-stale-paths.md"
      to: "(deleted – merged into ops-hygiene.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ops-context.md"
      to: "(deleted – merged into ops-inspect.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/ops-optimize.md"
      to: "(deleted – merged into ops-perf.md)"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/git-guidelines.md"
      to: "docs/references/git-guidelines.md"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/demo.md"
      to: "docs/guides/demo.md"
      scope: "plugins/ai/skills/ai_bridge/"
    - from: "agent-workflows/thread-hardening.md"
      to: "docs/references/thread-hardening.md"
      scope: "plugins/ai/skills/ai_bridge/"
  files_affected:
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-workflows/*.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/ide-integration/registry.yaml"
    - glob: "plugins/dev/skills/developer/augur.yaml"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-174: Skill & Command Consolidation**.

Read the full ADR: `docs/decisions/ADR-174-skill-command-consolidation.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-174-consolidation", description="Implementing ADR-174: Skill & Command Consolidation")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-174-consolidation", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-174-consolidation team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-174-consolidation`

#### Phase 1: Remove Dead Commands
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Delete 5 dead workflow files | `agent-workflows/{orch-chain,ai-bridge-update,gitignore-inspect,commands,start}.md` |
| 1.2 | developer | low | Move 3 workflows to docs/ | `agent-workflows/{git-guidelines,demo,thread-hardening}.md` → `docs/{references,guides}/` |
| 1.3 | developer | low | Remove all 8 entries from registry.yaml | `ide-integration/registry.yaml` |

#### Phase 2: Merge Thin Wrappers (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Merge dev-reload into dev-build with --watch flag | `agent-workflows/dev-build.md`, delete `dev-reload.md` |
| 2.2 | developer | medium | Merge dev-deploy into dev-merge with --push flag | `agent-workflows/dev-merge.md`, delete `dev-deploy.md` |
| 2.3 | developer | medium | Merge orch-offloads + orch-swarm into orch-dispatch | `agent-workflows/orch-dispatch.md`, delete 2 files |
| 2.4 | developer | medium | Merge test-check into test-coverage with --quick flag | `agent-workflows/test-coverage.md`, delete `test-check.md` |
| 2.5 | developer | low | Update registry.yaml — remove 5 absorbed entries | `ide-integration/registry.yaml` |

#### Phase 3: Consolidate Ops Cluster (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create ops-hygiene.md combining cleanup + plugin-lint + stale-paths | `agent-workflows/ops-hygiene.md` (new) |
| 3.2 | developer | medium | Merge ops-context into ops-inspect | `agent-workflows/ops-inspect.md` |
| 3.3 | developer | medium | Merge ops-optimize into ops-perf | `agent-workflows/ops-perf.md` |
| 3.4 | developer | low | Delete 5 absorbed files + update registry.yaml | 5 workflow files, `registry.yaml` |

#### Phase 4: Resolve Plugin Overlaps (independent)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Add merge:ignore for code-reviewer in developer augur.yaml | `plugins/dev/skills/developer/augur.yaml` |
| 4.2 | developer | medium | Add superpowers:systematic-debugging reference to dev-debug | `agent-workflows/dev-debug.md` |

#### Phase 5: Reclassify Hidden Commands (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Update registry.yaml categories: onboarding→core, retrospective→dev, guide-task-lifecycle→core, memory-sync→ops | `ide-integration/registry.yaml` |

#### Phase 6: Regenerate & Verify (depends on all phases)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | devops | low | Run `sync_agents.py --all` to regenerate CLAUDE.md + adapters |
| 6.2 | validator | low | Verify CLAUDE.md lists exactly 37 commands in correct categories |
| 6.3 | validator | low | Run `pytest tests/` — verify no regressions |
| 6.4 | validator | low | Run `python3 .github/scripts/scan_stale_paths.py --ci` — verify no stale references to deleted workflows |
| 6.5 | architect | low | Verify ADR intent: 54→37 commands, 0 hidden, all overlaps resolved |

### Completion Criteria
- [ ] All phases executed
- [ ] 17 workflow files deleted or moved
- [ ] registry.yaml reflects 37 commands in 5 categories (core/dev/orch/test/ops), 0 hidden
- [ ] `sync_agents.py --all` succeeds
- [ ] All tests pass (`pytest tests/`)
- [ ] Stale path scanner clean
- [ ] Impact Manifest validated — zero references to deleted workflow filenames in active code
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-174-skill-command-consolidation.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
