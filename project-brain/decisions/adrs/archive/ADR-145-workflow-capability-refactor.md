---
status: Implemented
date: '2026-02-24'
deciders:
- Augur project team
related:
- ADR-054 (offload gate)
- ADR-098 (unified command sync)
- ADR-101 (worktree isolation)
- ADR-130 (dispatch modes)
hub: null
tags:
- workflow
- capability
- refactor
- claude
- code
superseded_by: null
---

# ADR-145: Workflow Capability Refactor — Claude Code Native Migration + Cross-Agent Parity

## Context

Augur's workflow infrastructure was designed before Claude Code's current feature set matured. Many patterns that required custom implementation now have native equivalents:

- **358 MCP tools** loaded eagerly into every session (~55K tokens) — native Tool Search reduces this by ~85%
- **6 active worktrees** managed by custom registry + scripts — native WorktreeCreate/Remove hooks can handle lifecycle
- **5 custom agents** with minimal frontmatter — missing model routing, skills preloading, persistent memory, scoped hooks
- **117 skills** with zero `context: fork` usage — heavy workflows pollute the main conversation's context window
- **1 of 17 hook lifecycle events** used — SessionStart, PostToolUse, Stop, PreCompact all have high-value use cases
- **Custom swarm orchestration** — native Agent Teams (experimental) provides built-in task dependencies and teammate communication
- **11 IDE adapters** in sync_agents.py with varying feature parity — Cursor/Windsurf/Gemini getting skills support that isn't being synced

The audit identified 14 patterns: 3 MIGRATE, 7 ENHANCE, 2 EXPLORE, 2 SKIP.

## Decision

### Work Package 1: MCP Tool Search (P0 — MIGRATE)

**Goal**: Replace eager MCP tool injection with native lazy loading.

**Changes**:
1. Verify `ENABLE_TOOL_SEARCH` is set to `auto` or `true` in `.claude/settings.json`
2. Remove eager tool injection from `src/mcp/augur_mcp/context_injector.py` — let Tool Search handle on-demand discovery
3. Update `/start` workflow (`plugins/ai/skills/ai_bridge/augur/data/agent-workflows/start.md`) to skip MCP tool enumeration step
4. Ensure all MCP tools have descriptive `description` fields (Tool Search relies on these for matching)

**Est. savings**: ~45K tokens/session
**Est. effort**: S
**Risk**: Rarely-used tools may not surface on first query. Mitigate with better tool descriptions.

### Work Package 2: Worktree Lifecycle Hooks (P0 — MIGRATE)

**Goal**: Wire worktree registry through native hooks instead of manual script invocation.

**Changes**:
1. Add `WorktreeCreate` hook to `.claude/settings.json`:
   ```json
   {
     "hooks": {
       "WorktreeCreate": [{
         "hooks": [{
           "type": "command",
           "command": "python3 scripts/worktree_registry.py register --from-hook"
         }]
       }]
     }
   }
   ```
2. Add `WorktreeRemove` hook that calls cleanup (kill processes on worktree ports, unregister)
3. Add `isolation: worktree` to agents that should get isolated worktrees
4. Simplify `/dev-merge` by removing manual worktree cleanup steps (lines 111-150)
5. Keep `worktree_registry.py` as backend — hooks are the new trigger mechanism

**Files**: `.claude/settings.json`, `scripts/worktree_registry.py` (add `--from-hook` flag), `.claude/agents/*.md`, `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/dev-merge.md`
**Est. effort**: S
**Risk**: Hooks don't fire on session crash. Keep manual cleanup as fallback.

### Work Package 3: Agent Frontmatter Enrichment (P0 — ENHANCE)

**Goal**: Upgrade all 5 custom agents with full frontmatter capabilities.

**Changes per agent**:

| Agent | Add `skills` | Add `memory` | Add `maxTurns` | Add `mcpServers` | Add `hooks` |
|-------|-------------|-------------|----------------|------------------|-------------|
| advisor.md | architecture-patterns, design-standards | project | 30 | context, settings | — |
| developer.md | api-conventions, error-handling | project | 50 | file tools, context | PostToolUse: lint |
| devops.md | ci-cd-patterns | user | 40 | settings, integrations | — |
| frontend.md | ui-components, design-standards | project | 50 | file tools | PostToolUse: lint |
| validator.md | test-patterns | project | 40 | — | PostToolUse: test |

Also update `registry.json` to reflect new capabilities.

**Files**: `.claude/agents/advisor.md`, `developer.md`, `devops.md`, `frontend.md`, `validator.md`, `.claude/agents/registry.json`
**Est. effort**: S
**Risk**: Over-constraining tools or MCP servers may break edge cases. Test each agent after changes.

### Work Package 4: Skills `context: fork` (P1 — ENHANCE)

**Goal**: Add context isolation to heavy audit/test workflows to prevent context pollution.

**Workflows to fork** (don't need conversation history, produce a structured report):
- `/ops-audit` — dependency audit
- `/ops-refactor` — capability migration audit
- `/ops-optimize` — flow performance analysis
- `/test-nightly` — full CI hardening
- `/orch-context-audit` — context usage audit
- `/ops-plugin-lint` — skill template linting

**Workflows to keep unforked** (need conversation context):
- `/start`, `/learn`, `/focus`, `/context-save`, `/dev-merge`, `/dev-debug`

**Implementation**: Create SKILL.md wrappers in `.claude/skills/` with:
```yaml
---
name: ops-audit
description: Audit and update project dependencies
context: fork
agent: general-purpose
---
!`cat plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-audit.md`
```

**Files**: New SKILL.md files in `.claude/skills/` for 6 workflows
**Est. effort**: M
**Risk**: Forked skills have no conversation history. Workflows that reference "the file we just edited" will fail silently.

### Work Package 5: Frontmatter-Scoped Hooks (P1 — ENHANCE)

**Goal**: Move agent-specific hooks from global config to agent frontmatter.

**Changes**:
1. Add PostToolUse lint hook to `developer.md` and `frontend.md`:
   ```yaml
   hooks:
     PostToolUse:
       - matcher: "Edit|Write"
         hooks:
           - type: command
             command: "npx eslint --fix ${toolInput.file_path} 2>/dev/null || true"
   ```
2. Add PostToolUse test hook to `validator.md`
3. Evaluate moving offload gate from global to per-agent (keep global as default, add agent-specific overrides)

**Files**: `.claude/agents/developer.md`, `frontend.md`, `validator.md`
**Est. effort**: S
**Risk**: Hook scoping precedence (global + frontmatter) needs testing.

### Work Package 6: Skills Hot-Reload Documentation (P1 — ENHANCE)

**Goal**: Document that skills in `.claude/skills/` hot-reload on file change.

**Changes**:
1. Add note to `SKILLS.md` topic doc about hot-reload behavior
2. Update skill development workflow in `WORKFLOWS.md`
3. No code changes — feature already works for `.claude/skills/` targets

**Files**: `plugins/ai/skills/ai_bridge/augur/agent-topics/SKILLS.md`, `WORKFLOWS.md`
**Est. effort**: S
**Risk**: None.

### Work Package 7: Hook Lifecycle Expansion (P2 — ENHANCE)

**Goal**: Add high-value hooks beyond the current single PreToolUse offload gate.

**New hooks to add**:
1. `SessionStart` (matcher: `startup`) — auto-run lightweight context loading
2. `PostToolUse` (matcher: `Edit|Write`) — auto-format changed files
3. `PreCompact` — auto-save checkpoint before context compaction
4. `SubagentStop` — log subagent results to `runtime/agent-log.jsonl`

**Implementation**: Add to `.claude/settings.json` hooks section.

**Files**: `.claude/settings.json`, new `scripts/session-start-hook.sh`, `scripts/pre-compact-hook.sh`
**Est. effort**: M
**Risk**: Too many hooks slow every interaction. Start with SessionStart + PreCompact only, measure impact.

### Work Package 8: Agent Teams Migration (P2 — MIGRATE)

**Goal**: Replace custom swarm orchestration with native Agent Teams when it reaches stable.

**Blocked on**: Agent Teams leaving experimental status.

**Pre-work (can start now)**:
1. Enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in a test environment
2. Convert 1 simple 2-agent swarm preset to Agent Teams configuration
3. Compare behavior/reliability with custom swarm
4. Document findings in this ADR (update status)

**Full migration (after stable)**:
1. Convert swarm presets to Team configurations
2. Replace `swarm_bridge.py` dispatch with `TeamCreate` tool
3. Map existing TaskList patterns to native task dependencies
4. Deprecate `/orch-swarm` custom orchestration

**Files**: `.claude/settings.json`, `plugins/ai/skills/ai_bridge/augur/lib/swarm_bridge.py`, `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/orch-swarm.md`
**Est. effort**: L
**Risk**: Experimental — task status can lag, no session resumption, no nested teams. Keep custom swarm as fallback.

### Work Package 9: Headless CI Chains (P2 — ENHANCE)

**Goal**: Enable chain execution from CI/CD via headless mode.

**Changes**:
1. Create `scripts/run-chain.sh` wrapper: `claude -p "execute chain $1" --output-format json`
2. Use `--resume` for multi-step chains that need context persistence
3. Integrate with `/test-nightly` workflow for headless test execution

**Files**: New `scripts/run-chain.sh`, update CI configs
**Est. effort**: M
**Risk**: Headless mode has no PermissionRequest hooks. Ensure chains don't require interactive approval.

### Work Package 10: Agent Persistent Memory (P2 — ENHANCE)

**Goal**: Enable cross-session memory for frequently-used agents.

**Changes**:
1. Add `memory: project` to `developer.md`, `advisor.md`, `frontend.md`, `validator.md`
2. Add `memory: user` to `devops.md` (env patterns span projects)
3. Seed initial `MEMORY.md` per agent from existing curated knowledge in `docs/memory/`
4. Add periodic memory review to `/ops-refactor` workflow

**Files**: `.claude/agents/*.md`, new `~/.claude/agent-memory/*/MEMORY.md` seed files
**Est. effort**: M
**Risk**: Memory drift — agents may accumulate outdated patterns. Mitigate with periodic review.

### Work Package 11: Cross-Agent Parity — Rules Enrichment (P1)

**Goal**: Enrich non-Claude agent rules files with more operational context from `agent-rules.md`.

**Changes**:
1. Update `sync_agents.py` to inject more sections into non-Claude rules files
2. Currently stripping slash command references, ADR status, hub layout, critical rules from non-Claude targets
3. Evaluate which sections are IDE-agnostic and should be shared

**Files**: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`
**Est. effort**: S
**Risk**: Oversized rules files may hit IDE token limits. Test with each IDE.

### Work Package 12: Cross-Agent Parity — Skills Sync (P2)

**Goal**: Populate `.cursor/skills/` and `.windsurf/skills/` with proper SKILL.md files.

**Changes**:
1. Add skill sync pass to `sync_agents.py`
2. Convert Augur SKILL.md to Cursor/Windsurf format (strip Claude-specific frontmatter: `context`, `agent`)
3. Keep universal fields: `name`, `description`, `allowed-tools`

**Files**: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`
**Est. effort**: M
**Risk**: Cursor/Windsurf SKILL.md format may differ from Claude's. Verify against each IDE's docs.

## Parallel Implementation Plan

Work packages can be executed in parallel with these dependency groups:

```
Independent (run in parallel):
  WP1: MCP Tool Search          ← standalone
  WP2: Worktree Hooks           ← standalone
  WP3: Agent Frontmatter        ← standalone (feeds into WP5, WP10)
  WP6: Hot-Reload Docs          ← standalone
  WP11: Rules Enrichment        ← standalone

After WP3 completes:
  WP5: Frontmatter-Scoped Hooks ← needs enriched agent files from WP3
  WP10: Agent Persistent Memory ← needs enriched agent files from WP3

Independent (lower priority):
  WP4: context: fork            ← standalone
  WP7: Hook Lifecycle           ← standalone
  WP9: Headless CI              ← standalone
  WP12: Skills Sync             ← standalone

Blocked:
  WP8: Agent Teams              ← blocked on experimental→stable
```

## Consequences

### Positive
- ~45K tokens/session saved from MCP Tool Search alone
- Agent-specific hooks prevent global side effects
- Context isolation prevents audit workflows from polluting active work
- Worktree lifecycle becomes automatic rather than manual
- Cross-agent parity improves from ~45% average to ~65%

### Negative
- Additional hooks add latency to every tool call (~50-200ms each)
- `context: fork` removes conversation history access — some workflows may need adaptation
- Agent Teams migration carries risk while the feature is experimental
- More frontmatter fields = more maintenance surface per agent

### Neutral
- Custom swarm and native Agent Teams can coexist during transition
- sync_agents.py remains the single source of truth for multi-IDE distribution
- Registry.yaml and native skills system complement each other (no replacement needed)
