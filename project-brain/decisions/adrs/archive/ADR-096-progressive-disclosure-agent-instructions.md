---
status: Implemented
date: '2026-02-13'
deciders:
- Gur Sannikov
related:
- ADR-052 (debugging efficiency)
- ADR-053 (slash commands)
- ADR-057 (memory sync)
- ADR-059 (MCP context focus)
hub: null
tags:
- progressive
- disclosure
- agent
- instructions
superseded_by: null
---

# ADR-096: Progressive Disclosure Agent Instructions

## Context

The current `CLAUDE.md` is **865 lines**. The canonical source `agent-rules.md` is **777 lines**. Both are loaded into every agent session as system prompt preamble — ~1,642 lines of context before the agent reads a single user message.

This is the "1,000-page manual" anti-pattern. Research from OpenAI's internal agent-driven team (1M LOC, zero human-written) found that large monolithic instruction files backfire: the AI can't distinguish what matters for a given task. Their fix: a ~100-line entry file acting as a **table of contents** with pointers to topic-specific docs loaded on demand. Progressive disclosure.

### Current problems

| Problem | Evidence |
|---------|----------|
| CLAUDE.md is a manual, not a map | 865 lines — everything from git protocol to UI anti-patterns |
| Context budget wasted on irrelevant rules | Agent doing Python work loads 50+ lines of Dashboard UI guidelines |
| No exec-plans directory | ADRs mix architectural decisions with execution tracking |
| No auto-generated indexes | Skill registry, route map, chain list all require manual context loading |
| No auto-fix for low-risk drift | `scan_code_markers.py` detects but doesn't fix TODO_CLEANUP/TODO_OUTDATED |
| Reference docs buried in plugin tree | `plugins/dev/skills/frontend/references/` not discoverable |

### Measurement baseline

| Metric | Current | Target |
|--------|---------|--------|
| CLAUDE.md lines | 865 | ~100 |
| agent-rules.md lines | 777 | ~100 (map) + 8 topic docs (~150 each) |
| Tokens in system prompt from instructions | ~4,000 | ~800 |
| Topic docs loaded per session (avg) | 1 (all-or-nothing) | 1-2 (on demand) |

## Decision

### 1. Split agent-rules.md into map + topic docs

Restructure the 777-line monolith into:

**Map file** (`agent-rules.md`, ~100 lines):
- Project identity (5 lines)
- Directory layout (15 lines)
- Critical rules — only rules that apply to EVERY session (20 lines)
- Topic index table pointing to deeper docs (30 lines)
- Available skills table (20 lines)
- Slash command summary (10 lines)

**Topic docs** (`plugins/ai/skills/ai_bridge/augur/agent-topics/`):

| File | Content (from current agent-rules.md sections) | When loaded |
|------|-----------------------------------------------|-------------|
| `ARCHITECTURE.md` | Monorepo structure, path resolution, plugin mounting, data separation | Agent touches file structure |
| `CODING.md` | Python/TS style, commit conventions, anti-patterns, no-workarounds policy | Agent writes code |
| `DASHBOARD.md` | Next.js patterns, shadcn/ui, hub rules, UI guidelines, plugin mounting | Agent touches dashboard |
| `WORKFLOWS.md` | Chains, nightly, CI, slash commands, running chains | Agent runs workflows |
| `SKILLS.md` | Skill table, creating/modifying skills, SKILL.md format, dependency management | Agent works on a skill |
| `DEBUGGING.md` | ADR-052 visibility stack, Chrome MCP, error detection protocol, background servers | Agent debugs issues |
| `CONTEXT.md` | MCP tools, context management, token budgets, agent teams discipline | Agent manages context or teams |
| `AGENTS.md` | Agent tiering, team protocol, git commit rules for teams, offloading | Agent works in a team |

**How progressive disclosure works:**

```
Session start:
  → CLAUDE.md loaded (~100 lines, the map)
  → Agent sees topic index table

User asks "fix the career dashboard page":
  → Agent reads DASHBOARD.md (dashboard rules)
  → Agent reads DEBUGGING.md (if errors found)
  → Other 6 topic docs never loaded — context saved
```

**Action**:
- Create `plugins/ai/skills/ai_bridge/augur/agent-topics/` directory
- Extract sections from `agent-rules.md` into 8 topic files
- Rewrite `agent-rules.md` as ~100-line map with topic index
- Update `sync_agents.py` to sync topic docs alongside rules
- Update `CLAUDE.md` generation to use the compact map

### 2. Add exec-plans directory

Create `docs/exec-plans/` for tracking in-progress and completed work plans:

```
docs/exec-plans/
├── active/          # Currently being implemented
│   └── .gitkeep
├── completed/       # Done, kept for reference
│   └── .gitkeep
└── README.md        # What goes here vs. ADRs
```

**Separation of concerns:**
- `docs/decisions/` = **Why** we decided (architectural reasoning, alternatives, consequences)
- `docs/exec-plans/` = **How** we're doing it (phased plan, agent assignments, progress)

ADR Implementation Prompt sections will be extracted to `docs/exec-plans/active/ADR-NNN-plan.md` when execution begins, and moved to `completed/` when done. This keeps ADRs clean as decision records.

**Action**:
- Create `docs/exec-plans/active/` and `docs/exec-plans/completed/`
- Add `docs/exec-plans/README.md`
- Update `/implement-adr` skill to extract plan to exec-plans

### 3. Add generated indexes directory

Create `docs/generated/` for auto-generated reference artifacts:

```
docs/generated/
├── skill-registry.md    # All skills with paths, descriptions, status
├── route-map.md         # All dashboard routes → source files
├── chain-index.md       # All chains with descriptions
├── marker-report.md     # Latest scan_code_markers output
└── README.md
```

These are regenerated by CI/nightly — never hand-edited. Agents can `Read` them for quick orientation without scanning the filesystem.

**Action**:
- Create `docs/generated/` with README
- Add generation scripts to nightly workflow
- Add `docs/generated/*.md` to `.gitignore` (runtime artifacts, not source)

### 4. Build auto-fix chain for low-risk drift

Create a `/auto-fix` chain that:
1. Runs `scan_code_markers.py --json` to get machine-readable marker list
2. Filters for low-risk categories: `TODO_CLEANUP`, `TODO_OUTDATED`
3. Dispatches haiku-tier agents to fix each marker
4. Runs tests to verify no regressions
5. Commits fixes with `chore(cleanup): auto-fix N markers`

**Scope guard**: Only `TODO_CLEANUP` (dead code, unused imports) and `TODO_OUTDATED` (stale comments/docs). Never auto-fixes `TODO_BUG`, `TODO_SECURITY`, `TODO_WORKAROUND` — those require human judgment.

**Action**:
- Add `--json` output mode to `scan_code_markers.py`
- Create chain YAML in `plugins/dev/skills/developer/chains/auto-fix-markers.yaml`
- Add `/auto-fix` slash command

### 5. Surface reference docs

Move reference docs from buried plugin paths to a discoverable location:

```
docs/references/
├── design-standards.md          # From plugins/dev/skills/frontend/references/
├── agents-page-design-pattern.md
└── README.md
```

Keep plugin `references/` as canonical source. `docs/references/` gets symlinks or copies via sync. This way agents find references without knowing the plugin tree.

**Action**:
- Create `docs/references/` directory
- Add sync step to `sync_agents.py` or nightly workflow
- Update CLAUDE.md map to point to `docs/references/`

## Consequences

### Positive

- **4x reduction in always-loaded context** (865 → ~100 lines in CLAUDE.md)
- **Progressive disclosure** — agents load only relevant topic docs per task
- **Cleaner ADRs** — decisions separate from execution tracking
- **Auto-generated indexes** — agents orient faster without filesystem scanning
- **Automated cleanup** — low-risk markers fixed without Friday manual labor
- **Discoverable references** — agents find design standards without knowing plugin tree
- **Aligned with industry best practice** — matches OpenAI's proven agent-first patterns

### Negative

- **Migration effort** — splitting 777-line file into 8 + rewriting sync pipeline
- **Agents must learn to drill in** — if map doesn't hint clearly, agent might miss loading a needed topic doc
- **More files to maintain** — 8 topic docs vs. 1 monolith (mitigated: each doc is focused and self-contained)

### Neutral

- Existing ADRs stay as-is — no retroactive changes
- `sync_agents.py` still generates CLAUDE.md — just from a smaller source
- Nightly workflow gets 3 new steps (generate indexes, sync references, auto-fix)

## Implementation Order

```
Phase 1: Topic docs + map (core change)
├── Step 1.1: Create agent-topics/ directory with 8 topic files
├── Step 1.2: Rewrite agent-rules.md as ~100-line map
├── Step 1.3: Update sync_agents.py to handle topic docs
└── Step 1.4: Verify CLAUDE.md generation produces compact output

Phase 2: Docs structure (parallel with Phase 1)
├── Step 2.1: Create docs/exec-plans/ with README
├── Step 2.2: Create docs/generated/ with README
├── Step 2.3: Create docs/references/ with README + symlinks
└── Step 2.4: Update .gitignore for docs/generated/

Phase 3: Automation (depends on Phase 1, 2)
├── Step 3.1: Add --json mode to scan_code_markers.py
├── Step 3.2: Create auto-fix chain YAML
├── Step 3.3: Add generation scripts for docs/generated/ indexes
├── Step 3.4: Add /auto-fix slash command
└── Step 3.5: Wire new generation steps into nightly workflow

Phase 4: Verification (depends on Phase 1, 2, 3)
├── Step 4.1: Run full test suite
├── Step 4.2: Verify CLAUDE.md < 120 lines
├── Step 4.3: Verify topic docs load correctly on demand
└── Step 4.4: Run nightly workflow end-to-end
```

## Alternatives Considered

### Alternative 1: Keep monolith, add @include directives

Add preprocessing to agent-rules.md that collapses sections behind `@include` markers that agents can expand. Rejected because: Claude Code doesn't support include directives natively — we'd need a custom preprocessor, and the content would still be loaded if the preprocessor runs at build time. Doesn't achieve progressive disclosure.

### Alternative 2: Use MCP tool for context injection

Build an MCP tool `get-agent-rules(topic)` that returns topic-specific rules on demand. Rejected because: adds MCP overhead, requires the agent to know to call the tool before starting work, and creates a dependency on MCP server being running. File-based progressive disclosure (`Read` a doc when needed) is simpler and works everywhere.

### Alternative 3: No change — rely on MCP context focus (ADR-059)

ADR-059 already scopes MCP tools per page. Could extend it to scope agent rules too. Rejected as insufficient: ADR-059 filters tools, not instruction content. The 865-line CLAUDE.md is still loaded regardless of which tools are active.

## References

- OpenAI internal team patterns (agent-first development, 1M LOC)
- ADR-052: Debugging efficiency — full-stack vision
- ADR-053: Slash command compaction
- ADR-057: Memory sync
- ADR-059: MCP context focus & skill-aware tool scoping
- `plugins/ai/skills/ai_bridge/augur/agent-rules.md` (canonical source)
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` (generation pipeline)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-096: Progressive Disclosure Agent Instructions**.

Read the full ADR: `docs/decisions/ADR-096-progressive-disclosure-agent-instructions.md`

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
4. Record the verdict:
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-096-progressive-disclosure", description="Implementing ADR-096: Progressive Disclosure Agent Instructions")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-096-progressive-disclosure", name="{role}",
        prompt="You are '{role}' on the adr-096 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: commit your changes, TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-096-progressive-disclosure`

#### Phase 1: Topic Docs + Map
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Extract 8 topic docs from agent-rules.md sections into `plugins/ai/skills/ai_bridge/augur/agent-topics/`. Map sections: Critical Rules → CODING.md + AGENTS.md; Architecture → ARCHITECTURE.md; Code Style → CODING.md; Dashboard UI → DASHBOARD.md; Key Workflows → WORKFLOWS.md; Skills table → SKILLS.md; Debugging → DEBUGGING.md; MCP/Context → CONTEXT.md | `plugins/ai/skills/ai_bridge/augur/agent-rules.md`, `plugins/ai/skills/ai_bridge/augur/agent-topics/*.md` |
| 1.2 | developer | high | Rewrite agent-rules.md as ~100-line map: project identity, directory layout, 5 critical rules (hardcoded paths, data separation, no workarounds, read README, in-code markers), topic index table with file paths, skills table, commands summary | `plugins/ai/skills/ai_bridge/augur/agent-rules.md` |
| 1.3 | devops | medium | Update `sync_agents.py` ClaudeCodeAdapter to: (a) copy topic docs to `docs/agent-topics/` during sync, (b) generate compact CLAUDE.md from new map format, (c) preserve auto-generated header | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |
| 1.4 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py --rules` and verify CLAUDE.md is < 120 lines | `CLAUDE.md` |

#### Phase 2: Docs Structure
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Create `docs/exec-plans/active/.gitkeep`, `docs/exec-plans/completed/.gitkeep`, and `docs/exec-plans/README.md` explaining separation from ADRs | `docs/exec-plans/README.md`, `docs/exec-plans/active/.gitkeep`, `docs/exec-plans/completed/.gitkeep` |
| 2.2 | developer | low | Create `docs/generated/README.md` explaining auto-generated nature, add `docs/generated/*.md` (except README) to `.gitignore` | `docs/generated/README.md`, `.gitignore` |
| 2.3 | developer | low | Create `docs/references/README.md`, symlink or copy `plugins/dev/skills/frontend/references/design-standards.md` and `agents-page-design-pattern.md` | `docs/references/README.md`, `docs/references/design-standards.md`, `docs/references/agents-page-design-pattern.md` |

#### Phase 3: Automation
**Strategy**: PARALLEL (3.1-3.3 parallel, then 3.4-3.5 pipeline)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add `--json` output mode to `scan_code_markers.py` that outputs `[{"marker": "TODO_CLEANUP", "file": "...", "line": N, "text": "..."}]` | `.github/scripts/scan_code_markers.py` |
| 3.2 | devops | medium | Create auto-fix chain YAML at `plugins/dev/skills/developer/chains/auto-fix-markers.yaml` — steps: scan markers (--json), filter TODO_CLEANUP + TODO_OUTDATED, dispatch fix agents, run tests, commit | `plugins/dev/skills/developer/chains/auto-fix-markers.yaml` |
| 3.3 | devops | medium | Create generation scripts for `docs/generated/`: `generate_skill_registry.py` (scan all SKILL.md files → skill-registry.md), `generate_route_map.py` (scan dashboard app/ → route-map.md), `generate_chain_index.py` (scan chains/ → chain-index.md) | `.github/scripts/generate_skill_registry.py`, `.github/scripts/generate_route_map.py`, `.github/scripts/generate_chain_index.py` |
| 3.4 | devops | low | Add `/auto-fix` slash command to `plugins/ai/skills/ai_bridge/augur/skills/` pointing to the chain | `plugins/ai/skills/ai_bridge/augur/skills/auto-fix/` |
| 3.5 | devops | low | Wire generation scripts and auto-fix into nightly workflow (`cron-nightly.yml` or equivalent local nightly chain) | `.github/workflows/cron-nightly.yml` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/src/` — all tests pass |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — clean build |
| V.3 | validator | low | Verify `CLAUDE.md` is < 120 lines and contains topic index table |
| V.4 | validator | low | Verify all 8 topic docs exist and cover all sections from original agent-rules.md |
| V.5 | validator | low | Run `python3 .github/scripts/scan_code_markers.py --json` — valid JSON output |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] CLAUDE.md < 120 lines with topic index table
- [ ] 8 topic docs in `plugins/ai/skills/ai_bridge/augur/agent-topics/`
- [ ] `docs/exec-plans/`, `docs/generated/`, `docs/references/` created with READMEs
- [ ] `scan_code_markers.py --json` produces valid JSON
- [ ] Auto-fix chain YAML exists
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-096-progressive-disclosure-agent-instructions.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
