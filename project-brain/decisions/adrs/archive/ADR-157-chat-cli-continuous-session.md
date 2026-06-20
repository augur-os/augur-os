---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-104 (embedded CLI)
- ADR-116 (online status + CLI health)
- ADR-124 (focus button)
hub: null
tags:
- chat
- cli
- continuous
- session
superseded_by: null
---

# ADR-157: Chat CLI Continuous Session UX

## Context

The dashboard's floating chat window embeds CLI agents (Claude, Codex, Kimi, etc.) via PTY. In operation mode, users interact with the CLI as their primary AI interface. Five UX gaps degrade this experience:

1. **No auto-context on start**: The CLI opens cold — no project context, no glossary, no awareness of the user's current page. The `/start` command loads full context but is never run automatically.

2. **Untargeted MCP tools**: The "Actions" button fetches tools filtered by page and mode, but applies no ranking. A hub with 40+ MCP tools shows them all equally — the user must scroll and search for the tool they need. No usage history, no recency weighting, no page-affinity scoring.

3. **No asset browser in operation mode**: The Data Browser is hidden in operation mode (`if (isOperationMode) return null`). Users have no way to see relevant files/assets for the current page without switching to dev mode.

4. **No continuous session management**: Each chat window open/close cycle feels disconnected. The CLI runs but the dashboard doesn't orchestrate it — no auto-focus on page navigation, no context save before close, no session continuity commands. The GUI buttons (Focus, Actions, etc.) operate independently rather than composing into a managed session lifecycle.

5. **Excessive debug output**: Claude Code's default output includes tool-use traces, thinking indicators, file diffs, and ANSI formatting that overwhelms operation-mode users who just want answers.

## Decision

### 1. Auto-Context on CLI Start

When the CLI starts in operation mode, automatically inject a `/start`-equivalent context payload before the first user message.

**Implementation**: Modify `handleStartAction` in `src/dashboard/app/api/cli/route.ts` and `startCliProcess` to accept an `autoContext` flag. When set, after the PTY spawns and the CLI is ready (detect via first output), write a startup prompt that includes:
- Project identity (from vision.md summary — cached, not re-read every time)
- Current page context (skill name, available actions)
- Session history summary (last 3 interactions on this page)

**Files**:
- Modify: `src/dashboard/app/api/cli/route.ts` — add `autoContext` to `CliRequestBody`, send startup prompt after spawn
- Modify: `src/dashboard/hooks/useCliChat.ts` — pass `autoContext: true` in operation mode starts
- Modify: `src/dashboard/components/FloatingChat.tsx` — pass through to `startCliWrapped`
- Create: `src/dashboard/lib/chat/startup-context.ts` — build the startup context payload (cached project identity + page context from focus-context MCP tool)

### 2. Smart MCP Tool Ranking

Replace flat tool listing with a scored ranking algorithm. Each tool gets a composite score:

```
score = (page_affinity × 0.4) + (recency × 0.3) + (frequency × 0.2) + (global_popularity × 0.1)
```

- **page_affinity**: Tools whose skill matches the current page score 1.0; same hub scores 0.5; cross-hub scores 0.0
- **recency**: Time-decayed score based on last use (1.0 = used in last hour, 0.5 = today, 0.1 = this week, 0.0 = never)
- **frequency**: Normalized count of uses in the last 30 days
- **global_popularity**: Normalized count across all pages (catches universally useful tools)

Display the top 8 tools prominently, then show "More" for the full list.

**Files**:
- Create: `src/dashboard/lib/chat/tool-ranker.ts` — scoring algorithm + types
- Create: `src/dashboard/app/api/mcp/tools/usage/route.ts` — record tool usage events, return usage stats
- Modify: `src/dashboard/app/api/mcp/tools/list/route.ts` — integrate ranker, return scored + sorted tools
- Modify: `src/dashboard/components/chat/ChatToolbar.tsx` — show top 8 with visual ranking, "More" expander
- Create: `runtime/chat/tool_usage.jsonl` — append-only usage log (gitignored)

### 3. Assets Button for Operation Mode

Add an "Assets" button to the chat toolbar in operation mode that shows the top 10 most relevant files for the current page.

**Relevance scoring**:
- Files modified most recently within the skill's data directory
- Files accessed during previous sessions on this page
- Files matching the skill's key patterns (e.g., `*.yaml` for config skills, `*.md` for content skills)

**Implementation**: The button opens a side popover (same pattern as MCP tools) showing file name, last modified time, and a preview snippet. Clicking a file inserts its path into the chat input.

**Files**:
- Create: `src/dashboard/app/api/assets/relevant/route.ts` — scan skill data dir, score and return top 10 assets
- Modify: `src/dashboard/components/chat/ChatToolbar.tsx` — add Assets button (visible in operation mode), wire to popover
- Create: `src/dashboard/components/chat/AssetsBrowser.tsx` — popover component showing ranked file list with metadata

### 4. Continuous Session Lifecycle

Transform the chat from "open CLI, type, close" into a managed continuous session. The dashboard orchestrates the CLI through lifecycle commands sent transparently:

| Event | Dashboard Action | CLI Command Sent |
|-------|-----------------|-----------------|
| Chat opens | Auto-start + context load | Startup context payload (decision 1) |
| User navigates to new page | Auto-refocus | `/focus` prompt with new page context |
| User idle > 5 min | Save context | `/context-save` prompt |
| Chat closes | Graceful save | `/context-save` + session metadata write |
| Chat reopens (same session) | Resume | Session summary + "Continuing from where we left off" |
| User clicks Focus button | Manual refocus | Current `/focus` behavior (unchanged) |

**Key principle**: The CLI process stays alive across page navigations. Only one CLI runs at a time. Page changes trigger a lightweight refocus, not a restart.

**Files**:
- Create: `src/dashboard/hooks/useSessionLifecycle.ts` — orchestrates lifecycle events (page change detection, idle timer, close handler)
- Modify: `src/dashboard/components/FloatingChat.tsx` — integrate `useSessionLifecycle`, wire page navigation to refocus
- Modify: `src/dashboard/hooks/useCliChat.ts` — add `sendSystemCommand(cmd)` that sends commands without showing them in user chat history
- Modify: `src/dashboard/app/api/cli/route.ts` — add `action: 'system'` that writes to PTY without logging to outputBuffer

### 5. Quiet Mode for Operation Users

Add a `--output-filter` flag equivalent for embedded CLI sessions. Since we control the PTY, filter the raw output before it reaches xterm.js.

**Filter rules for operation mode**:
- Suppress tool-use traces (`⏳ Running...`, `✓ Completed`, file diff blocks)
- Suppress thinking indicators (`Thinking...`, spinner lines)
- Suppress permission prompts (already auto-approved via `--dangerously-skip-permissions`)
- Keep: final answers, errors, and user-facing questions
- Keep: progress indicators for long operations (simplified to single-line status)

**Implementation**: Add a post-processing filter in the SSE stream path. Raw PTY data flows through a `QuietModeFilter` that strips verbose output patterns before encoding to the client.

**Files**:
- Create: `src/dashboard/lib/chat/quiet-filter.ts` — regex-based output filter with configurable verbosity levels (`quiet`, `normal`, `verbose`)
- Modify: `src/dashboard/app/api/cli/route.ts` — apply filter in SSE data handler when `verbosity` param is set
- Modify: `src/dashboard/hooks/useCliChat.ts` — pass `verbosity: 'quiet'` for operation mode, `'normal'` for dev mode
- Modify: `src/dashboard/components/chat/ChatHeader.tsx` — add verbosity toggle (eye icon) in dev mode

## Consequences

### Positive
- Operation mode users get a coherent, context-aware assistant experience without manual setup
- MCP tool discovery becomes practical even with 40+ tools per hub
- Assets are accessible without switching to dev mode
- Page navigation feels seamless — the AI follows the user through the dashboard
- Reduced output noise means users focus on answers, not plumbing

### Negative
- Auto-context adds ~2s latency to CLI startup (mitigated by caching project identity)
- Tool usage tracking adds a new runtime data file to manage
- Quiet mode filter may occasionally suppress useful output (mitigated by toggle)
- Session lifecycle adds complexity to the FloatingChat component (mitigated by extracting to dedicated hook)

### Neutral
- Dev mode is largely unaffected — all new features default to off or less aggressive in dev mode
- Existing `/focus` and `/start` slash commands continue to work as manual overrides
- CLI agent configurations (cli_agents.yaml) don't change

## Implementation Order

```
Phase 1: Quiet Mode Filter (reduces noise, immediate UX improvement)
├── Step 1.1: Create quiet-filter.ts with regex patterns
├── Step 1.2: Integrate filter in SSE stream path
└── Step 1.3: Wire verbosity param from client

Phase 2: Auto-Context on Start (builds on existing /start and focus-context)
├── Step 2.1: Create startup-context.ts with cached project identity
├── Step 2.2: Modify CLI start flow to inject context after spawn
└── Step 2.3: Wire autoContext flag from FloatingChat

Phase 3: Smart Tool Ranking (builds on existing tool list API)
├── Step 3.1: Create tool-ranker.ts scoring algorithm
├── Step 3.2: Create usage tracking API route + storage
├── Step 3.3: Integrate ranker into tools/list API
└── Step 3.4: Update ChatToolbar with ranked display

Phase 4: Assets Button (independent, parallel with Phase 3)
├── Step 4.1: Create relevant assets API route
├── Step 4.2: Create AssetsBrowser component
└── Step 4.3: Add button to ChatToolbar

Phase 5: Continuous Session Lifecycle (depends on Phase 1 + 2)
├── Step 5.1: Create useSessionLifecycle hook
├── Step 5.2: Add system command channel to CLI API
├── Step 5.3: Wire page navigation → refocus
├── Step 5.4: Add idle timer → context save
└── Step 5.5: Add close handler → graceful save

Phase 6: Verification (depends on all)
├── Step 6.1: Verify operation mode startup → context → quiet output
├── Step 6.2: Verify page navigation → auto-refocus
├── Step 6.3: Verify tool ranking reflects usage patterns
└── Step 6.4: Verify assets button shows relevant files
```

## Alternatives Considered

### 1. Separate "Operation Chat" component instead of enhancing FloatingChat

Rejected: Would duplicate 80% of FloatingChat's code. The mode-aware pattern (already used for labels, visibility, auto-start) is the right extension point.

### 2. Server-side output filtering via Claude Code's `--output-style` flag

Rejected: Claude Code's built-in output modes don't map to our needs. We need PTY-level filtering because we control the terminal renderer and can make finer-grained decisions about what operation users see.

### 3. Pre-computed tool rankings via nightly batch job

Rejected: Usage patterns change within a session. Real-time scoring with lightweight JSONL tracking is fast enough and always current.

## References

- ADR-104: Embedded CLI in dashboard
- ADR-116: Online status and CLI health detection
- ADR-124: Focus button and MCP-first API
- `src/dashboard/components/FloatingChat.tsx` — main chat component
- `src/dashboard/hooks/useCliChat.ts` — CLI session management
- `src/dashboard/app/api/cli/route.ts` — PTY spawn and SSE streaming
- `plugins/ai/skills/ai_bridge/augur/data/cli_agents.yaml` — CLI agent configs

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-157: Chat CLI Continuous Session UX**.

Read the full ADR: `docs/decisions/ADR-157-chat-cli-continuous-session.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-157-chat-cli-ux", description="Implementing ADR-157: Chat CLI Continuous Session UX")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-157-chat-cli-ux", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-157 team.
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

**Team name**: `adr-157-chat-cli-ux`

#### Phase 1: Quiet Mode Filter
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create quiet-filter.ts with regex patterns for suppressing tool traces, thinking indicators, permission prompts. Export `filterOutput(raw: string, level: 'quiet'|'normal'|'verbose'): string` | `src/dashboard/lib/chat/quiet-filter.ts` |
| 1.2 | developer | medium | Integrate filter in SSE stream data handler — apply before base64 encoding when verbosity param is set | `src/dashboard/app/api/cli/route.ts` |
| 1.3 | developer | low | Wire verbosity from client: pass `verbosity: 'quiet'` for operation mode in SSE stream URL params, add toggle in ChatHeader for dev mode | `src/dashboard/hooks/useCliChat.ts`, `src/dashboard/components/chat/ChatHeader.tsx` |

#### Phase 2: Auto-Context on Start
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create startup-context.ts: cache project identity (vision summary, hub list), fetch page context via focus-context MCP tool, build startup prompt string | `src/dashboard/lib/chat/startup-context.ts` |
| 2.2 | developer | medium | Modify CLI start flow: add `autoContext` to CliRequestBody, after PTY ready detection (first onData event), write startup prompt to PTY | `src/dashboard/app/api/cli/route.ts` |
| 2.3 | developer | low | Wire autoContext flag: pass `autoContext: true` from FloatingChat in operation mode starts | `src/dashboard/components/FloatingChat.tsx`, `src/dashboard/hooks/useCliChat.ts` |

#### Phase 3: Smart Tool Ranking
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create tool-ranker.ts: implement composite scoring (page_affinity 0.4, recency 0.3, frequency 0.2, global_popularity 0.1), export `rankTools(tools, page, usageStats): RankedTool[]` | `src/dashboard/lib/chat/tool-ranker.ts` |
| 3.2 | developer | medium | Create usage tracking: POST /api/mcp/tools/usage records {tool, page, timestamp} to runtime/chat/tool_usage.jsonl, GET returns aggregated stats | `src/dashboard/app/api/mcp/tools/usage/route.ts` |
| 3.3 | developer | medium | Integrate ranker into tools/list: fetch usage stats, score tools, return sorted with scores. Record usage when tool is selected | `src/dashboard/app/api/mcp/tools/list/route.ts` |
| 3.4 | developer | low | Update ChatToolbar: show top 8 tools with visual weight (larger text/bolder for higher scores), "Show all" expander for remaining | `src/dashboard/components/chat/ChatToolbar.tsx` |

#### Phase 4: Assets Button (PARALLEL with Phase 3)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create relevant assets API: resolve skill from page path, scan skill data dir, score by mtime + access history + file type relevance, return top 10 with metadata | `src/dashboard/app/api/assets/relevant/route.ts` |
| 4.2 | developer | medium | Create AssetsBrowser component: side popover matching ChatSidePopover pattern, shows file name + relative path + last modified + size, click inserts path to chat input | `src/dashboard/components/chat/AssetsBrowser.tsx` |
| 4.3 | developer | low | Add Assets button to ChatToolbar: folder icon, visible in operation mode, badge with count, opens AssetsBrowser popover | `src/dashboard/components/chat/ChatToolbar.tsx` |

#### Phase 5: Continuous Session Lifecycle (depends on Phase 1 + 2)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Create useSessionLifecycle hook: detect page navigation via pathname changes, idle timer (5min), close handler. Emit lifecycle events | `src/dashboard/hooks/useSessionLifecycle.ts` |
| 5.2 | developer | medium | Add system command channel: new `action: 'system'` in CLI API that writes to PTY but skips outputBuffer logging. Add `sendSystemCommand` to useCliChat | `src/dashboard/app/api/cli/route.ts`, `src/dashboard/hooks/useCliChat.ts` |
| 5.3 | developer | medium | Wire page navigation to refocus: on pathname change (while CLI is running), send focus-context payload as system command | `src/dashboard/components/FloatingChat.tsx` |
| 5.4 | developer | low | Add idle timer: after 5min idle, send context-save system command | `src/dashboard/hooks/useSessionLifecycle.ts` |
| 5.5 | developer | low | Add close handler: on chat close, send context-save before stopping CLI | `src/dashboard/components/FloatingChat.tsx` |

#### Phase 6: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Verify operation mode: open chat → CLI starts → context auto-loads → output is quiet. Check no tool traces visible |
| 6.2 | validator | low | Verify page navigation: navigate to different hub → CLI receives refocus prompt → tools update |
| 6.3 | validator | low | Verify tool ranking: use a tool 3x → it appears higher in next fetch. Verify top 8 display |
| 6.4 | validator | low | Verify assets: navigate to career page → Assets button shows career skill data files sorted by recency |
| 6.5 | architect | low | Verify ADR intent: review all changes against ADR-157, confirm no scope creep, operation/dev mode separation preserved |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`npm run build`)
- [ ] Quiet mode suppresses tool traces in operation mode
- [ ] Auto-context loads on CLI start in operation mode
- [ ] Tool ranking reflects page affinity and usage history
- [ ] Assets button visible and functional in operation mode
- [ ] Page navigation triggers auto-refocus without CLI restart
- [ ] No regressions in dev mode behavior
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-157-chat-cli-continuous-session.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
