---
status: Implemented
date: '2026-03-03'
deciders:
- Gur Sannikov
related:
- ADR-190 (Page Builder)
- ADR-062 (Observability Hub)
- ADR-093 (Dev Hub)
hub: null
tags:
- dissolve
- core
- plugin
- bundle
superseded_by: null
---

# ADR-201: Dissolve Core Plugin Bundle

## Context

The `plugins/core/` bundle was created recently (2026-03-03) as a home for framework-level skills. It currently contains only 2 skills:

- **executor** — a scaffold placeholder with no commands, no MCP tools, no real functionality. Just a `hub: {id: core, role: primary}` declaration, one empty dashboard page, and 3 chain-plan backlog files.
- **page-builder** — a block-based page builder (ADR-190) that already contributes its single page to the **ai** hub at order 909.

The core bundle has no conceptual gravity. Its skills don't relate to each other, and neither needs a dedicated bundle to function. The executor is premature (YAGNI), and page-builder already belongs to ai. Maintaining a bundle for 2 unrelated skills — one of which is empty — violates the plugin decentralization principle that bundles should be self-contained and meaningful.

Additionally, the `core` entry in `hub_registry.yaml` is `always_enabled: true` with an empty skills list, adding a phantom hub that serves no user-facing purpose.

This decision was reached after a broader brainstorming session that also evaluated merging the observability and dev bundles. The conclusion: **don't merge observe + dev** (both work well independently at 94/100 and 3,273 files respectively), but **dissolve core** because it lacks justification to exist.

## Decision

### 1. Move page-builder to ai bundle

Move `plugins/core/skills/page-builder/` to `plugins/ai/skills/page-builder/`.

No augur.yaml changes needed — page-builder already declares `contributes_to: ai` and `hub: {id: ai, owner: false}`. The skill mounts identically regardless of which bundle directory it lives in.

**Files moved**: 31 files (dashboard pages, lib blocks, API routes, augur.yaml, SKILL.md)

### 2. Delete executor skill

Remove `plugins/core/skills/executor/` entirely.

- No commands, no MCP tools, no actions depend on it
- The `hub: {id: core, role: primary}` declaration in its augur.yaml is the only thing keeping the `core` hub alive
- The 3 chain-plan backlog files in `data/agent-tasks/backlog/` are ephemeral session artifacts with no archival value

### 3. Delete core bundle

Remove `plugins/core/` directory after steps 1 and 2.

### 4. Clean up references

- Remove or let regeneration clean the `core` entry from `config/dashboard/generated/hub_registry.yaml`
- Re-run `mount-plugins` and `sync_agents` to regenerate configs
- Update docs that reference `plugins/core` (ADR-190, memory files, hardening reports)

## Consequences

**Positive**:
- One fewer bundle to maintain (18 bundles → 17)
- Eliminates a phantom `core` hub from the registry
- page-builder lives alongside the ai skills it contributes to — cleaner discovery
- Removes a premature abstraction (executor) before it accumulates cruft

**Negative**:
- If a "core framework" bundle is needed later, it would need to be recreated. Low cost — creating a bundle is trivial.

**Neutral**:
- No dashboard route changes (page-builder was already on `/ai`)
- No command changes (core had zero commands)
- No MCP tool changes (core had zero tools)
- Observability and dev bundles are unaffected

## Implementation Order

```
Phase 1: Move and delete
├── Step 1: Move plugins/core/skills/page-builder/ → plugins/ai/skills/page-builder/
├── Step 2: Delete plugins/core/skills/executor/
└── Step 3: Delete plugins/core/

Phase 2: Regenerate and clean references (depends on Phase 1)
├── Step 4: Run mount-plugins to regenerate dashboard mounts
├── Step 5: Run sync_agents.py --all to regenerate agent configs
└── Step 6: Update ADR-190 and doc references from plugins/core to plugins/ai
```

## Alternatives Considered

### A. Merge core into admin
Admin is the "system infrastructure" bundle, so core skills could go there. Rejected because page-builder is not admin infrastructure — it's an ai-hub feature. Forcing it into admin would be a worse conceptual fit than its current home.

### B. Keep core with a clearer mandate
Give core a real purpose and plan to add more framework skills. Rejected per YAGNI — there are no concrete framework skills planned, and creating a bundle "in case we need it" is premature. If the need arises, creating a new bundle is trivial.

## References

- ADR-190: Block-based page builder (created page-builder skill)
- ADR-062: Observability Hub (evaluated during brainstorming, kept separate)
- ADR-093: Project Dev Hub (evaluated during brainstorming, kept separate)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/core/skills/page-builder"
      to: "plugins/ai/skills/page-builder"
      scope: "docs/, config/"
    - from: "plugins/core/skills/executor"
      to: "(deleted)"
      scope: "docs/, config/"
    - from: "plugins/core"
      to: "(deleted)"
      scope: "docs/, config/"
  files_affected:
    - glob: "docs/decisions/ADR-190-page-builder.md"
    - glob: "config/dashboard/generated/hub_registry.yaml"
    - glob: "docs/generated/hardening/hardening-2026-03-0*.md"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-201: Dissolve Core Plugin Bundle**.

Read the full ADR: `docs/decisions/ADR-201-dissolve-core-bundle.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-201-dissolve-core", description="Implementing ADR-201: Dissolve Core Plugin Bundle")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Agent(subagent_type="general-purpose", team_name="adr-201-dissolve-core", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-201 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: Phase 1 is PARALLEL (steps 1-3 are independent file operations). Phase 2 is PIPELINE (depends on Phase 1).
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-201-dissolve-core`

#### Phase 1: Move and Delete
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Move `plugins/core/skills/page-builder/` to `plugins/ai/skills/page-builder/` (preserve all contents, no augur.yaml changes needed) | `plugins/core/skills/page-builder/**` → `plugins/ai/skills/page-builder/**` |
| 1.2 | developer | low | Delete `plugins/core/skills/executor/` entirely | `plugins/core/skills/executor/` |
| 1.3 | developer | low | Delete `plugins/core/` directory (after 1.1 and 1.2 empty it) | `plugins/core/` |

#### Phase 2: Regenerate and Clean References
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | devops | low | Run `npx tsx scripts/mount-plugins.ts` to regenerate dashboard mounts | `src/app/`, `config/dashboard/generated/` |
| 2.2 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` to regenerate agent configs | `CLAUDE.md`, `.cursorrules`, config files |
| 2.3 | developer | low | Update references in `docs/decisions/ADR-190-page-builder.md` — change `plugins/core` to `plugins/ai` | `docs/decisions/ADR-190-page-builder.md` |
| 2.4 | developer | low | Grep for any remaining `plugins/core` references in docs/ and update or remove them | `docs/**` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run `npm run build` — verify no broken imports or missing pages |
| 3.2 | validator | low | Run `python3 .github/scripts/scan_stale_paths.py --ci` — verify no phantom `plugins/core` references |
| 3.3 | devops | low | Verify `core` hub is removed from regenerated `hub_registry.yaml` |

### Completion Criteria
- [ ] All phases executed
- [ ] `npm run build` passes
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean — zero `plugins/core` references in active code
- [ ] Impact Manifest validated — zero stale references for `plugins/core`
- [ ] `core` hub removed from `hub_registry.yaml`
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-201-dissolve-core-bundle.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
