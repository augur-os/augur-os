---
status: Implemented
date: '2026-02-03'
deciders: []
related: []
hub: null
tags:
- cli
- chat
- window
- enhancements
- resizable
superseded_by: null
---

# ADR-035: CLI Chat Window Enhancements — Resizable Terminal, Unified FAB, and Embedded Action Dialog

**Extends**: ADR-034

## Context

ADR-034 introduced a CLI-based chat window (`FloatingChat`) with file attachment support, replacing the simulated chat with a real PTY-backed terminal. Three UX gaps remain:

1. **Fixed dimensions** — The chat window is locked at 900x640px. Standard terminal width (80 columns) is more appropriate for CLI interaction, and users need the ability to enlarge the window for complex output.

2. **Two disconnected buttons** — The FAB button (`UnifiedActionsFab`) shows a static `MessageSquare` icon with no indication of whether a CLI is running. Users have no visual feedback about CLI state from the collapsed view.

3. **Separate action dialog** — The `ActionButtonModal` is a full-screen overlay independent of `FloatingChat`. When users trigger an AI action, they lose context of their running CLI session. The action dialog and terminal should be unified.

## Decision

### Enhancement 1: Resizable Chat Window with Standard Terminal Width

- Default dimensions changed from `w-[900px] h-[640px]` to `w-[700px] h-[600px]` (~80 columns, ~24 rows at standard xterm.js font size)
- Enlarge toggle button in the header switches between 600px (standard) and 960px (enlarged, ~48 rows) height
- Width stays fixed at 700px
- `max-h-[calc(100vh-3rem)]` prevents overflow on small screens
- xterm.js `ResizeObserver` + `FitAddon` automatically handles PTY resize — no server changes needed

**Future phase**: Replace enlarge toggle with drag-to-resize handle.

**Files modified**:
- `src/dashboard/lib/stores/chatStore.ts` — Added `isEnlarged` state + `toggleEnlarged()` action
- `src/dashboard/components/FloatingChat.tsx` — Dynamic dimensions, enlarge button (Maximize2/Minimize2 icon)

### Enhancement 2: Unified FAB Button with CLI Status Badge

Evaluated three approaches:

| Approach | Pros | Cons |
|----------|------|------|
| **A: Two icons** | Visual state indicator | Same position, different icon = confusing |
| **B: Single icon** | Predictable | No state indication |
| **C: Badge** (chosen) | Consistent icon + clear state; matches existing patterns | Slightly more complex rendering |

**Chosen**: Option C — `MessageSquare` icon always visible, green pulse badge overlay (`bg-emerald-500`, `animate-ping`) when `cliProcess.status === 'running'`. Consistent with the status dot pattern in FloatingChat's minimized pill and CLI selector dropdown.

**File modified**: `src/dashboard/components/UnifiedActionsFab.tsx`

### Enhancement 3: Embedded Action Dialog (Replaces ActionButtonModal)

`ActionButtonModal` is fully replaced. All LLM/IDE action button clicks now route to an embedded `ActionDialogView` inside `FloatingChat`.

**Routing**: `useActionRunner.ts` sets `chatStore.embeddedAction` and `chatStore.chatView = 'action-dialog'`, then ensures FloatingChat is open. No branching on CLI state.

**View switching**: `FloatingChat` supports two views via `chatView: 'terminal' | 'action-dialog'`. The terminal div stays always mounted with `display: none/block` (not conditional rendering) to prevent xterm.js disposal and SSE stream reconnection.

**Action buttons in embedded dialog**:

| Button | Behavior | Active CLI |
|--------|----------|------------|
| **Continue with {activeCli}** (primary) | Sends full prompt to active CLI stdin | Stays running |
| **Send to IDE** | Calls `useIdeBridge.sendPrompt()` | Stays running |
| **Copy to Clipboard** | Copies full prompt | Stays running |
| **Send to Other CLI** | Opens CLI selector; exits active CLI, starts selected CLI, sends prompt | Old stops, new starts |

**When no CLI is running**: "Continue with CLI" auto-starts the default CLI (claude-code) and sends the prompt. The UI is identical regardless of CLI state.

**Files created**: `src/dashboard/components/ActionDialogView.tsx`

**Files modified**:
- `src/dashboard/lib/stores/chatStore.ts` — Added `chatView`, `embeddedAction`, `setChatView()`, `setEmbeddedAction()`
- `src/dashboard/components/FloatingChat.tsx` — View switching, action dialog callbacks
- `src/dashboard/hooks/useActionRunner.ts` — Routes all LLM/IDE actions to embedded view
- `src/dashboard/components/ProductizationTaskRow.tsx` — Routes refactor actions through chatStore
- `src/dashboard/components/GlobalShell.tsx` — Removed `<ActionButtonModal />`

**Files deleted**:
- `src/dashboard/components/ActionButtonModal.tsx`
- `src/dashboard/lib/stores/actionModalStore.ts`
- `src/dashboard/components/AgentSelector.tsx` (dead code after deletion)
- `src/dashboard/components/AgentSelector.test.tsx` (dead code after deletion)
- `src/dashboard/lib/stores/actionModalStore.test.ts` (dead code after deletion)

## Testing & Verification

| Test | Expected Result |
|------|-----------------|
| Click enlarge button | Height toggles between 600px and 960px, xterm.js re-fits |
| Enlarge on small viewport | Window clamped to `100vh - 3rem` |
| Start CLI + check FAB | Green pulse badge appears on FAB |
| Stop CLI + check FAB | Badge disappears |
| Trigger LLM action (CLI running) | Embedded dialog opens in FloatingChat |
| Trigger LLM action (no CLI) | Embedded dialog opens, FloatingChat auto-opens |
| Click "Continue with CLI" (CLI running) | Prompt sent to CLI stdin, view returns to terminal |
| Click "Continue with CLI" (no CLI) | Default CLI starts, prompt sent, view returns to terminal |
| Click "Send to IDE" | Prompt sent to IDE, CLI stays running |
| Click "Copy to Clipboard" | Prompt copied, CLI stays running |
| Click "Send to Other CLI" | Active CLI exits, new CLI starts, prompt sent |
| Click "Back" in dialog | View returns to terminal, no action taken |

## Consequences

### Positive
- Unified experience: CLI terminal and AI actions in one window
- Standard terminal width improves CLI output readability
- FAB badge provides at-a-glance CLI status
- No full-screen modal interruption for AI actions
- Simpler architecture: two stores merged into one, fewer components

### Negative
- `ActionDialogView` is simplified compared to `ActionButtonModal` — no eval framework, execution mode toggle, or agent selector (these can be added later)
- "Send to Other CLI" flow involves multiple async operations that could fail mid-sequence
- Dead code remains (`ExecutionModeToggle`, `useContextSwitcher`, `promptLoader`) that was only used by the deleted modal

### Migration
- `ActionButtonModal.tsx` — Deleted; replaced by `ActionDialogView.tsx` embedded in `FloatingChat`
- `actionModalStore.ts` — Deleted; state moved to `chatStore.ts`
- `useActionRunner.ts` — No longer imports `actionModalStore`; routes directly through `chatStore`
- `ProductizationTaskRow.tsx` — Updated to route through `chatStore` instead of `actionModalStore`
- `GlobalShell.tsx` — `<ActionButtonModal />` removed
- `promptLoader.ts` — `PromptMeta` type defined locally (was imported from deleted `actionModalStore`)
