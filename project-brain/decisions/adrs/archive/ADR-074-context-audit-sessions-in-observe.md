---
status: Implemented
date: '2026-02-11'
deciders:
- Gur Sannikov
related:
- ADR-062 (Observability Hub)
- ADR-028 (Two-Layer Memory)
hub: null
tags:
- context
- audit
- sessions
- observability
- hub
superseded_by: null
---

# ADR-074: Context Audit Sessions in Observability Hub

## Context

Two session-level diagnostics exist but their output is ephemeral:

1. **`/context-audit`** — produces agent budget tables, file loading patterns, risk assessments, and execution mode recommendations. Output exists only in the active CLI session. No persistence, no historical view.

2. **`/context-clean`** — creates session checkpoints (completed tasks, modified files, pending work, active decisions) and recommends cleanup. The checkpoint is written to the daily memory log as prose and printed to chat for manual copy-paste. There is no structured persistence — if the user doesn't copy it, it's gone.

Additional problems:

3. **Naming mismatch** — `/context-clean` is named after its cleanup advice, but its primary value is *saving* session state. The name "clean" implies destruction; the action is preservation. Users looking for a save command won't find it.
4. **No recovery path** — neither command produces a recoverable file. A user who ran `/context-audit` or `/context-clean` yesterday cannot point a new session at the results.
5. **Observe hub gap** — ADR-062 built 7 tabs (Overview, Health, Logs, MCP, Agents, Memory, Markers) but none surfaces session-level diagnostics.

Users need to:
- Save session state to a recoverable file with a clearly-named command
- See past context audits and session checkpoints in the dashboard
- Copy a CLI recovery command to resume from any saved snapshot
- Track context budget trends over time

## Decision

### 1. Rename `/context-clean` → `/context-save`

The command's primary value is saving session state, not cleaning. Rename to match intent:

- Rename file: `plugins/ai/ai_bridge/agent-workflows/context-clean.md` → `context-save.md`
- Update all references in: `CLAUDE.md`, `agent-rules.md`, `MEMORY.md`, IDE adapter configs (`.cursor/`, `.antigravity/`, etc.)
- `sync_agents.py` will propagate the rename to all 8 IDE adapters automatically

The workflow content stays the same (check usage, create checkpoint, recommend action) — only the name changes.

### 2. Meaningful File Names

Saved files use the pattern `{date}-{slug}.json` where the slug is derived from the session's primary activity. This makes files scannable at a glance:

```
data/runtime/session-checkpoints/
├── 2026-02-11-adr071-build-stabilization.json
├── 2026-02-11-fix-chain-cascade.json
└── 2026-02-10-career-hardening.json

data/runtime/context-audits/
├── 2026-02-11-full-pre-swarm.json
├── 2026-02-11-developer-only.json
└── 2026-02-10-full-nightly.json
```

**Slug derivation rules** (agent picks the first that applies):

| Priority | Source | Example slug |
|----------|--------|-------------|
| 1 | User provides label: `/context-save "adr-071 build stabilization"` | `adr071-build-stabilization` |
| 2 | Active ADR in session (from modified files or active decisions) | `adr071-build-stabilization` |
| 3 | Most-modified directory (e.g., `plugins/career/skills/career/`) | `career-hardening` |
| 4 | First completed task summary, slugified | `fix-chain-cascade` |
| 5 | Fallback | `session` |

For audits, the slug combines scope + optional user label:
- `/context-audit` → `full`
- `/context-audit developer` → `developer-only`
- `/context-audit "pre-swarm check"` → `full-pre-swarm`

Slugs are lowercased, spaces replaced with hyphens, max 40 chars, stripped of special characters.

### 3. Persist Session Checkpoints as JSON

Modify the renamed `/context-save` workflow to save a structured JSON file to `data/runtime/session-checkpoints/`:

**File format**:
```json
{
  "id": "2026-02-11-adr071-build-stabilization",
  "type": "checkpoint",
  "timestamp": "2026-02-11T14:30:00Z",
  "label": "ADR-071 build stabilization",
  "token_usage_estimate": 145000,
  "token_limit": 200000,
  "usage_percent": 72.5,
  "completed": [
    "Added auth middleware to /api/* routes (src/middleware.ts)",
    "Created login flow tests (tests/auth/login.test.ts)"
  ],
  "modified_files": [
    "src/middleware.ts",
    "tests/auth/login.test.ts"
  ],
  "pending_tasks": [
    "Wire auth into API routes",
    "Add error handling for expired tokens"
  ],
  "active_decisions": [
    "Using JWT with 15-minute expiry (ADR-012)",
    "Auth middleware runs before all /api/* routes"
  ],
  "summary": "Session at 72.5% — auth middleware implemented, 2 tasks remaining."
}
```

**Actions**:
- Rename + modify: `plugins/ai/ai_bridge/agent-workflows/context-clean.md` → `context-save.md` — add new Step 4: persist JSON to `data/runtime/session-checkpoints/`
- The existing daily log append (now Step 5) stays as-is

### 4. Persist Context Audit Results

Modify the `/context-audit` workflow to save results as JSON files in `data/runtime/context-audits/`:

**File format**:
```json
{
  "id": "2026-02-11-full-pre-swarm",
  "type": "audit",
  "timestamp": "2026-02-11T14:30:00Z",
  "label": "pre-swarm check",
  "scope": "full",
  "agent_filter": null,
  "token_usage_estimate": 145000,
  "token_limit": 200000,
  "usage_percent": 72.5,
  "agents": [
    {
      "name": "developer",
      "type": "executor",
      "profile_lines": 120,
      "max_files": 50,
      "load_pattern": "scoped",
      "risk": "medium",
      "recommended_mode": "team_member"
    }
  ],
  "optimizations": [
    "Tighten analyst glob from **/*.py to src/analysis/*.py",
    "Downgrade security agent to haiku for advisory tasks"
  ],
  "summary": "8 agents audited. 2 high-risk, 4 medium, 2 low. Estimated 145K/200K tokens (72.5%)."
}
```

**Actions**:
- Modify: `plugins/ai/ai_bridge/agent-workflows/context-audit.md` — add Step 7: persist results to `data/runtime/context-audits/`

### 5. Python Script to List Sessions

Create `plugins/observability/skills/observe/scripts/list_sessions.py` — reads **both** `data/runtime/context-audits/` and `data/runtime/session-checkpoints/`, returns a unified JSON array sorted by timestamp (newest first). Each entry has a `type` field (`"audit"` or `"checkpoint"`). Supports `--limit N` and `--type audit|checkpoint` flags.

### 6. API Route

Create `src/dashboard/app/api/observe/sessions/route.ts`:
- `GET` → calls `list_sessions.py` → returns unified list
- Query params: `?limit=20`, `?type=audit|checkpoint`

### 7. New "Sessions" Tab in Observe Hub

Add a `sessions` tab to the observe dashboard displaying both checkpoints and audits in one timeline:

**Checkpoint rows**:

| Column | Source |
|--------|--------|
| Date | `timestamp` |
| Type | Badge: "Checkpoint" |
| Usage | `usage_percent`% bar |
| Tasks | `completed` count done / `pending_tasks` count remaining |
| Recovery | Copy button |

**Audit rows**:

| Column | Source |
|--------|--------|
| Date | `timestamp` |
| Type | Badge: "Audit" |
| Usage | `usage_percent`% bar |
| Scope | `scope` (full / agent name) |
| Recovery | Copy button |

Each row has a **"Copy Recovery Command"** button that copies to clipboard:

```
Resume session from checkpoint: data/runtime/session-checkpoints/2026-02-11-adr071-build-stabilization.json
```
or
```
Recover context audit from file: data/runtime/context-audits/2026-02-11-full-pre-swarm.json
```

The user pastes this into Claude Code, and the agent reads the JSON to restore context.

**Actions**:
- Create: `plugins/observability/skills/observe/augur/tabs/SessionsTab.tsx`
- Modify: `plugins/observability/skills/observe/augur.yaml` — add sessions tab
- Create: `src/dashboard/app/api/observe/sessions/route.ts`
- Create: `plugins/observability/skills/observe/scripts/list_sessions.py`

### 8. Overview Tab Update

Add a "Sessions" link card to the Overview tab grid, showing count of recent sessions.

**Actions**:
- Modify: `plugins/observability/skills/observe/augur/tabs/OverviewTab.tsx` — add GlassLinkCard for sessions

## Consequences

### Positive

- `/context-save` name matches user intent — "save my session" not "clean my context"
- Both audits and checkpoints become persistent and browsable — no more lost diagnostics
- One-click CLI recovery path lowers friction for resuming from any saved snapshot
- Unified Sessions tab shows the full session history timeline (audits + checkpoints)
- Trend visibility: comparing audits over time reveals budget drift
- Fits naturally into the existing observe hub (ADR-062)

### Negative

- `data/runtime/context-audits/` and `data/runtime/session-checkpoints/` accumulate files — needs periodic cleanup (existing `cleanup_temp_files.py` can handle this)
- Rename requires updating references across multiple IDE adapter configs (automated via `sync_agents.py`)
- Both workflows become slightly longer (extra save step each)

### Neutral

- JSON format is runtime-only (gitignored via `data/runtime/`)
- No new Python dependencies required
- Recovery is manual (paste into CLI) — no auto-restore mechanism
- Daily log append in `/context-save` stays as-is (feeds memory pipeline)

## Implementation Order

```
Phase 1: Rename /context-clean → /context-save
├── Step 1: Rename workflow file + update content
├── Step 2: Update all references (CLAUDE.md, agent-rules.md, IDE configs)
└── Step 3: Run sync_agents.py to propagate

Phase 2: Persistence Layer (depends on Phase 1)
├── Step 4: Create list_sessions.py script
├── Step 5: Update /context-save workflow to persist JSON (meaningful slug names)
├── Step 6: Update /context-audit workflow to persist JSON (meaningful slug names)
└── Step 7: Create API route for listing sessions

Phase 3: Dashboard UI (depends on Phase 2)
├── Step 8: Create SessionsTab.tsx component
├── Step 9: Add sessions tab to dashboard.yaml
└── Step 10: Update OverviewTab.tsx with sessions link card

Phase 4: Verification (depends on Phase 3)
├── Step 11: Build check (npm run build)
└── Step 12: Verify tab renders and API returns data
```

## Alternatives Considered

### Alternative 1: Keep `/context-clean` Name, Add Separate `/context-save`

Split into two commands: `/context-save` (always persist) and `/context-clean` (save + cleanup advice).

Rejected: Two commands for overlapping behavior creates confusion. The cleanup advice is a lightweight addition to the save — not worth a separate command. One command, clear name.

### Alternative 2: Persist Audits in Daily Memory Logs

Store audit output as markdown in `data/memory/daily/YYYY-MM-DD.md`.

Rejected: Daily logs are for curated learnings (ADR-028), not structured diagnostic data. JSON format enables the API route and dashboard rendering. Mixing structured audit data into markdown logs would require complex parsing.

### Alternative 3: Add Audit History to the Existing Agents Tab

Extend `AgentsTabView.tsx` with an "Audit History" section.

Rejected: The agents tab shows live agent status. Past audit snapshots are a different concern (session diagnostics vs. current state). A dedicated tab keeps responsibilities clean and avoids overloading the agents view.

## References

- ADR-062: Observability Hub
- ADR-028: Two-Layer Memory System
- `/context-audit` workflow: `plugins/ai/ai_bridge/agent-workflows/context-audit.md`
- `/context-clean` workflow (to be renamed): `plugins/ai/ai_bridge/agent-workflows/context-clean.md`
- Checkpoint manager: `.github/scripts/checkpoint_manager.py`
- Observe plugin: `plugins/observability/skills/observe/`
- Agent sync script: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-074: Context Audit Sessions in Observability Hub**.

Read the full ADR: `docs/decisions/ADR-074-context-audit-sessions-in-observe.md`

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

1. **Create team**: `TeamCreate(team_name="adr-074-context-audit-sessions", description="Implementing ADR-074: Context Audit Sessions in Observability Hub")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-074-context-audit-sessions", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-074 team.
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

**Team name**: `adr-074-context-audit-sessions`

#### Phase 1: Rename /context-clean → /context-save
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Rename `context-clean.md` → `context-save.md`. Update title from `# /context-clean` to `# /context-save`. Update all internal references. Keep workflow logic identical. | `plugins/ai/ai_bridge/agent-workflows/context-save.md` (new), `plugins/ai/ai_bridge/agent-workflows/context-clean.md` (delete) |
| 1.2 | devops | low | Find and replace all references to `context-clean` → `context-save` across IDE adapter configs and docs. Files: `CLAUDE.md`, `plugins/ai/ai_bridge/agent-rules.md`, `.cursor/workflows/context-clean.md` (rename), `.cursor/memory/augur-memory.md`, `.antigravity/instructions.md`, `.opencode/AGENTS.md`, `.gemini/GEMINI.md`, `.github/copilot-memory.md`, `.github/copilot-instructions.md`, `CODEX.md`, `data/memory/MEMORY.md`. | All files listed |
| 1.3 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py` to propagate rename to all 8 IDE adapters. Verify no stale `context-clean` references remain: `grep -r "context-clean" . --include="*.md" --include="*.yaml" --include="*.json"`. | N/A (verification) |

#### Phase 2: Persistence Layer
**Strategy**: PIPELINE
**Blocked by**: Phase 1 completion

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `list_sessions.py` — read both `data/runtime/context-audits/` and `data/runtime/session-checkpoints/`, return unified JSON array sorted by timestamp (newest first). Each entry has a `type` field (`"audit"` or `"checkpoint"`). Support `--limit N`, `--type audit\|checkpoint`, and `--json` flags. Reference `scan_code_markers.py` for pattern. | `plugins/observability/skills/observe/scripts/list_sessions.py` |
| 2.2 | developer | low | Update `/context-save` workflow: add new Step 4 between checkpoint creation and daily log append. Step 4: derive a meaningful slug from session context (see Section 2 slug derivation rules in ADR), write JSON to `data/runtime/session-checkpoints/{date}-{slug}.json`. Support optional user label: `/context-save "my label"`. Ensure directory is created if missing. Renumber subsequent steps. | `plugins/ai/ai_bridge/agent-workflows/context-save.md` |
| 2.3 | developer | low | Update `/context-audit` workflow: add Step 7 after producing the audit table. Derive slug from scope + optional user label (see Section 2 slug rules in ADR). Write JSON to `data/runtime/context-audits/{date}-{slug}.json`. Ensure directory is created if missing. | `plugins/ai/ai_bridge/agent-workflows/context-audit.md` |
| 2.4 | developer | medium | Create API route `GET /api/observe/sessions` that calls `list_sessions.py` via `runPythonScript`. Support `?limit=20` and `?type=audit\|checkpoint` query params. Reference `src/dashboard/app/api/markers/summary/route.ts` for pattern. | `src/dashboard/app/api/observe/sessions/route.ts` |

#### Phase 3: Dashboard UI
**Strategy**: PARALLEL (no deps between 3.1, 3.2, 3.3)
**Blocked by**: Phase 2 completion

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Create `SessionsTab.tsx` — fetch from `/api/observe/sessions`, render unified timeline table. Show type badge (Checkpoint/Audit), date, usage % bar, summary, and Copy Recovery Command button. Use `navigator.clipboard.writeText()` for copy. Follow GlassCard pattern from `AgentsTabView.tsx`. Include loading/error/empty states. Copy text format: `Resume session from checkpoint: {filepath}` for checkpoints, `Recover context audit from file: {filepath}` for audits. | `plugins/observability/skills/observe/augur/tabs/SessionsTab.tsx` |
| 3.2 | developer | low | Add sessions tab to `dashboard.yaml` — id: sessions, label: Sessions, icon: History, href: /observe?tab=sessions. Place after markers tab. | `plugins/observability/skills/observe/augur.yaml` |
| 3.3 | developer | low | Update `OverviewTab.tsx` — add a `GlassLinkCard` for Sessions (icon: History, color: indigo, href: /observe?tab=sessions, subtitle: "Session checkpoints & audits"). | `plugins/observability/skills/observe/augur/tabs/OverviewTab.tsx` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Blocked by**: Phase 3 completion

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run `npm run build` in `src/dashboard/` — verify no TypeScript or build errors |
| 4.2 | validator | low | Run `npm run mount-plugins` and verify SessionsTab.tsx is mounted to `src/dashboard/app/observe/tabs/` |
| 4.3 | validator | low | Verify no stale `context-clean` references remain: `grep -r "context-clean" . --include="*.md" --include="*.yaml" --include="*.json"` should return 0 matches (excluding git history and ADR-074 Alternatives section) |
| 4.4 | architect | low | Verify ADR-074 intent matches implementation — sessions tab exists with both checkpoint and audit rows, copy buttons produce correct CLI commands, API returns unified list |

### Completion Criteria
- [ ] `/context-clean` renamed to `/context-save` across all IDE adapters
- [ ] `/context-save` persists JSON to `data/runtime/session-checkpoints/`
- [ ] `/context-audit` persists JSON to `data/runtime/context-audits/`
- [ ] `GET /api/observe/sessions` returns unified audit + checkpoint list
- [ ] Sessions tab renders at `/observe?tab=sessions` with both types
- [ ] Saved files use meaningful names (`2026-02-11-adr071-build-stabilization.json`, not timestamps)
- [ ] Copy button copies correct recovery command per type
- [ ] Overview tab shows Sessions link card
- [ ] `npm run build` passes
- [ ] No stale `context-clean` references
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-074-context-audit-sessions-in-observe.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
