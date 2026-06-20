---
status: Implemented
date: '2026-02-13'
deciders:
- Gur Sannikov
related:
- ADR-096 (progressive disclosure)
- ADR-053 (slash command compaction)
hub: null
tags:
- command
- consolidation
- naming
superseded_by: null
---

# ADR-097: Command Consolidation & Naming

## Context

The system has 40 user-facing commands + 8 hidden + 37 chains. Usage analysis over 6 weeks reveals:
- **10 commands** are used regularly (daily/weekly)
- **7 commands** have zero invocations in 6 weeks
- **22 chains** have never been executed
- Naming is inconsistent: `ops-*` prefix on some, verbose names where unnecessary (`ops-self-heal-test`, `review-offloads`)

Goals:
1. Delete truly dead commands and chains
2. Clean up naming: drop redundant prefixes, keep full readable words
3. Integrate `/ops-perf` into CI workflow instead of standalone
4. Keep operation-mode chains (google, career, health, venture) for near-term use

## Decision

### 1. Delete Dead Commands (3)

| Source File | Current Alias | Reason |
|-------------|---------------|--------|
| `documentation-sync.md` | `/ops-docs` | 0 uses in 6 weeks, 211 lines |
| `tech-debt-triage.md` | `/ops-debt` | 0 uses, `/tidy` + markers cover this |
| `rollback-recovery.md` | `/ops-rollback` | 0 uses, `git revert` is simpler |

Also delete broken symlink: `.claude/commands/kill-exocortex.md`

### 2. Delete Dead Chains (17)

| Chain | Skill | Lines | Reason |
|-------|-------|-------|--------|
| `bug_workflow.yaml` | developer | 89 | `/debug` + `/fix` cover this |
| `feature_development.yaml` | developer | 86 | `/impl` supersedes |
| `dashboard_hardening.yaml` | frontend | 28 | `/harden` covers this |
| `generate_delight.yaml` | frontend | 25 | Never used |
| `redesign_page.yaml` | frontend | 32 | `/harden` + `/impl` cover this |
| `ui_quality_audit.yaml` | frontend | 41 | `/harden` covers this |
| `cli-integration-audit.yaml` | mcp-app-factory | 163 | Never used |
| `cli-smoke-test.yaml` | mcp-app-factory | 28 | Never used |
| `plugin-audit.yaml` | mcp-app-factory | 104 | Never used |
| `plugin-creation.yaml` | mcp-app-factory | 118 | `/import` covers this |
| `plugin-migration.yaml` | mcp-app-factory | 136 | Never used |
| `skill_refactoring.yaml` | mcp-app-factory | 32 | Never used |
| `code_review.yaml` | validator | 42 | `/review` covers this |
| `plugin_batch_verification.yaml` | validator | 170 | Never used |
| `plugin_verification.yaml` | validator | 299 | Never used |
| `qa_pipeline.yaml` | validator | 27 | `/check` + `/nightly` cover this |
| `knowledge_capture.yaml` | knowledge | 27 | `/learn` covers this |

**Total savings**: 3 commands (~630 lines) + 17 chains (~1,447 lines) = ~2,077 lines removed.

### 3. Rename Commands

Naming convention:
- **Full English words** — no cryptic abbreviations (`/coverage` not `/cov`, `/implement` not `/impl`)
- **Drop redundant prefixes** — `/audit` not `/ops-audit`, `/cleanup` not `/ops-cleanup`
- **Max 2 natural words** — `/self-heal` not `/ops-self-heal-test`, `/write-adr` stays
- **Keep unchanged** if already clean — most daily commands stay as-is

Only 13 commands actually change. The rest are already well-named.

| Source File | Old Alias | New Alias | Change |
|-------------|-----------|-----------|--------|
| **Unchanged (27 commands)** | | | |
| `nightly.md` | `/nightly` | `/nightly` | — |
| `code-review.md` | `/review` | `/review` | — |
| `rebuild-ui.md` | `/build` | `/build` | — |
| `ci-check.md` | `/check` | `/check` | — |
| `swarm.md` | `/swarm` | `/swarm` | — |
| `learn.md` | `/learn` | `/learn` | — |
| `merge.md` | `/merge` | `/merge` | — |
| `sync-repos.md` | `/deploy` | `/deploy` | — |
| `debug-protocol.md` | `/debug` | `/debug` | — |
| `load-context.md` | `/start` | `/start` | — |
| `focus.md` | `/focus` | `/focus` | — |
| `reload-dashboard.md` | `/reload` | `/reload` | — |
| `review-markers.md` | `/tidy` | `/tidy` | — |
| `chain.md` | `/chain` | `/chain` | — |
| `inspect.md` | `/inspect` | `/inspect` | — |
| `file-bug.md` | `/fix` | `/fix` | — |
| `commands.md` | `/commands` | `/commands` | — |
| skill:`write-adr` | `/write-adr` | `/write-adr` | — |
| skill:`harden` | `/harden` | `/harden` | — |
| skill:`auto-fix` | `/auto-fix` | `/autofix` | — |
| skill:`import` | `/import` | `/import` | — |
| `run-coverage.md` | `/coverage` | `/coverage` | — |
| `context-audit.md` | `/context-audit` | `/context-audit` | — |
| `context-save.md` | `/context-save` | `/context-save` | — |
| `client-test.md` | `/client-test` | `/client-test` | — |
| `performance-profiling.md` | `/ops-perf` | `/ops-perf` | — (integrated into nightly) |
| `dispatch-subagent.md` | `/dispatch-subagent` | `/dispatch-subagent` | — |
| **Renamed (13 commands)** | | | |
| skill:`implement-adr` | `/implement-adr` | `/implement` | Drop `-adr` (only ADR gets implemented) |
| `sync-agents.md` | `/ops-sync` | `/sync` | Drop `ops-` prefix |
| `dependency-audit.md` | `/ops-audit` | `/audit` | Drop `ops-` prefix |
| `structure-cleanup.md` | `/ops-cleanup` | `/cleanup` | Drop `ops-` prefix |
| `kill-augur.md` | `/ops-kill` | `/kill` | Drop `ops-` prefix |
| `self-heal-test.md` | `/ops-self-heal-test` | `/self-heal` | Shorter, still readable |
| `review-offloads.md` | `/review-offloads` | `/offloads` | Drop `review-` (it's always a review) |
| `ai-bridge-update.md` | `/_ai-bridge-update` | `/_bridge-update` | Shorter but clear |
| `git-guidelines.md` | `/_git-guidelines` | `/_git-rules` | Shorter but clear |
| `gitignore-inspect.md` | `/_gitignore-inspect` | `/_gitignore` | Drop `-inspect` |
| `guide-task-lifecycle.md` | `/_guide-task-lifecycle` | `/_task-guide` | Reorder for clarity |
| `memory-sync.md` | `/_memory-sync` | `/_memory-sync` | — (already clean) |
| `onboarding.md` | `/_onboarding` | `/_onboarding` | — (already clean) |
| `retrospective.md` | `/_retrospective` | `/_retrospective` | — (already clean) |
| `thread-hardening.md` | `/_thread-hardening` | `/_clarify` | Rename to intent |

### 4. Integrate `/ci-perf` into Nightly

Add performance profiling as a step in the `/nightly` workflow instead of standalone. The nightly workflow already runs tests, lint, security — performance is a natural addition.

**Action**: Add a "perf check" phase to `nightly.md` that invokes the performance profiling logic from `performance-profiling.md`. Keep `/ci-perf` as a standalone for ad-hoc use.

### 5. Keep Chains (20)

| Chain | Skill | Reason |
|-------|-------|--------|
| `auto-fix-markers.yaml` | developer | New from ADR-096 |
| `data_migration.yaml` | developer | Useful when needed |
| `incident_response.yaml` | devops | Insurance |
| `open_source_release.yaml` | devops | Releasing soon |
| `system_optimization.yaml` | advisor | Advisory |
| `interview_prep.yaml` | career | Operation mode |
| `content_campaign.yaml` | content | Operation mode |
| `health_checkup.yaml` | health | Operation mode |
| `deal_pipeline.yaml` | venture-augur | Operation mode |
| `investor_demo.yaml` | venture-augur | Operation mode |
| `product_launch.yaml` | venture-augur | Operation mode |
| `daily_briefing.yaml` | google-workspace | Integrating soon |
| `email_triage.yaml` | google-workspace | Integrating soon |
| `weekly_digest.yaml` | google-workspace | Integrating soon |
| `apply_support_patch.yaml` | channels | Active |
| `full_update.yaml` | updater | Active |
| `adaptive_growth_cycle.yaml` | executor | Active |
| `finance_monthly_review.yaml` | executor | Active |
| `agent_tiers.yaml` | ai_bridge | Active |
| `build_error_resolver.yaml` | ai_bridge | Active |

### Final Command Cheat Sheet

After consolidation, the full command set organized by usage:

```
Daily (10):    /nightly /sync /review /build /check /swarm /learn /merge /deploy /debug
ADR (3):       /write-adr /implement /harden
Quality (4):   /coverage /ops-perf /tidy /autofix
Context (5):   /start /focus /reload /context-audit /context-save
Ops (6):       /audit /cleanup /kill /self-heal /offloads /inspect
Agent (3):     /chain /dispatch-subagent /swarm
Other (3):     /fix /import /client-test /commands
Hidden (8):    /_bridge-update /_git-rules /_gitignore /_task-guide /_memory-sync /_onboarding /_retrospective /_clarify
               Total: 42 (from 48)
```

## Consequences

### Positive
- 6 fewer commands, 17 fewer chains (~2,077 lines removed)
- Cleaner naming: drop `ops-` prefix, keep full readable words
- Performance integrated into nightly CI
- Only 13 renames — minimal disruption, all obvious

### Negative
- Some muscle memory disrupted (e.g., `/ops-sync` → `/sync`, `/ops-kill` → `/kill`)
- Cross-references in docs/memory need updating
- `sync_agents.py` alias mapping needs update for 13 commands

### Neutral
- Underscore aliases auto-generated by sync (e.g., `/ctx_audit` = `/ctx-audit`)
- Hidden commands shortened but remain hidden

## Implementation Order

```
Phase 1: Delete dead weight
├── Step 1.1: Delete 3 source workflow files + kill-exocortex symlink
├── Step 1.2: Delete 17 chain YAML files
└── Step 1.3: Run sync_agents.py to regenerate commands

Phase 2: Rename aliases (parallel)
├── Step 2.1: Update alias: field in all 40 workflow source files
├── Step 2.2: Update alias references in skill SKILL.md files
├── Step 2.3: Update CLAUDE.md map command list
└── Step 2.4: Update agent-topics/WORKFLOWS.md command references

Phase 3: Integrate perf into nightly
├── Step 3.1: Add perf check phase to nightly.md
└── Step 3.2: Verify nightly runs with perf step

Phase 4: Regenerate & verify
├── Step 4.1: Run sync_agents.py --all
├── Step 4.2: Verify all commands resolve
├── Step 4.3: Run /nightly to confirm CI still works
└── Step 4.4: Update docs/generated/ indexes
```

## Alternatives Considered

### Alternative 1: Full prefix system (`ci-*`, `dev-*`, `ops-*` for everything)
Rejected: Makes daily commands longer (`/dev-build` vs `/build`). Top-10 commands should be prefix-free.

### Alternative 2: Only delete, don't rename
Rejected: Inconsistent naming is a usability tax. Renaming now prevents accumulating more inconsistency.

## References

- ADR-096: Progressive disclosure agent instructions
- ADR-053: Slash command compaction
- Usage analysis from git log, runtime logs (2026-01-20 to 2026-02-13)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-097: Command Consolidation & Naming**.

Read the full ADR: `docs/decisions/ADR-097-command-consolidation.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict accordingly
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

1. **Create team**: `TeamCreate(team_name="adr-097-cmd-consolidation", description="Implementing ADR-097: Command Consolidation & Naming")`
2. **Create tasks** per step, with blocking dependencies
3. **Spawn teammates**: developer (medium) for file edits, devops (medium) for sync/CI
4. After all phases, validator verifies

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-097-cmd-consolidation`

#### Phase 1: Delete Dead Weight
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Delete 3 workflow source files: `plugins/ai/skills/ai_bridge/augur/agent-workflows/documentation-sync.md`, `tech-debt-triage.md`, `rollback-recovery.md`. Delete `.claude/commands/kill-exocortex.md` symlink. | 4 files |
| 1.2 | developer | low | Delete 17 chain YAML files (see ADR section 2 for full list): bug_workflow, feature_development, dashboard_hardening, generate_delight, redesign_page, ui_quality_audit, all 6 mcp-app-factory chains, code_review, plugin_batch_verification, plugin_verification, qa_pipeline, knowledge_capture | 17 files |
| 1.3 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` to regenerate `.claude/commands/`. Verify deleted commands no longer appear. | sync output |

#### Phase 2: Rename Aliases
**Strategy**: PARALLEL (2.1-2.2), then PIPELINE (2.3-2.4)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update `alias:` field in workflow source files for the 13 renamed commands per the ADR rename table. Key renames: `ops-sync`→`sync`, `ops-audit`→`audit`, `ops-cleanup`→`cleanup`, `ops-kill`→`kill`, `ops-self-heal-test`→`self-heal`, `review-offloads`→`offloads`, `implement-adr`→`implement`, `_ai-bridge-update`→`_bridge-update`, `_git-guidelines`→`_git-rules`, `_gitignore-inspect`→`_gitignore`, `_guide-task-lifecycle`→`_task-guide`, `_thread-hardening`→`_clarify`. Also rename skill alias: `auto-fix`→`autofix`. | `plugins/ai/skills/ai_bridge/augur/agent-workflows/*.md`, skill SKILL.md files |
| 2.2 | developer | low | Update command references in `plugins/ai/skills/ai_bridge/augur/agent-topics/WORKFLOWS.md` and `plugins/ai/skills/ai_bridge/augur/agent-rules.md` to use new aliases | `agent-topics/WORKFLOWS.md`, `agent-rules.md` |
| 2.3 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --all` to regenerate all commands with new aliases | sync output |
| 2.4 | devops | low | Run generation scripts to update `docs/generated/` indexes | `docs/generated/*.md` |

#### Phase 3: Integrate Perf into Nightly
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add perf check phase to `plugins/ai/skills/ai_bridge/augur/agent-workflows/nightly.md` — add a step that runs the performance profiling checks from `performance-profiling.md` as part of the nightly hardening cycle | `nightly.md` |

#### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Verify `.claude/commands/` has exactly 42 commands (35 visible + 8 hidden - 1 meta = 42 files). List them and confirm names match ADR rename table. |
| V.2 | validator | low | Verify 17 deleted chain files no longer exist |
| V.3 | validator | low | Verify 3 deleted workflow source files no longer exist |
| V.4 | validator | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --check` to verify sync is clean |

### Completion Criteria
- [ ] 3 dead commands deleted
- [ ] 17 dead chains deleted
- [ ] All aliases renamed per table
- [ ] `/nightly` includes perf check
- [ ] `sync_agents.py --all` runs clean
- [ ] Command count: 42 files in `.claude/commands/`
- [ ] ADR status updated to "Implemented"

### How to Run
```
/implement docs/decisions/ADR-097-command-consolidation.md
```
