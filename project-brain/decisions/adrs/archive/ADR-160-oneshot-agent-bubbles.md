---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-130 (oneshot dispatch)
- ADR-134 (dispatch escalation)
- ADR-034 (CLI integration)
- ADR-035 (chat window)
- ADR-047 (terminal view)
- ADR-144 (chat dispatch mode)
- ADR-157 (continuous session UX)
hub: null
tags:
- oneshot
- agent
- bubbles
- visible
- cli
superseded_by: null
---

# ADR-160: Oneshot Agent Bubbles — Visible CLI Execution in Chat Window

---

## Context

Oneshot dispatch (`dispatch: oneshot`) currently runs LLM tasks headlessly via `run-oneshot-cli` with a 60-second timeout. The user sees only a loading toast (`Running ${label}...`) and eventually a result or error. There is no way to:

1. **See what the agent is doing** — the CLI runs in the background with zero visibility
2. **Intervene** — if the agent asks a question or gets stuck, the user cannot respond
3. **Monitor parallel agents** — dispatch-escalation and multi-agent actions have no visual representation

This creates a black-box experience: the user triggers an action and waits blindly. For expensive or long-running operations, this is unacceptable.

The current chat window (`FloatingChat`) is a single-instance component positioned at `bottom-right` with one terminal session. It supports one CLI at a time via `useCliChat`. There is no concept of stacked or parallel agent sessions.

### Current Pain Points

- **Invisible execution**: 6 oneshot actions across career, lifestyle, and other hubs run with no output streaming
- **No intervention path**: Timeout errors (504) and agent questions are silent failures
- **Single-session constraint**: Only one CLI session can run in the chat window at a time
- **Lost context**: Oneshot results arrive as static text blobs, disconnected from the execution trace

---

## Decision

### 1. Agent Bubble Stack — Stacked Mini-CLIs Above the Chat Window

Introduce an **AgentBubbleStack** component that renders up to **5 concurrent agent bubbles** stacked vertically above the main FloatingChat window. Each bubble represents one active CLI session running an agent task.

**Visual layout** (bottom-right corner, bottom to top):

```
┌──────────────────────┐  ← Agent Bubble 3 (top-most, if exists)
│ ● ai-tailor-resume   │
└──────────────────────┘
┌──────────────────────┐  ← Agent Bubble 2
│ ● recipe-ideas       │
└──────────────────────┘
┌──────────────────────┐  ← Agent Bubble 1 (first spawned)
│ ● learning-roadmap   │
└──────────────────────┘
┌──────────────────────┐  ← Main FloatingChat (existing)
│  Chat Window         │
│  (unchanged)         │
└──────────────────────┘
```

**Bubble states**:

| State | Visual | Behavior |
|-------|--------|----------|
| Running (minimized) | Pill with action label + spinning indicator | Default on spawn |
| Running (expanded) | Mini-terminal (200px height) | On double-click |
| Needs attention | Glowing red pulse animation | Timeout, error, or user question detected |
| Complete | Fade-out + evaporate animation (300ms) | Auto-close on success |

### 2. Agent Bubble Component — `AgentBubble`

Each bubble is a lightweight CLI instance with key differences from the main chat:

1. **Starts minimized** — collapsed pill showing only the action label and status indicator
2. **Full terminal mode** — no input bar, no buttons, no chat bubbles; raw xterm.js terminal output only
3. **Double-click to expand** — opens a compact terminal view (200px height) where the user can see streaming output; in operation mode, double-click also enables keyboard input to the PTY
4. **Auto-evaporate on completion** — when the CLI exits with code 0, the bubble fades out and is removed from the stack after 2 seconds
5. **Red glow on issues** — if the agent times out, encounters an error, or outputs a prompt/question pattern, the bubble pulses red to draw attention

**File**: `src/dashboard/components/chat/AgentBubble.tsx`

### 3. Agent Bubble Store — `agentBubbleStore`

New Zustand store to manage the lifecycle of agent bubbles independently from the main `chatStore`.

```typescript
interface AgentBubbleState {
  id: string;                          // Unique bubble ID (UUID)
  actionId: string;                    // Source action
  actionLabel: string;                 // Display label
  status: 'running' | 'attention' | 'complete' | 'error';
  isExpanded: boolean;                 // Minimized (false) or expanded terminal
  pid?: number;                        // CLI process PID for cleanup
  startedAt: Date;
  completedAt?: Date;
}

interface AgentBubbleStore {
  bubbles: AgentBubbleState[];         // Max 5
  addBubble: (bubble: Omit<AgentBubbleState, 'id'>) => string | null;  // null if at capacity
  removeBubble: (id: string) => void;
  updateBubble: (id: string, patch: Partial<AgentBubbleState>) => void;
  toggleExpanded: (id: string) => void;
  getBubbleCount: () => number;
}
```

**Capacity**: Hard limit of 5 concurrent bubbles. If a 6th agent is triggered, it queues (FIFO) and spawns when a slot opens.

**File**: `src/dashboard/lib/stores/agentBubbleStore.ts`

### 4. Oneshot Dispatch Upgrade — From Headless to Embedded CLI

Replace the headless `fetch('/api/actions/oneshot')` path with an **embedded CLI session** that runs inside an agent bubble. The execution flow changes from:

**Before** (ADR-130):
```
User clicks action → fetch(/api/actions/oneshot) → wait 60s → toast result
```

**After** (ADR-160):
```
User clicks action → spawn AgentBubble → start CLI in bubble → stream output
                   → auto-evaporate on success
                   → glow red on error/question → user can expand and intervene
```

**Changes to `useActionRunner.ts`**:

The `runOneshot()` function will:
1. Check `agentBubbleStore.getBubbleCount()` — if < 5, proceed; else queue
2. Create a bubble via `agentBubbleStore.addBubble()`
3. Start a CLI process via the same `useCliChat.startCli()` mechanism but bound to the bubble's xterm instance
4. Monitor the CLI output for completion/error patterns
5. On success: set bubble status to `complete` (triggers evaporate animation)
6. On error/timeout/question: set bubble status to `attention` (triggers red glow)

**File changes**: `src/dashboard/hooks/useActionRunner.ts`

### 5. Agent Bubble PTY Hook — `useAgentBubblePty`

A lightweight version of `useXtermTerminal` tailored for agent bubbles:

- Smaller terminal (cols: 80, rows: 8 when expanded)
- Read-only by default; writable only when user double-clicks in operation mode
- Output pattern detection:
  - Exit code 0 → `complete`
  - Error/exception patterns → `error`
  - Question mark at end of line / "y/n" / "continue?" → `attention`
  - No output for 30s → `attention` (potential hang)
- Auto-kill after 90s timeout (configurable per action via `timeout_s` YAML field)

**File**: `src/dashboard/hooks/useAgentBubblePty.ts`

### 6. Attention Detection Patterns

The bubble monitors CLI output to detect when user intervention is needed:

```typescript
const ATTENTION_PATTERNS = [
  /\?\s*$/,                    // Line ending with ?
  /\(y\/n\)/i,                 // y/n prompt
  /\[Y\/n\]/,                  // [Y/n] prompt
  /continue\?/i,               // continue prompt
  /press enter/i,              // press enter prompt
  /waiting for input/i,        // explicit input wait
  /permission denied/i,        // access error
  /SIGTERM|SIGKILL|killed/i,   // process signals
];
```

When any pattern matches, the bubble transitions to `attention` state with the red glow animation.

**File**: `src/dashboard/lib/chat/attentionPatterns.ts`

### 7. Visual Design

**Minimized bubble** (pill):
```
┌─────────────────────────────────────┐
│  ◉  ai-tailor-resume          ⏳ 12s │
└─────────────────────────────────────┘
```
- 40px height, width matches FloatingChat (700px)
- 8px gap between stacked bubbles
- Status icon: ◉ spinning (running), ◉ red pulse (attention), ✓ green (complete)
- Timer showing elapsed seconds

**Expanded bubble** (mini-terminal):
```
┌─────────────────────────────────────┐
│  ◉  ai-tailor-resume          ⏳ 12s │
├─────────────────────────────────────┤
│  $ claude --print "..."             │
│  Generating tailored resume...      │
│  [████████████░░░] 67%              │
│                                     │
└─────────────────────────────────────┘
```
- 200px height when expanded
- xterm.js terminal with same theme as main chat
- Click outside or Escape to re-minimize

**Red glow** (attention state):
- CSS `box-shadow: 0 0 12px 2px rgba(239, 68, 68, 0.6)` with pulse animation
- `animation: pulse-red 1.5s ease-in-out infinite`

### 8. Queue System

When 5 bubbles are active and a new oneshot is triggered:

1. Show toast: "Agent queued — waiting for a slot (5/5 active)"
2. Add to FIFO queue in `agentBubbleStore`
3. When any bubble evaporates, dequeue and spawn next
4. Queue indicator appears on the main FloatingChat header: "🔴 2 queued"

---

## Consequences

### Positive
- **Full visibility** into oneshot execution — users see streaming output in real-time
- **User intervention** — users can respond to agent questions or kill stuck processes
- **Parallel awareness** — up to 5 concurrent agents are visually tracked
- **Graceful lifecycle** — auto-cleanup on success, attention flag on problems
- **Zero disruption** — main FloatingChat session is unaffected; bubbles are independent

### Negative
- **Terminal resource cost** — each bubble instantiates an xterm.js terminal (mitigated: only created on expand)
- **Complexity increase** — new store, hook, component, and pattern detection adds ~600 LOC
- **Behavior change** — existing oneshot actions switch from headless fetch to embedded CLI, which changes timing characteristics and error handling

### Neutral
- The headless `/api/actions/oneshot` route remains for programmatic/API callers (not removed)
- Dispatch-escalation (ADR-134) tiers are unchanged; Tier 1 now renders in a bubble instead of headlessly
- Action YAML files require no changes — `dispatch: oneshot` behavior is upgraded transparently

---

## Implementation Order

```
Phase 1: Store & Types
├── Step 1: Create agentBubbleStore with state, actions, capacity logic
├── Step 2: Create attention pattern detection module
└── Step 3: Define AgentBubbleState types and exports

Phase 2: Components (depends on Phase 1)
├── Step 4: Create AgentBubble component (pill + expanded states)
├── Step 5: Create AgentBubbleStack layout component
└── Step 6: Wire AgentBubbleStack into main layout (above FloatingChat)

Phase 3: PTY Integration (depends on Phase 1)
├── Step 7: Create useAgentBubblePty hook (lightweight terminal)
└── Step 8: Wire PTY output to attention pattern detection

Phase 4: Dispatch Wiring (depends on Phases 2 + 3)
├── Step 9: Modify runOneshot() in useActionRunner to spawn bubbles
├── Step 10: Add queue system for overflow (>5 bubbles)
└── Step 11: Wire dispatch-escalation Tier 1 to use bubble path

Phase 5: Polish & Animation
├── Step 12: Implement evaporate animation (fade-out + scale-down)
├── Step 13: Implement red glow pulse animation
└── Step 14: Add elapsed timer and status indicators

Phase 6: Verification (depends on all above)
├── Step 15: Test parallel agent bubble lifecycle (spawn, expand, evaporate)
├── Step 16: Test attention detection patterns
├── Step 17: Test queue behavior at capacity (5+1)
└── Step 18: Verify main FloatingChat session is unaffected
```

---

## Alternatives Considered

### 1. Tabbed Multi-Session in Existing Chat Window

Add tabs to FloatingChat for each agent session, similar to browser tabs.

**Rejected**: Tabs require the chat window to be open and visible. Oneshot agents should be low-friction background tasks that don't commandeer the main chat. Tabs also don't convey the "ephemeral task" nature — bubbles communicate transience better.

### 2. Notification-Only (No Terminal)

Show agent progress as a notification stack (like macOS notifications) with no terminal access.

**Rejected**: Defeats the core purpose — users need to intervene when agents get stuck. Read-only notifications don't solve the "agent is asking a question" problem. The whole point is to give users a terminal they can interact with when needed.

### 3. Extend FloatingChat to Support Multiple PTY Sessions

Make the existing FloatingChat manage multiple concurrent PTY sessions with a session switcher.

**Rejected**: Over-engineering. The main chat window already has complex state (messages, views, actions, tools, files). Adding multi-session multiplexing would make it even more complex. Separate bubble components are simpler and independently testable.

---

## References

- ADR-130 — Oneshot dispatch mode
- ADR-134 — Dispatch escalation tiers
- ADR-034 — Embedded CLI integration
- ADR-035 — Floating chat window
- ADR-047 — Terminal view mode
- [ADR-157](ADR-157-chat-cli-continuous-session.md) — Continuous session UX

---

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: runOneshot
      module: src/dashboard/hooks/useActionRunner.ts
      breaking: false  # Fallback to headless still available
  patterns_deprecated:
    - grep: "fetch\\('/api/actions/oneshot'"
      replacement: "agentBubbleStore.addBubble() + embedded CLI"
  files_affected:
    - glob: "src/dashboard/hooks/useActionRunner.ts"
    - glob: "src/dashboard/components/FloatingChat.tsx"
    - glob: "src/dashboard/lib/stores/chatStore.ts"
```

---

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-160: Oneshot Agent Bubbles — Visible CLI Execution in Chat Window**.

Read the full ADR: `docs/decisions/ADR-160-oneshot-agent-bubbles.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-160-agent-bubbles", description="Implementing ADR-160: Oneshot Agent Bubbles")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-160-agent-bubbles", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-160 team.
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

**Team name**: `adr-160-agent-bubbles`

#### Phase 1: Store & Types
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `agentBubbleStore` Zustand store with AgentBubbleState, addBubble (max 5), removeBubble, updateBubble, toggleExpanded, queue FIFO logic | `src/dashboard/lib/stores/agentBubbleStore.ts` |
| 1.2 | developer | low | Create attention pattern detection module with ATTENTION_PATTERNS regex array and `detectAttention(line: string): boolean` function | `src/dashboard/lib/chat/attentionPatterns.ts` |

#### Phase 2: Components (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Create `AgentBubble` component — pill (minimized) and expanded (mini-terminal) states, status indicators (spinning/red-glow/green-check), elapsed timer, double-click expand, click-outside minimize. Use xterm.js only when expanded (lazy init). | `src/dashboard/components/chat/AgentBubble.tsx` |
| 2.2 | developer | medium | Create `AgentBubbleStack` layout component — positions bubbles above FloatingChat (stacked vertically with 8px gaps), renders from agentBubbleStore.bubbles, handles evaporate animation on removal | `src/dashboard/components/chat/AgentBubbleStack.tsx` |
| 2.3 | developer | medium | Wire AgentBubbleStack into main dashboard layout — render above FloatingChat's fixed position (calculate `bottom` offset from bubble count), ensure z-index layering is correct | `src/dashboard/components/FloatingChat.tsx` |

#### Phase 3: PTY Integration (depends on Phase 1)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Create `useAgentBubblePty` hook — lightweight xterm.js terminal (80×8), read-only by default, writable on double-click in operation mode, output monitoring via attentionPatterns.detectAttention(), auto-kill after timeout, exit code detection for completion | `src/dashboard/hooks/useAgentBubblePty.ts` |
| 3.2 | developer | medium | Wire PTY output callbacks to agentBubbleStore.updateBubble() — on attention pattern match set status='attention', on exit code 0 set status='complete', on error set status='error' | `src/dashboard/hooks/useAgentBubblePty.ts` |

#### Phase 4: Dispatch Wiring (depends on Phases 2 + 3)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | high | Modify `runOneshot()` in useActionRunner — check bubble capacity, create bubble via store, start CLI process in bubble's PTY, monitor for completion/error, auto-evaporate on success. Keep headless fetch as fallback when FloatingChat is not mounted. | `src/dashboard/hooks/useActionRunner.ts` |
| 4.2 | developer | medium | Add queue system — when 5 bubbles active, queue new oneshot requests in agentBubbleStore FIFO queue, dequeue on bubble evaporation, show toast for queued state | `src/dashboard/lib/stores/agentBubbleStore.ts`, `src/dashboard/hooks/useActionRunner.ts` |
| 4.3 | developer | medium | Wire dispatch-escalation Tier 1 to use bubble path — update `dispatch-escalation.ts` to spawn agent bubble instead of headless oneshot when dashboard is active | `src/dashboard/lib/dispatch-escalation.ts` |

#### Phase 5: Polish & Animation
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Implement evaporate animation — 300ms fade-out + scale-down CSS transition on bubble removal, 2s delay after completion before triggering | `src/dashboard/components/chat/AgentBubble.tsx` |
| 5.2 | developer | low | Implement red glow pulse — `@keyframes pulse-red` CSS animation, box-shadow with rgba(239,68,68,0.6), 1.5s infinite ease-in-out cycle | `src/dashboard/components/chat/AgentBubble.tsx` |
| 5.3 | developer | low | Add elapsed timer display — show seconds since spawn in pill, update every 1s via setInterval, format as "⏳ 12s" / "⏳ 1m 23s" | `src/dashboard/components/chat/AgentBubble.tsx` |

#### Phase 6: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Run all tests: `pytest tests/src/`, `npm run build`, verify no regressions |
| 6.2 | validator | low | Test attention detection patterns — unit tests for all ATTENTION_PATTERNS against sample CLI output |
| 6.3 | validator | low | Test bubble lifecycle — spawn, expand, evaporate, queue at capacity (5+1) |
| 6.4 | architect | low | Verify ADR intent matches implementation — bubbles are independent from main chat, max 5, auto-evaporate, red glow |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] AgentBubble renders above FloatingChat with correct stacking
- [ ] Oneshot actions spawn visible bubbles instead of headless fetch
- [ ] Bubbles auto-evaporate on success, glow red on attention
- [ ] Max 5 concurrent bubbles with FIFO queue for overflow
- [ ] Main FloatingChat session is completely unaffected
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-160-oneshot-agent-bubbles.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
