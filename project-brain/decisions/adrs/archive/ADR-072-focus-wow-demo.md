---
status: Superseded
date: '2026-02-11'
deciders:
- Gur Sannikov
related:
- ADR-059 (MCP Context Focus)
- ADR-030 (Context Merge Algorithm)
- ADR-054 (Offloading)
hub: null
tags:
- cross
- ide
- focus
- synchronization
- one
superseded_by: null
---

# ADR-072: Cross-IDE Focus Synchronization — "One Brain, Every IDE" Demo

**Superseded by**: [ADR-254](ADR-254-agent-discovery-protocol.md)

## Context

ADR-059 built skill-aware context focusing — navigate to `/career` and the MCP narrows tools, injects skill orientation, surfaces actions/chains. It works. But it only works **inside Claude Code + the dashboard**. No other IDE sees the focus.

**The real demo problem**: Augur's pitch is "one AI brain across your entire workflow." Today, a user can open Claude Code, Cursor, Windsurf, Gemini CLI, and the Augur dashboard — but they are islands. Each IDE has the same static rules (via `sync_agents.py`), but none of them know what page the user is looking at in the dashboard. The focus system (ADR-059) is powerful but siloed.

**What the demo should look like**:
1. User opens 3+ IDEs (Claude Code, Cursor, Windsurf) and the Augur dashboard
2. User navigates to `/career` in the dashboard
3. User types "give me focus" (or `/focus`) in **any** IDE or CLI
4. ALL of them return the **same** career-focused response: skill name, data paths, active tools, actions, chains, orientation prompt
5. Audience reaction: "The dashboard is the control plane. Every IDE is a synchronized view of the same brain."

**Current gaps preventing this**:

| Gap | Detail |
|-----|--------|
| **No page broadcast** | Dashboard only writes `chat_session.json` when spawning CLIs (`POST /api/cli`), NOT on regular page navigation |
| **Path mismatch** | Dashboard writes to `data/temp/chat_session.json`, MCP reads from `data/runtime/temp/chat_session.json` |
| **IDE MCP coverage** | Only Claude Code has full MCP configured. Cursor/Windsurf may not have `augur` MCP server in their config |
| **No visual feedback** | After `/focus` returns, there's no rich output — just raw JSON. No structured "you are focused on Career" display |

## Decision

Build **cross-IDE focus synchronization** — the dashboard broadcasts page state on every navigation to a src/lib file, and every IDE reads it via the same `focus-context` MCP tool. The demo becomes: navigate once in the dashboard, ask from anywhere, get the same answer.

### Component 1: Dashboard Page Broadcast

On every page navigation, the dashboard writes focus state to a src/lib file that all MCP server instances can read.

**File**: `data/runtime/focus_state.json`

**Schema**:
```json
{
  "current_page": "/career",
  "skill_name": "career",
  "bundle": "apps",
  "timestamp": "2026-02-11T14:30:00Z",
  "source": "dashboard"
}
```

**Integration**: The `useMCPContext` hook already detects page changes and calls `focusContext()`. After the API call succeeds, it also writes focus state via a new `POST /api/focus-state` endpoint. This endpoint writes the JSON file to `data/runtime/focus_state.json`.

**Why a separate file** (not `chat_session.json`):
- `chat_session.json` is overwritten by CLI spawn logic and carries CLI-specific state
- `focus_state.json` is owned solely by the dashboard navigation — clean separation
- Multiple MCP processes reading one atomic JSON file is safe (read-only for them)

**Actions**:
- Create `src/dashboard/app/api/focus-state/route.ts` — POST endpoint that writes `focus_state.json`
- Modify `src/dashboard/hooks/useMCPContext.ts` — after successful `focusContext()`, POST to `/api/focus-state`
- Modify `src/dashboard/lib/mcp/MCPContextClient.ts` — add `broadcastFocusState()` method

### Component 2: MCP Focus State Reader

The `focus-context` MCP tool already has a fallback that reads `chat_session.json` when no explicit `skill_name` or `page` is provided (context_manager.py lines 1097-1110). Extend this to also read `focus_state.json` — and prioritize it over `chat_session.json` since it reflects the latest dashboard navigation.

**Resolution order** (when `/focus` called with no args):
1. Explicit `skill_name` argument → use directly
2. Explicit `page` argument → resolve via registry
3. `focus_state.json` exists and recent (< 30 min) → use `current_page` from it
4. `chat_session.json` fallback → existing behavior
5. Error: "Navigate to a skill page in the dashboard or specify a skill name"

**Actions**:
- Modify `src/mcp/augur_mcp/context_manager.py` — `focus_on_skill()` reads `focus_state.json` before `chat_session.json`
- Use `get_runtime_dir()` for path resolution (not hardcoded) to avoid path mismatch bug

### Component 3: IDE MCP Configuration Distribution

Ensure all supported IDEs have the `augur` MCP server configured so they can call `focus-context`.

**Current state**:

| IDE | MCP Support | Augur MCP Configured | Status |
|-----|-------------|---------------------|--------|
| Claude Code | Yes (native) | Yes (`.claude/mcp.json`) | Working |
| Cursor | Yes (MCP protocol) | Partial (`.cursor/mcp.json` may exist) | Needs verification |
| Windsurf | Yes (MCP protocol) | Unknown | Needs config |
| Gemini CLI | Limited | No | Skip for demo |
| OpenCode | Yes | Unknown | Needs config |

**Actions**:
- Extend `sync_agents.py` to distribute MCP server config to Cursor (`.cursor/mcp.json`) and Windsurf (`.windsurf/mcp.json`)
- Template: use `src/config/mcp_config.template.json` with IDE-specific adjustments
- Each IDE's MCP config points to the same `src/mcp` server entry point

### Component 4: Rich `/focus` Output Formatting

When `/focus` returns a FocusPayload, the agent should render it as a structured, readable response — not raw JSON. Update the `/focus` workflow to specify the output format.

**Terminal output format**:
```
Focused: career (apps)

Data:    plugins/career/
Tools:   12 active (33 removed)
Actions: career_status, company_research, career_hardening
Chains:  interview_prep

The AI is now oriented on your career skill — job pipeline,
resume, companies, and interview preparation.
```

**Actions**:
- Modify `plugins/ai/ai_bridge/agent-workflows/focus.md` — add explicit output formatting instructions
- The workflow already exists in all IDEs via `sync_agents.py` — just updating the source propagates everywhere

### Component 5: Demo Script

The intended demo sequence (~60 seconds):

```
Setup: Open the Augur dashboard, Claude Code terminal, and Cursor side by side.

1. [DASHBOARD] Navigate to /career
   → Dashboard shows career hub. Under the hood, focus_state.json is written.

2. [CLAUDE CODE] Type: /focus
   → Claude Code calls focus-context MCP tool → reads focus_state.json
   → Prints: "Focused: career (apps) — 12 tools active, 33 removed"
   → "Same brain. It knows I'm on Career because the dashboard told it."

3. [CURSOR] Type: "augur give me focus" (or /focus if cursor workflow supports it)
   → Cursor calls same focus-context MCP tool → reads same focus_state.json
   → Prints identical career focus response
   → "Different IDE. Same answer. One brain."

4. [DASHBOARD] Navigate to /health
   → focus_state.json updates to health

5. [CLAUDE CODE] Type: /focus
   → Now shows health focus — different tools, different data paths
   → "I didn't tell it to switch. The dashboard is the control plane."

6. [CURSOR] Type: /focus
   → Also shows health focus
   → "Every IDE follows the dashboard. Zero configuration per IDE."
```

**Key message**: The dashboard is a visual control plane. Navigate once, focus everywhere. The MCP server is the src/lib brain — every IDE is just a different mouth asking the same brain.

### Architecture: Cross-IDE Event Flow

```
User navigates to /career in Dashboard
        |
        v
useMCPContext.ts detects skill page
        |
        ├──> Calls POST /api/mcp/context/focus (existing)
        |         |
        |         v
        |    ContextManager.focus_on_skill("career")
        |    Returns FocusPayload to dashboard
        |
        └──> Calls POST /api/focus-state (NEW)
                  |
                  v
             Writes data/runtime/focus_state.json
             { current_page: "/career", skill_name: "career", ... }

--- Later, in ANY IDE ---

User types /focus (no args) in Claude Code, Cursor, or Windsurf
        |
        v
Agent calls focus-context MCP tool (no args)
        |
        v
ContextManager.focus_on_skill()
        |
        ├── No skill_name or page provided
        ├── Reads data/runtime/focus_state.json  ← NEW priority
        ├── Finds current_page: "/career"
        ├── Resolves career skill via registry.yaml
        └── Returns FocusPayload (identical to what dashboard received)
```

## Consequences

### Positive

- Focus becomes Augur's signature demo moment — "one brain, every IDE"
- Proves the MCP-as-gateway architecture (ADR-005) works across the entire IDE ecosystem
- Dashboard becomes a **visual control plane**, not just a viewer
- Zero per-IDE configuration needed — `/focus` just works after MCP is configured once
- The demo is live and real — no mocks, no slides, no staged data

### Negative

- Requires MCP server configured in each IDE (one-time setup per IDE)
- `focus_state.json` is a src/lib-file coordination mechanism — simple but not real-time (30s staleness threshold acceptable)
- IDEs without MCP support (e.g., plain vim) cannot participate

### Neutral

- FocusPayload schema unchanged from ADR-059
- No new MCP tools needed — `focus-context` already exists
- `sync_agents.py` already distributes workflows — just adding MCP config distribution

## Implementation Order

```
Phase 1: Shared State (no deps)
├── Step 1: Create POST /api/focus-state endpoint
├── Step 2: Extend focus_on_skill() to read focus_state.json
└── Step 3: Fix path resolution — use get_runtime_dir() consistently

Phase 2: Dashboard Broadcasting (depends on Phase 1)
├── Step 4: Hook useMCPContext to POST focus state after focusContext()
└── Step 5: Add broadcastFocusState() to MCPContextClient

Phase 3: IDE Distribution (depends on Phase 1)
├── Step 6: Add MCP config templates for Cursor and Windsurf
└── Step 7: Extend sync_agents.py to distribute MCP configs

Phase 4: Rich Output (no deps, parallel with Phase 1-3)
└── Step 8: Update /focus workflow with structured output format

Phase 5: Verification
├── Step 9: End-to-end test — navigate in dashboard, /focus in Claude Code
├── Step 10: Verify Cursor receives same FocusPayload
└── Step 11: Build + lint + test pass
```

## Alternatives Considered

### Alternative 1: WebSocket Push (Real-Time)

Dashboard pushes focus changes to all IDEs via WebSocket. Rejected: overkill for demo. File-based is simpler, debuggable (`cat focus_state.json`), and the 0-30s latency is irrelevant when the user explicitly types `/focus`. Real-time would add a WebSocket server, connection management, and reconnect logic.

### Alternative 2: Shared MCP Server Process

Run a single MCP server daemon that all IDEs connect to (TCP/HTTP transport instead of stdio). Rejected: would require changing MCP transport for all IDEs, which is a much larger change. Each IDE spawning its own stdio MCP process that reads the same file achieves the same result with zero infrastructure.

### Alternative 3: Dashboard-Only Demo (No Cross-IDE)

Show the focus animation purely in the dashboard with UI effects (the previous version of this ADR). Rejected: misses the actual differentiating value. Every app has animations. No app synchronizes context across IDE boundaries. The cross-IDE demo is what makes people say "I've never seen that before."

## References

- ADR-059: MCP Context Focus & Skill-Aware Tool Scoping
- ADR-030: Context Merge Algorithm
- ADR-005: MCP as Execution Gateway
- `src/mcp/augur_mcp/context_manager.py` — `focus_on_skill()` (line 1066)
- `src/dashboard/hooks/useMCPContext.ts` — page detection + focus trigger
- `src/dashboard/lib/mcp/MCPContextClient.ts` — `focusContext()` method
- `src/dashboard/app/api/cli/route.ts` — existing `writeChatSession()` pattern
- `plugins/ai/ai_bridge/agent-workflows/focus.md` — `/focus` workflow
- `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` — IDE distribution

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-072: Cross-IDE Focus Synchronization — "One Brain, Every IDE" Demo**.

Read the full ADR: `docs/decisions/ADR-072-focus-wow-demo.md`

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

1. **Create team**: `TeamCreate(team_name="adr-072-cross-ide-focus", description="Implementing ADR-072: Cross-IDE Focus Synchronization")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-072-cross-ide-focus", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-072 team.
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

**Team name**: `adr-072-cross-ide-focus`

#### Phase 1: Shared State Foundation
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | frontend | medium | Create `POST /api/focus-state` endpoint. Reads JSON body `{ current_page, skill_name, bundle }`, writes to `data/runtime/focus_state.json` with added `timestamp` and `source: "dashboard"`. Use `fs.writeFileSync` with atomic write (write to `.tmp` then rename). Create parent dirs if missing. Follow existing pattern from `writeChatSession()` in `src/dashboard/app/api/cli/route.ts`. | `src/dashboard/app/api/focus-state/route.ts` |
| 1.2 | developer | medium | Extend `focus_on_skill()` in `context_manager.py` to read `focus_state.json` as priority fallback. In the "Fallback: try to infer from chat session" block (lines 1097-1110), add a NEW block BEFORE the `chat_session.json` read that: (a) reads `get_runtime_dir() / "focus_state.json"`, (b) checks timestamp is < 30 minutes old, (c) uses `current_page` to resolve skill. Use `get_runtime_dir()` from `src.config.paths` — NOT hardcoded paths. | `src/mcp/augur_mcp/context_manager.py` |
| 1.3 | developer | low | Fix existing path mismatch: `route.ts` writes `chat_session.json` to `path.join(DATA_DIR, 'temp', ...)` but MCP reads from `get_user_data_base() / "runtime" / "temp" / ...`. Verify both resolve to the same absolute path. If they don't, fix `CHAT_SESSION_FILE` in `route.ts` to include `runtime/` in the path, matching `get_runtime_dir()`. Reference: MEMORY.md pattern about hooks and library code using same path resolution. | `src/dashboard/app/api/cli/route.ts` |

#### Phase 2: Dashboard Broadcasting
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Add `broadcastFocusState(page: string, payload: FocusPayload)` method to `MCPContextClient`. It POSTs to `/api/focus-state` with `{ current_page: page, skill_name: payload.skill_name, bundle: payload.bundle }`. Fire-and-forget (don't await, catch errors silently). | `src/dashboard/lib/mcp/MCPContextClient.ts` |
| 2.2 | frontend | medium | In `useMCPContext.ts`, after `contextClient.focusContext(pathname)` succeeds and returns a payload, call `contextClient.broadcastFocusState(pathname, payload)`. Only broadcast for skill pages (not system pages). The `isSystemPage()` check already exists. | `src/dashboard/hooks/useMCPContext.ts` |

#### Phase 3: IDE MCP Distribution
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | medium | Create MCP config templates for Cursor (`.cursor/mcp.json`) and Windsurf (`.windsurf/mcp.json`). Each should configure the `augur` MCP server pointing to `src/mcp` with the same entry point as `.claude/mcp.json`. Use `${AUGUR_ROOT}` style placeholders resolved by sync_agents. Check existing `.claude/mcp.json` for the exact server config to replicate. | `.cursor/mcp.json`, `.windsurf/mcp.json` |
| 3.2 | devops | medium | Extend `sync_agents.py` to distribute MCP config: add `sync_mcp_config()` method to `CursorAdapter` and `WindsurfAdapter`. Read from `src/config/mcp_config.template.json`, resolve placeholders, write to IDE-specific MCP config files. Only sync if template exists. | `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` |

#### Phase 4: Rich Output
**Strategy**: PARALLEL (no deps, can run alongside Phases 1-3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Update `/focus` workflow to specify structured output format. After receiving FocusPayload, the agent should print a clean summary: skill name + bundle, data dir, tool count (active/removed), action names, chain names, and a 1-sentence orientation. NOT raw JSON. Follow the format specified in the ADR's Component 4 section. | `plugins/ai/ai_bridge/agent-workflows/focus.md` |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Run `npm run build` in `src/dashboard/`. Verify no build errors. Run `npm run lint`. |
| 5.2 | validator | low | Verify `focus_state.json` is written on page navigation: check that `useMCPContext.ts` calls `broadcastFocusState` after `focusContext`. Check that `context_manager.py` reads `focus_state.json` before `chat_session.json`. |
| 5.3 | architect | low | Review: no new MCP tools created (reuses `focus-context`), FocusPayload schema unchanged, `focus_state.json` uses `get_runtime_dir()` not hardcoded paths, path mismatch is resolved. |

### Completion Criteria
- [ ] All 5 phases executed
- [ ] Dashboard writes `focus_state.json` on every skill page navigation
- [ ] `focus-context` MCP tool reads `focus_state.json` when no args provided
- [ ] Path mismatch between dashboard and MCP is resolved
- [ ] Cursor and Windsurf have MCP configs pointing to augur server
- [ ] `/focus` workflow produces structured readable output (not raw JSON)
- [ ] `npm run build` passes, no lint errors
- [ ] ADR-072 status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-072-focus-wow-demo.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
