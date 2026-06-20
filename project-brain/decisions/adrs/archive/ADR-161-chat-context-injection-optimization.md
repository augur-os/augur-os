---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-030 (context merge algorithm)
- ADR-034 (embedded CLI)
- ADR-047 (operation mode chatbot)
- ADR-059 (skill-aware focus)
- ADR-134 (dispatch escalation)
- ADR-157 (continuous session UX)
hub: null
tags:
- chat
- context
- injection
- optimization
superseded_by: null
---

# ADR-161: Chat Context Injection Optimization

---

## Context

Chat context injection is the system that enriches CLI agent sessions with knowledge about the current page, active skill, user preferences, and project identity — so the agent can act on the user's behalf without asking "what are you working on?" every time.

Today, context flows through **six disconnected layers** with no coordination, no token budget, and no deduplication:

| Layer | File | What it injects | Problem |
|-------|------|----------------|---------|
| 1. Chat Store | `chatStore.ts` | `ChatContext` (page, hub, skill, actionId) | Untyped `[key: string]: unknown` catch-all; no validation |
| 2. Action Runner | `useActionRunner.ts:buildPrompt()` | Action label + description + page | Flat string, no structured context, ignores hub/skill |
| 3. Startup Context | `startup-context.ts` | Project identity (vision.md) + page path | 5-min stale cache; only page path, no skill data |
| 4. CLI Route | `api/cli/route.ts` | `AUGUR_CURRENT_PAGE` env var | Single env var — agents must call MCP to get anything else |
| 5. Chat Session File | `runtime/temp/chat_session.json` | Page + cliId + status | Written pre-spawn for MCP `get-chat-session`; minimal |
| 6. MCP Context Manager | `context_manager.py` | Mode, skills, tools, page | Full merge algorithm but decoupled from dashboard; agent must call `get-context` |

### Current Pain Points

1. **No token budget** — Startup context (`buildStartupPrompt`) injects ~500 chars of project identity on every session start, regardless of whether the page is the AI hub (where it's useful) or a recipe page (where it's noise). No mechanism to cap total injected tokens.

2. **Stale context** — `readProjectIdentity()` caches for 5 minutes. If the user navigates from `/consulting` to `/career` within that window, the startup prompt still references the old context. Page context is only captured at spawn time, never refreshed.

3. **Redundant round-trips** — After the dashboard writes `chat_session.json` and spawns the CLI, the CLI agent must still call `get-chat-session` and then `get-context` to learn about available tools and skills. That's 2 MCP round-trips (~100ms each) before the agent can start its actual task.

4. **No skill-aware injection** — When the user triggers an action from the Notes page, `buildPrompt()` includes the action description but not the skill's capabilities, data paths, or relevant MCP tools. The agent flies blind until it calls `focus-context`.

5. **Context duplication across tiers** — Dispatch escalation (ADR-134) sends the same prompt through Tier 1→2→3 with escalation preambles appended, but the underlying context (page, skill, tools) is never refreshed between tiers. A 60s oneshot might complete after the user has already navigated away.

6. **No context for agent bubbles** — ADR-160 agent bubbles spawn oneshot CLIs with `oneshotPrompt` only. They inherit no structured context (hub, skill, available tools) because the bubble dispatch path bypasses `buildStartupPrompt()` entirely.

### Token Cost Analysis

Current injection per session start (approximate):

| Component | Tokens | Source |
|-----------|--------|--------|
| Project identity (vision.md) | ~150 | `readProjectIdentity()` |
| Page context (path + hub) | ~30 | `buildPageContext()` |
| Greeting instruction | ~20 | Hardcoded suffix |
| **Total startup** | **~200** | `buildStartupPrompt()` |
| Action prompt (per action) | ~100-300 | `buildPrompt()` |
| MCP get-context response | ~500-1000 | `context_manager.merge()` |

The problem isn't size — it's that startup context is **low-signal** (generic identity) while high-signal context (skill data, tools, chains) requires extra MCP calls. The token budget is inverted.

---

## Decision

### 1. Structured Context Envelope — Replace Flat Strings with Typed Payloads

Replace `buildStartupPrompt()` (flat string) and `buildPrompt()` (flat string) with a single `ContextEnvelope` that carries structured, typed context through all dispatch paths.

```typescript
interface ContextEnvelope {
  /** Session identity */
  sessionId: string;
  timestamp: number;

  /** Navigation context */
  page: string;
  hub: string;
  skill: string | null;

  /** Skill context (pre-resolved) */
  skillSummary: string | null;     // First 200 chars of SKILL.md
  skillDataDir: string | null;     // Resolved data directory
  skillTools: string[];            // MCP tools relevant to this skill
  skillActions: string[];          // Available action IDs

  /** Action context (when triggered by action button) */
  action: {
    id: string;
    label: string;
    description: string;
    prompt: string;
  } | null;

  /** Token budget */
  maxContextTokens: number;        // Default: 800
  priority: 'minimal' | 'standard' | 'rich';
}
```

**File**: `src/dashboard/lib/chat/context-envelope.ts`

### 2. Context Resolution API — Server-Side Pre-Resolution

Add a new API endpoint that resolves all context in one call, replacing the current multi-step process (write session → spawn CLI → CLI calls get-chat-session → CLI calls get-context).

```
POST /api/chat/resolve-context
Body: { page: string, actionId?: string, priority?: 'minimal' | 'standard' | 'rich' }
Response: ContextEnvelope
```

The endpoint:
1. Parses `page` to extract hub + skill
2. Reads skill's `SKILL.md` (first 200 chars) and `augur.yaml` (action list)
3. Calls `context_manager.get_page_tools()` to resolve available MCP tools
4. Assembles a `ContextEnvelope` within the token budget
5. Returns in ~50ms (all local reads, no LLM)

This replaces:
- `buildStartupPrompt()` (now derived from envelope)
- `writeChatSession()` (session file written from envelope)
- Agent's `get-chat-session` + `get-context` calls (pre-resolved)

**File**: `src/dashboard/app/api/chat/resolve-context/route.ts`

### 3. Token Budget Tiers — Priority-Based Context Depth

Three tiers control how much context is injected, matching the dispatch mode:

| Priority | Budget | When | What's included |
|----------|--------|------|----------------|
| `minimal` | 200 tokens | Agent bubbles (oneshot) | Page + hub + action prompt only |
| `standard` | 800 tokens | Chat sessions | Page + hub + skill summary + tool list |
| `rich` | 2000 tokens | IDE dispatch | Full skill context + action chain + data paths |

The `maxContextTokens` field in `ContextEnvelope` is a soft cap — the prompt builder truncates from lowest-priority sections first:
1. Project identity (cut first — lowest signal)
2. Skill actions list (cut second — derivable from MCP)
3. Skill tools list (cut third — agent discovers via MCP anyway)
4. Skill summary (preserved — highest signal-to-token ratio)
5. Page/hub/action (always preserved — essential routing)

### 4. Envelope Injection Points — Unified Dispatch Wiring

All dispatch paths construct a `ContextEnvelope` before execution:

#### 4a. Chat dispatch (`runChat`)
```
User clicks action → resolve-context API (standard) → openChat with envelope
                   → startup prompt built from envelope (not vision.md)
```

#### 4b. Oneshot / Agent Bubble dispatch (`runOneshot`)
```
User clicks action → resolve-context API (minimal) → spawn bubble
                   → oneshotPrompt includes action + page only
```

#### 4c. IDE dispatch (`runIde`)
```
User clicks action → resolve-context API (rich) → adaptPrompt with full context
                   → IDE receives skill-aware prompt
```

#### 4d. Escalation dispatch (ADR-134)
```
Tier 1 fail → resolve-context API (standard, re-resolved) → Tier 2 with fresh context
           → if still on same page: reuse envelope
           → if navigated: new envelope with current page
```

**Key change**: Escalation tiers re-resolve context before each escalation, so Tier 2 and Tier 3 see the user's *current* page, not the stale page from Tier 1 spawn.

### 5. Context Refresh on Navigation — Live Context for Long Sessions

For active chat sessions (ADR-157 continuous sessions), context can go stale if the user navigates to a different page. Add a navigation-aware refresh:

1. `FloatingChat` subscribes to `window.location.pathname` changes via `usePathname()` (Next.js hook)
2. On navigation: call `resolve-context` API with new page
3. If hub changed: write a system command to the PTY via the existing `system` action handler
4. System command: `/context-save` followed by the new context summary
5. Agent sees the context update in its conversation and adapts

**Throttle**: Max 1 refresh per 10 seconds to avoid noise during rapid navigation.

**File changes**: `src/dashboard/components/FloatingChat.tsx`, `src/dashboard/hooks/useCliChat.ts`

### 6. Envelope Serialization — Prompt Builder

The `ContextEnvelope` is serialized to a prompt string by a budget-aware builder:

```typescript
function buildPromptFromEnvelope(envelope: ContextEnvelope): string {
  const sections: Array<{ content: string; priority: number; tokens: number }> = [];

  // Priority 5 (always): Core routing
  sections.push({
    content: `Page: ${envelope.page}\nHub: ${envelope.hub}`,
    priority: 5,
    tokens: estimateTokens(/*...*/),
  });

  // Priority 4 (always): Action prompt
  if (envelope.action) {
    sections.push({
      content: `## Task\n${envelope.action.prompt}`,
      priority: 4,
      tokens: estimateTokens(/*...*/),
    });
  }

  // Priority 3: Skill summary
  if (envelope.skillSummary) {
    sections.push({
      content: `## Skill: ${envelope.skill}\n${envelope.skillSummary}`,
      priority: 3,
      tokens: estimateTokens(/*...*/),
    });
  }

  // Priority 2: Available tools
  if (envelope.skillTools.length > 0) {
    sections.push({
      content: `Available tools: ${envelope.skillTools.join(', ')}`,
      priority: 2,
      tokens: estimateTokens(/*...*/),
    });
  }

  // Priority 1 (cut first): Project identity
  sections.push({
    content: readProjectIdentity(),
    priority: 1,
    tokens: estimateTokens(/*...*/),
  });

  // Assemble within budget — cut lowest priority first
  return assembleWithinBudget(sections, envelope.maxContextTokens);
}
```

**File**: `src/dashboard/lib/chat/context-envelope.ts`

### 7. Deprecate Direct vision.md Reads

`readProjectIdentity()` in `startup-context.ts` reads `docs/memory/vision.md` on every session start. This function becomes internal to the envelope builder (Priority 1 section, first to be cut). The 5-minute cache remains but is now a non-issue — the cached identity is used as filler, not as the primary context.

`buildStartupPrompt()` and `buildStartupContext()` are deprecated. Callers migrate to `buildPromptFromEnvelope()`.

---

## Consequences

### Positive
- **Single source of truth** — All dispatch paths use `ContextEnvelope`, eliminating ad-hoc context assembly in 4 separate files
- **Token-aware** — Budget tiers prevent over-injection for oneshot (cheap) and under-injection for IDE (rich)
- **Faster agent startup** — Pre-resolved context eliminates 2 MCP round-trips (~200ms saved per session)
- **Fresh context on escalation** — Tier 2/3 see current page, not stale Tier 1 page
- **Navigation-aware** — Long chat sessions adapt when the user moves between pages

### Negative
- **New API endpoint** — `resolve-context` adds a route, though it replaces implicit work done by agents
- **Migration cost** — 4 files need updating (`useActionRunner.ts`, `startup-context.ts`, `FloatingChat.tsx`, `dispatch-escalation.ts`)
- **Skill resolution latency** — Reading `SKILL.md` and `augur.yaml` per session adds ~10ms (mitigated by filesystem cache)

### Neutral
- `chat_session.json` continues to be written (for MCP `get-chat-session`) but is now populated from the envelope
- The MCP `get-context` and `focus-context` tools remain available for agents that need dynamic re-focusing mid-session
- `buildPrompt()` in `useActionRunner.ts` remains as a fallback for actions without a resolved envelope

---

## Implementation Order

```
Phase 1: Types & API
├── Step 1: Create ContextEnvelope type and budget constants
├── Step 2: Create resolve-context API route (reads SKILL.md, augur.yaml, page tools)
└── Step 3: Create buildPromptFromEnvelope() with priority-based assembly

Phase 2: Dispatch Wiring (depends on Phase 1)
├── Step 4: Wire runChat() to resolve-context → envelope → startup prompt
├── Step 5: Wire runOneshot() to resolve-context (minimal) → bubble prompt
├── Step 6: Wire runIde() to resolve-context (rich) → adapted prompt
└── Step 7: Wire dispatch-escalation to re-resolve context per tier

Phase 3: Navigation Refresh (depends on Phase 2)
├── Step 8: Add usePathname() listener in FloatingChat
├── Step 9: Throttled resolve-context call on navigation
└── Step 10: System command injection for context update

Phase 4: Cleanup & Deprecation
├── Step 11: Mark buildStartupPrompt/buildStartupContext as deprecated
├── Step 12: Update chat_session.json writes to use envelope data
└── Step 13: Remove redundant readProjectIdentity() cache logic

Phase 5: Verification
├── Step 14: Unit tests for ContextEnvelope assembly and budget truncation
├── Step 15: Integration test: action → resolve-context → CLI receives context
├── Step 16: Test escalation re-resolution (navigate during Tier 1 → Tier 2 sees new page)
└── Step 17: Test navigation refresh throttle (rapid nav → max 1 refresh per 10s)
```

---

## Alternatives Considered

### 1. Inject All Context via Environment Variables

Pass structured context as JSON in `AUGUR_CONTEXT` env var, read by the CLI on startup.

**Rejected**: Environment variables have OS-level size limits (~128KB on macOS, ~2MB on Linux), but more importantly, env is set at spawn time and cannot be updated mid-session. Navigation-aware refresh requires a live channel (PTY write), not a static env.

### 2. Lazy Context — Let the Agent Call MCP

Keep current approach: inject minimal context at spawn, let the agent call `get-context` and `focus-context` on demand.

**Rejected**: This is the status quo. It costs 2 MCP round-trips (~200ms) per session and requires every agent to follow the session protocol. Oneshot agents (60s timeout) waste 3-5% of their budget on context discovery. Pre-resolution is strictly better.

### 3. WebSocket Context Channel

Open a persistent WebSocket between FloatingChat and the CLI for bidirectional context updates.

**Rejected**: Over-engineering. The existing PTY channel (SSE stream + system commands) already provides a live channel. Adding WebSocket infrastructure for context alone doesn't justify the complexity. PTY system commands (ADR-157 Decision 4) achieve the same result.

---

## References

- ADR-030 — Context merge algorithm
- ADR-034 — Embedded CLI integration
- [ADR-047](ADR-047-operation-mode-chatbot-experience.md) — Operation mode chatbot
- ADR-059 — Skill-aware focusing
- ADR-134 — Dispatch escalation tiers
- [ADR-157](ADR-157-chat-cli-continuous-session.md) — Continuous session UX

---

## Impact Manifest

```yaml
impact:
  apis_changed:
    - endpoint: POST /api/chat/resolve-context
      breaking: false  # New endpoint, no existing callers
    - function: buildStartupPrompt
      module: src/dashboard/lib/chat/startup-context.ts
      breaking: false  # Deprecated, not removed
    - function: buildPrompt
      module: src/dashboard/hooks/useActionRunner.ts
      breaking: false  # Fallback retained
  patterns_deprecated:
    - grep: "buildStartupPrompt\\("
      replacement: "buildPromptFromEnvelope(envelope)"
    - grep: "buildStartupContext\\("
      replacement: "resolveContext() API call"
  files_affected:
    - glob: "src/dashboard/lib/chat/startup-context.ts"
    - glob: "src/dashboard/lib/chat/context-envelope.ts"    # NEW
    - glob: "src/dashboard/app/api/chat/resolve-context/route.ts"  # NEW
    - glob: "src/dashboard/hooks/useActionRunner.ts"
    - glob: "src/dashboard/components/FloatingChat.tsx"
    - glob: "src/dashboard/lib/dispatch-escalation.ts"
    - glob: "src/dashboard/hooks/useCliChat.ts"
    - glob: "src/dashboard/app/api/cli/route.ts"
```

---

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-161: Chat Context Injection Optimization**.

Read the full ADR: `docs/decisions/ADR-161-chat-context-injection-optimization.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-161-context-injection", description="Implementing ADR-161: Chat Context Injection Optimization")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-161-context-injection", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-161 team.
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

**Team name**: `adr-161-context-injection`

#### Phase 1: Types & API
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `ContextEnvelope` interface, budget constants (`BUDGET_MINIMAL=200`, `BUDGET_STANDARD=800`, `BUDGET_RICH=2000`), and `estimateTokens()` utility (chars/4 approximation) | `src/dashboard/lib/chat/context-envelope.ts` |
| 1.2 | developer | high | Create `resolve-context` API route — parse page path to hub+skill, read SKILL.md (first 200 chars), read augur.yaml actions list, call context_manager page tools resolution, assemble ContextEnvelope within budget | `src/dashboard/app/api/chat/resolve-context/route.ts` |
| 1.3 | developer | medium | Create `buildPromptFromEnvelope()` — priority-sorted section assembly with budget truncation (cut priority 1 first, preserve priority 5 always) | `src/dashboard/lib/chat/context-envelope.ts` |

#### Phase 2: Dispatch Wiring (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Wire `runChat()` — call resolve-context (standard), pass envelope to openChat, build startup prompt from envelope instead of buildStartupPrompt() | `src/dashboard/hooks/useActionRunner.ts` |
| 2.2 | developer | medium | Wire `runOneshot()` — call resolve-context (minimal), pass envelope to bubble spawn, build oneshotPrompt from envelope | `src/dashboard/hooks/useActionRunner.ts` |
| 2.3 | developer | medium | Wire `runIde()` — call resolve-context (rich), include skill context in adapted prompt | `src/dashboard/hooks/useActionRunner.ts` |
| 2.4 | developer | medium | Wire dispatch-escalation — re-resolve context before Tier 2 and Tier 3 escalation, check if page changed since Tier 1 | `src/dashboard/lib/dispatch-escalation.ts` |

#### Phase 3: Navigation Refresh (depends on Phase 2)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add usePathname() listener in FloatingChat — on navigation, call resolve-context, if hub changed send system command with new context summary, throttle to 1 per 10s | `src/dashboard/components/FloatingChat.tsx`, `src/dashboard/hooks/useCliChat.ts` |

#### Phase 4: Cleanup
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Add `@deprecated` JSDoc to `buildStartupPrompt()` and `buildStartupContext()`, update `handleStartAction` in cli/route.ts to populate chat_session.json from envelope when available | `src/dashboard/lib/chat/startup-context.ts`, `src/dashboard/app/api/cli/route.ts` |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | validator | low | Unit tests for ContextEnvelope assembly — budget truncation, priority ordering, edge cases (no skill, no action) |
| 5.2 | validator | low | Unit tests for resolve-context API — valid page, missing skill, action resolution |
| 5.3 | validator | medium | Integration test: full action→resolve-context→CLI flow, verify agent receives structured context |
| 5.4 | validator | low | Run all tests: `npm run build`, verify no regressions |
| 5.5 | architect | low | Verify ADR intent — envelope replaces flat strings, budget tiers match dispatch modes, navigation refresh is throttled |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`npm run build`)
- [ ] No orphaned files or broken references
- [ ] `ContextEnvelope` used by all 4 dispatch paths (fire, oneshot, chat, ide)
- [ ] resolve-context API returns within 50ms for local reads
- [ ] Budget truncation preserves high-priority sections, cuts low-priority first
- [ ] Navigation refresh fires max 1 per 10s
- [ ] Escalation tiers re-resolve context (no stale pages)
- [ ] `buildStartupPrompt()` marked deprecated
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-161-chat-context-injection-optimization.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
