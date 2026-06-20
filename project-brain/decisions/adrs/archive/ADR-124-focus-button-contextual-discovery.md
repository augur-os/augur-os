---
status: Superseded
date: '2026-02-19'
deciders:
- Project team
related:
- ADR-059 (MCP Context Focus)
- ADR-072 (Cross-IDE Focus Sync)
- ADR-116 (Chat Window Hardening)
- ADR-078 (Magic Button)
hub: null
tags:
- focus
- button
- contextual
- discovery
superseded_by: null
---

# ADR-124: Focus Button with Contextual Discovery

**Superseded by**: [ADR-254](ADR-254-agent-discovery-protocol.md)

## Context

The chat window (`FloatingChat.tsx`, ~2430 lines) serves both operation mode (chatbot) and dev mode (multi-agent terminal). Several buttons exist — Commands, MCP Tools, Data, Magic — but most are mode-specific. There is no single entry point that:

1. **Works in both modes** — operation mode hides Commands/Data/Magic; dev mode hides suggested actions
2. **Orients the user to their current page context** — the existing focus system (ADR-059) narrows MCP tools but doesn't tell the user what they were working on
3. **Discovers recent activity** — no mechanism reads recently-edited files to infer what the user is doing and proactively suggest next steps

Currently, focus is triggered by:
- **Dashboard auto-focus** — `useMCPContext.ts` calls `focus-context` on page navigation (tool scoping only)
- **`/focus` slash command** — returns skill metadata, tools, actions, chains
- **Commands button** — sends `/focus` to IDE bridge (dev mode only)

None of these analyze recent file edits, generate a personalized welcome, or work as a one-click button in both modes.

## Decision

### 1. Focus Button (UI Component)

Add a **Focus** button to `FloatingChat.tsx` toolbar, visible in **both** operation mode and dev mode. Positioned as the leftmost toolbar button (before Commands/MCP Tools).

**Button behavior:**
- Icon: `Crosshair` (from lucide-react) — matches the "focus" metaphor
- Label: "Focus" (tooltip: "Focus on this page — discover what you're working on")
- Click → calls `handleFocusClick()` which:
  1. Auto-starts CLI if not running (same pattern as Magic button)
  2. Calls `GET /api/focus-discover?page={pathname}` to run discovery
  3. Sends discovery result + prompt to CLI for AI-generated welcome message

**Files:**
- Modify: `src/dashboard/components/FloatingChat.tsx` — add `FocusButton` component
- Modify: `src/dashboard/components/FloatingChat.tsx` — add to toolbar in both mode branches

### 2. Unified MCP Backend (No Separate API Route)

Per the MCP-first API pattern, there is **no separate `/api/focus-discover` route**. The dashboard calls the existing `focus-context` MCP tool (enhanced with `discover=true`) via the standard MCP proxy at `/api/mcp/tool`.

**Dashboard call:**
```typescript
const res = await fetch('/api/mcp/tool', {
  method: 'POST',
  body: JSON.stringify({ tool: 'focus-context', args: { current_page: pathname, discover: true } })
});
```

**MCP tool response** (enhanced `FocusPayload` when `discover=true`):
```json
{
  "skill_name": "career",
  "bundle": "career",
  "focus_prompt": "...",
  "active_tools": [...],
  "discovery": {
    "recent_files": [
      { "path": "plugins/career/skills/career/augur/page.tsx", "age_minutes": 12, "change_summary": "+45 -12" }
    ],
    "session_history": [
      { "page": "/career", "entered_at": "2026-02-19T14:30:00Z", "duration_minutes": 25 }
    ],
    "skill_context": {
      "name": "career",
      "description": "Career management hub",
      "actions": ["update-resume", "track-applications"],
      "chains": ["career-weekly-report"],
      "todo_markers": ["TODO_BUG in page.tsx:45"]
    },
    "important_files": [
      { "path": "plugins/career/skills/career/SKILL.md", "summary": "Career tracking with LinkedIn integration..." }
    ]
  }
}
```

This keeps MCP as the single backend for both dashboard and CLI. The `/focus discover` CLI command calls the same MCP tool with the same `discover=true` parameter.

### 3. Focus Discovery Script (Python)

Python script that analyzes recent file activity within a hub/skill directory and returns structured context for the AI to generate a welcome message.

**Location:** `plugins/ai/skills/ai_bridge/scripts/focus_discover.py`

**Discovery algorithm:**

```
Input: page_path (e.g., "/career"), time_window (default: 60 min)

Step 1: Resolve page → skill → plugin directory
  - Use registry.yaml page_contexts to map page → skill
  - Resolve skill → plugin dir via PLUGIN_BUNDLES or directory scan

Step 2: Find recently edited files
  - git log --diff-filter=M --since="{time_window} minutes ago" -- {plugin_dir}/
  - Fallback: find {plugin_dir}/ -mmin -{time_window} -type f
  - Filter out: node_modules, .next, __pycache__, *.pyc
  - Sort by most recently modified first
  - Limit to top 20 files

Step 3: Analyze important files
  - Always read: SKILL.md (first 10 lines), dashboard.yaml, page.tsx (first 30 lines)
  - For each recently edited file: extract first comment block or function names
  - Scan for TODO_BUG, TODO_CLEANUP, TODO_OUTDATED markers

Step 4: Check session history
  - Read runtime/focus_state.json for previous focus entries on this page
  - Calculate time spent on this page in recent sessions

Step 5: Build context object
  - recent_files: [{path, age_minutes, change_summary}]
  - session_history: [{page, entered_at, duration_minutes}]
  - skill_context: {name, description, actions, chains, todo_markers}
  - important_files: [{path, summary}]
```

**Output:** JSON to stdout (consumed by the API route via `runPythonScript`)

**Files:**
- Create: `plugins/ai/skills/ai_bridge/scripts/focus_discover.py`

### 4. Welcome Message Prompt Template

The discovery context feeds into a structured prompt sent to the CLI. The AI generates a personalized welcome with suggestions.

**Prompt template** (built in `FloatingChat.tsx`):

```
You are the Augur assistant. The user just focused on the {skill_name} page.

## Recent Activity
{formatted list of recently edited files with timestamps}

## Skill Context
{skill description, available actions, chains}

## Open Issues
{TODO markers found in this skill's files}

Based on this context, write a brief welcome message:
1. Greet the user and mention what they were recently working on
2. Suggest 2-3 specific next actions based on recent edits and available tools
3. Ask what they'd like to focus on

Keep it concise (3-5 sentences). Use the skill's actions and chains as suggestions where relevant.
```

**Files:**
- Modify: `src/dashboard/components/FloatingChat.tsx` — add `buildFocusPrompt()` function

### 5. MCP Tool Enhancement (Optional)

Extend the existing `focus-context` MCP tool to accept a `discover: true` parameter that triggers the discovery script. This makes the discovery available to all IDEs, not just the dashboard.

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/mcp_management.py` — add `discover` param to `focus_context_tool`
- Modify: `src/mcp/augur_mcp/context_manager.py` — add `focus_with_discovery()` method

## Consequences

### Positive
- **Single entry point** for both modes — reduces cognitive load
- **Contextual awareness** — AI knows what you were working on, suggests relevant next steps
- **Faster onboarding per session** — no need to manually explain context to the AI
- **Cross-IDE potential** — discovery available via MCP tool for Claude Code, Cursor, etc.
- **Builds on existing infrastructure** — reuses `focus-context`, `registry.yaml`, `focus_state.json`

### Negative
- **Git dependency** — `git log` may be slow on large repos; fallback to `find` needed
- **Cold start** — first visit to a page with no recent edits produces thin context
- **FloatingChat complexity** — already 2430 lines; adding another button requires careful placement

### Neutral
- Existing `/focus` slash command continues to work as before
- Dashboard auto-focus (tool scoping) is unchanged
- Operation mode suggested actions coexist with the focus button

## Implementation Order

```
Phase 1: Discovery Script + MCP Enhancement
├── Step 1: Create focus_discover.py with page→skill resolution
├── Step 2: Implement git-based recent file detection
├── Step 3: Add important file analysis and TODO scanning
├── Step 4: Add session history from focus_state.json
├── Step 5: Add discover param to focus-context MCP tool
└── Step 6: Add focus_with_discovery() to context_manager.py (calls focus_discover.py)

Phase 2: UI Integration (depends on Phase 1)
├── Step 7: Add FocusButton component to FloatingChat.tsx
├── Step 8: Add buildFocusPrompt() function
├── Step 9: Wire handleFocusClick → MCP tool (discover=true) → prompt → CLI
└── Step 10: Add button to both operation mode and dev mode toolbars

Phase 3: CLI Integration (depends on Phase 1)
├── Step 11: Update /focus workflow to support /focus discover flag
└── Step 12: /focus discover calls focus-context MCP tool with discover=true

Phase 4: Verification
├── Step 13: Manual test — click Focus on 3 different hub pages
├── Step 14: Verify operation mode and dev mode both show button
├── Step 15: Verify /focus discover in CLI produces same output
└── Step 16: Verify discovery output with recently edited files
```

## Alternatives Considered

### A. Extend Magic Button Instead of New Button
The Magic button already analyzes pages. We could add "recent activity" to its prompt.

**Rejected**: Magic is dev-mode only and focused on improvement suggestions, not session orientation. The Focus button serves a fundamentally different purpose — "what am I working on?" vs "what should I improve?"

### B. Auto-Run Discovery on Page Navigation
Instead of a button, automatically run discovery every time a user navigates to a page.

**Rejected**: Too expensive — `git log` and file scanning on every navigation would add latency. A deliberate button click is the right UX for an operation that takes 1-2 seconds. Could add as opt-in setting later.

### C. Use Only Client-Side File Metadata (No Python Script)
Fetch file metadata via a Next.js API route using `fs.stat()` instead of a Python script.

**Rejected**: Node.js `fs.stat` can't access git history (change summaries, commit messages). The Python script can use `git log` for richer context. Also aligns with existing pattern of Python scripts called via `runPythonScript`.

## References

- [ADR-059: MCP Context Focus](ADR-059-mcp-context-focus.md)
- [ADR-072: Cross-IDE Focus Sync](ADR-072-focus-wow-demo.md)
- [ADR-078: Magic Button](ADR-078-magic-button-proactive-insights.md)
- [ADR-116: Chat Window Hardening](ADR-116-chat-window-hardening.md)
- `src/dashboard/components/FloatingChat.tsx` — Main chat component
- `src/mcp/augur_mcp/context_manager.py` — Focus resolution logic
- `plugins/ai/skills/ai_bridge/augur/agent-workflows/focus.md` — `/focus` command

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-124: Focus Button with Contextual Discovery**.

Read the full ADR: `docs/decisions/ADR-124-focus-button-contextual-discovery.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-124-focus-button", description="Implementing ADR-124: Focus Button with Contextual Discovery")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-124-focus-button", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-124 team.
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

**Team name**: `adr-124-focus-button`

#### Phase 1: Discovery Script + MCP Backend
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `focus_discover.py` with page→skill resolution using `registry.yaml` `page_contexts` and plugin directory scanning | `plugins/ai/skills/ai_bridge/scripts/focus_discover.py` |
| 1.2 | developer | medium | Add git-based recent file detection (`git log --diff-filter=M --since`) with `find` fallback, filtering out build artifacts | `plugins/ai/skills/ai_bridge/scripts/focus_discover.py` |
| 1.3 | developer | medium | Add important file analysis (SKILL.md, dashboard.yaml, page.tsx reading) and TODO marker scanning | `plugins/ai/skills/ai_bridge/scripts/focus_discover.py` |
| 1.4 | developer | low | Add session history reading from `runtime/focus_state.json` | `plugins/ai/skills/ai_bridge/scripts/focus_discover.py` |
| 1.5 | developer | medium | Add `discover: bool = False` param to `focus_context_tool` in `mcp_management.py`. When true, call `focus_with_discovery()` | `src/mcp/augur_mcp/infrastructure/mcp_management.py` |
| 1.6 | developer | medium | Add `focus_with_discovery(skill_name, page)` method to `ContextManager` that runs `focus_discover.py` and merges discovery into `FocusPayload` | `src/mcp/augur_mcp/context_manager.py` |

#### Phase 2: UI Integration
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add `FocusButton` component to `FloatingChat.tsx` — Crosshair icon, tooltip, loading state, click handler calling `focus-context` MCP tool with `discover=true` via `/api/mcp/tool` proxy | `src/dashboard/components/FloatingChat.tsx` |
| 2.2 | developer | medium | Add `buildFocusPrompt(discovery)` function that formats discovery context into AI welcome prompt template | `src/dashboard/components/FloatingChat.tsx` |
| 2.3 | developer | medium | Wire `handleFocusClick` → MCP tool → build prompt → auto-start CLI → send message. Add button to toolbar in BOTH operation mode and dev mode sections | `src/dashboard/components/FloatingChat.tsx` |

#### Phase 3: CLI Integration
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Update `/focus` workflow to support `/focus discover` flag — calls `focus-context` MCP tool with `discover=true` | `plugins/ai/skills/ai_bridge/augur/agent-workflows/focus.md` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | low | Run TypeScript build (`npm run build` in `src/dashboard/`), verify no type errors |
| 4.2 | validator | low | Run Python tests (`pytest tests/src/ -x`), verify discovery script works |
| 4.3 | architect | low | Verify Focus button appears in both operation mode and dev mode, and `/focus discover` in CLI produces same output |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Focus button visible in both operation mode and dev mode
- [ ] Discovery script returns recently edited files for at least 3 different hubs
- [ ] Welcome message includes specific suggestions based on recent activity
- [ ] MCP tool accepts `discover=true` and returns enhanced focus payload
- [ ] `/focus discover` in CLI produces same discovery output as button click
- [ ] No separate API route created — all backend logic goes through MCP tool
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-124-focus-button-contextual-discovery.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
