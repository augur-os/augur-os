---
status: Implemented
date: '2026-02-24'
deciders:
- Augur Team
related:
- ADR-130 (Action Button Dispatch Modes)
- ADR-134 (Dispatch Escalation)
hub: null
tags:
- chat
- dispatch
- mode
superseded_by: null
---

# ADR-144: Chat Dispatch Mode

## Context

ADR-130 established 4 dispatch modes: `fire`, `oneshot`, `ide`, `modal`. In practice, the most common user interaction pattern — multi-turn conversational work inside the dashboard — has no dedicated mode.

Current workarounds:
- **oneshot** can route long results to FloatingChat, but the conversation is an afterthought — the LLM runs first, user reacts second
- **ide** opens an external IDE (Claude Desktop, Antigravity) where the agent edits files autonomously — wrong model for advisory/brainstorming work where the user drives

The missing mode is **chat**: open the internal FloatingChat, seed it with action context (skill, page, prompt), and let the user drive a multi-turn conversation. No file editing, no external IDE, no one-shot-and-done. The user stays in the dashboard and works interactively.

This is expected to be the **highest-volume dispatch mode** — most dashboard actions are conversational (brainstorm content, review drafts, plan strategy, get advice) rather than deterministic scripts or file edits.

### Updated Dispatch Mode Map

| Mode | Runs where | Interaction model | Use case |
|------|-----------|-------------------|----------|
| `fire` | Backend script | None (toast result) | Sync data, refresh cache, publish |
| `oneshot` | Backend LLM call | Single result → inline card or chat | Quick analysis, summarize |
| **`chat`** | **Internal FloatingChat** | **Multi-turn conversation** | **Brainstorm, review, iterate, advise** |
| `ide` | External IDE | Agent edits files autonomously | Write posts, fix code, refactor |
| `modal` | Dialog overlay / scheduler | Form input, cron config, bulk ops | Schedule tasks, API config, bulk execution |

### Clarification: Modal Scope

`modal` covers more than confirmation dialogs. It's the mode for:
- **Cron-based scheduling**: Configure recurring execution (frequency, day, time)
- **Bulk operations**: Select multiple items, configure batch parameters
- **API configuration**: Set credentials, endpoints, webhook URLs
- **Parameter forms**: Any action that needs structured user input before execution

## Decision

### Add `chat` as the 5th dispatch mode

**Schema update** (`action-schema.yaml`):
```yaml
dispatch_modes:
  chat:
    description: "Open internal chat with action context for multi-turn work"
    requires_prompt: true
    schedulable_default: false
```

**Validation update**:
```yaml
dispatch: ["fire", "oneshot", "chat", "ide", "modal"]
```

### Dispatch Flow

```
User clicks action button (dispatch: chat)
    │
    ├─ 1. Build prompt from action YAML (prompt field + page context)
    │
    ├─ 2. chatStore.openChat({
    │       mode: 'auto',
    │       context: { actionId, actionName, skill, hub, page },
    │       initialPrompt: builtPrompt,
    │     })
    │
    ├─ 3. FloatingChat opens in chat view
    │     ├─ Context banner shows: "Working on: {action.label}"
    │     ├─ initialPrompt displayed as system context (not sent yet)
    │     └─ Input focused — user types first message or hits Enter to use default prompt
    │
    └─ 4. Multi-turn conversation
          ├─ Each message goes through embedded CLI (MCP tools available)
          ├─ User can refine, ask follow-ups, change direction
          └─ Chat persists in session until user closes
```

### Key Differences from Oneshot

| Aspect | oneshot | chat |
|--------|---------|------|
| **Who initiates** | System runs LLM first | User drives from the start |
| **First message** | Auto-sent prompt → result | User chooses when to send |
| **Context** | Minimal (action + page) | Rich (action + skill + page + prompt as briefing) |
| **Multi-turn** | Afterthought (only for long results) | Primary interaction model |
| **UI state** | Inline card or chat (based on result length) | Always FloatingChat from the start |

### Key Differences from IDE

| Aspect | ide | chat |
|--------|-----|------|
| **Where** | External IDE (Claude Desktop, Antigravity) | Internal FloatingChat |
| **Agent autonomy** | High — agent edits files, runs commands | Low — user drives, agent advises |
| **File editing** | Yes — primary purpose | No — conversation only |
| **Escalation tier** | Tier 2-3 (ADR-134) | N/A — no escalation needed |

### Implementation

**1. action-schema.yaml** — Add `chat` to dispatch_modes and validation

**2. useActionRunner.ts** — Add `runChat()` function:
```typescript
async function runChat(
  action: ActionDef,
  chatStore: ChatState,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): Promise<void> {
  const prompt = buildPrompt(action);
  const pageContext = typeof window !== 'undefined' ? window.location.pathname : action.page;

  chatStore.openChat({
    mode: 'auto',
    context: {
      page: pageContext,
      actionId: action.id,
      actionName: action.label,
      skill: action.skill,
      hub: action.hub,
    },
    initialPrompt: prompt,
  });

  setState({ isExecuting: false, result: null });
}
```

Add to switch statement:
```typescript
case 'chat':
  await runChat(action, chatStore, setState);
  return;
```

**3. FloatingChat.tsx / ChatBubbleView.tsx** — Wire up `initialPrompt`:
- When `initialPrompt` is set, display it as a context briefing banner above the chat input
- Auto-focus the input field
- If user presses Enter without typing, send `initialPrompt` as the first message
- If user types their own message, prepend `initialPrompt` as system context

**4. chatStore.ts** — No structural changes needed. `openChat()` already accepts `initialPrompt` and `context` — they're just unused. Wire them through.

### Example Action YAMLs

```yaml
# Brainstorm content ideas (consulting)
id: brainstorm-content
label: Brainstorm Content Ideas
description: Start a conversation to brainstorm content ideas for the client
dispatch: chat
page: /consulting/client-smb-design/content-pipeline
agents: [consultant]
prompt: |
  You are helping brainstorm content ideas for the SMB design client.
  Review the recent posts and suggest fresh topics that align with
  the brand voice and target audience.

# Review draft (career)
id: review-post-draft
label: Review Draft
description: Get interactive feedback on a LinkedIn post draft
dispatch: chat
page: /career/content
agents: [content]
prompt: |
  Review the current post draft. Provide feedback on tone, structure,
  and engagement potential. Wait for the user to share the draft or
  ask which draft to review.

# Plan weekly priorities (productivity)
id: plan-week
label: Plan My Week
description: Interactive weekly planning session
dispatch: chat
page: /productivity/eisenhower
agents: [organizer]
prompt: |
  Help the user plan their week. Review their Eisenhower matrix,
  upcoming calendar events, and pending tasks. Ask about priorities
  and energy levels before suggesting a schedule.
```

## Consequences

**Positive:**
- The most common interaction pattern (multi-turn conversation) gets a first-class dispatch mode
- Users stay in the dashboard — no context-switching to external IDEs for advisory work
- Action YAMLs clearly communicate intent: `dispatch: chat` means "this starts a conversation"
- Existing infrastructure (`initialPrompt`, `openChat`, FloatingChat) is leveraged — minimal new code

**Negative:**
- 5th dispatch mode adds complexity to the action schema
- Some existing `oneshot` actions may need reclassification to `chat`
- FloatingChat needs to handle `initialPrompt` display — minor UI work

## Migration

After implementation, audit existing actions and reclassify where appropriate:
- `oneshot` actions where users frequently follow up → `chat`
- `ide` actions that don't edit files (advisory only) → `chat`
- New actions default to `chat` unless they fit another mode's profile

## References

- [ADR-130: Action Button Dispatch Modes](ADR-130-action-button-dispatch-modes.md) — established the 4-mode system
- ADR-134: Dispatch Escalation — tiered execution for pipeline stages
- chatStore.ts — already has `initialPrompt` and `context` fields (unused)
- useActionRunner.ts — dispatch switch statement to extend
