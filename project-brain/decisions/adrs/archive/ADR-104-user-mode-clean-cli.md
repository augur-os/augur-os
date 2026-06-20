---
status: Implemented
date: '2026-02-15'
deciders:
- Project lead
related: []
hub: null
tags:
- user
- mode
- clean
- cli
- reduced
superseded_by: null
---

# ADR-104: User Mode — Clean CLI with Reduced Cognitive Pressure

**Implementation Date**: 2026-02-15
**Supersedes**: ADR-047 Phase 5 (chat bubble parsing approach)

## Context

ADR-047 introduced a chat bubble view for operation (USER) mode that attempted to parse raw PTY output into structured chat messages. After extensive iteration, this approach proved fundamentally fragile:

- Claude Code uses **cursor positioning** (`\x1b[nG`, `\x1b[row;colH`) for rendering text, which destroys word boundaries when stripped
- **Spinner animations** (Kneading..., Recombobulating...) render character-by-character via cursor repositioning, producing fragments that are nearly impossible to filter reliably
- **Command echoes**, prompt characters (`●`, `❯`), status bars, and stats text all leak through despite dozens of regex patterns
- The terminal (xterm.js) already handles all of this perfectly — it was built for it

Meanwhile, the terminal view in DEVELOPMENT mode renders Claude Code output flawlessly. The problem is not the data — it's the attempt to re-parse what a terminal already handles.

**Key insight**: Users don't need a different *rendering engine* — they need a different *UI wrapper* around the same clean terminal output. Cognitive pressure comes from too many controls, developer jargon, and unfamiliar UI elements — not from the terminal itself.

## Decision

**Replace the chat bubble parser with a clean terminal view wrapped in a simplified UI shell.** User mode will show the same xterm.js terminal as dev mode but with:

### 1. Simplified Header
| Element | Dev Mode | User Mode |
|---------|----------|-----------|
| Mode toggle | BUILDER badge | USER badge (keep) |
| CLI selector | Full dropdown (7 CLIs) | Hidden — label says "Assistant" (keep) |
| PID badge | Shown | Hidden |
| View toggle (chat/terminal) | Shown | **Removed** — always terminal |
| Expand/minimize | Shown | Shown |
| Close | Shown | Shown |

### 2. Clean Terminal Container
- Same xterm.js terminal, same SSE stream, same PTY — zero parsing
- **Terminal chrome overlay**: a subtle top gradient that fades the Claude Code startup banner (pixel art, version info) so it doesn't overwhelm non-technical users
- `disableStdin: true` — keyboard input goes through the input bar, not the terminal directly
- Scroll position auto-follows new output (already default)

### 3. Simplified Input Bar
| Element | Dev Mode | User Mode |
|---------|----------|-----------|
| Input field | "Type a command..." | "Message..." (keep) |
| File attach button | Shown | Shown |
| Send button | Shown | Shown |
| Send shortcut hint | Shown | Hidden |
| Actions button | "MCP Tools" + count | "Actions" (simplified label, keep) |
| Help button | Shown | Shown |
| Magic button | Shown | Hidden |
| Data browser | Shown | **Hidden** (already done) |
| Page context indicator | `/lifestyle/movies` | Hidden |

### 4. Overlay Cards (Optional Enhancement — Phase 2)
Instead of parsing PTY text, detect interactive moments via **pattern matching on the raw stream** and show overlay cards *on top of* the terminal:

- **Tool approval**: When `Allow .+ to .+\?` detected in stream, show a floating card with Allow/Deny buttons — clicking sends `y\n` or `n\n` to PTY
- **Progress**: When percentage pattern detected, show a subtle progress pill in the header
- **Errors**: When `exit code [1-9]` detected, show a toast notification with Retry button

These overlays are **additive** — they don't replace the terminal output, they augment it. If detection fails, the user still sees the prompt in the terminal and can type `y`/`n` directly.

### 5. Welcome State
When no CLI is running yet, show a clean welcome screen:
- "Ask me anything" heading
- 3 suggested action pills (page-contextual, already built)
- Auto-start default CLI on first message (already implemented)

## Architecture

```
USER MODE (new):
  FloatingChat
  ├── SimplifiedHeader (mode toggle, "Assistant" label, expand/close)
  ├── xterm.js terminal (same as dev mode, full PTY rendering)
  │   └── Optional: overlay cards for approvals/progress/errors
  ├── SuggestedActions (when no messages yet)
  └── SimplifiedInputBar (message field, attach, send, actions)

DEV MODE (unchanged):
  FloatingChat
  ├── FullHeader (mode toggle, CLI selector, PID, view toggle, controls)
  ├── xterm.js terminal OR ChatBubbleView (user choice)
  ├── DataBrowser, McpTools, Magic
  └── FullInputBar (all controls)
```

### What Gets Removed
- `ChatBubbleView` component — no longer used as default in user mode
- `PtyStreamParser` class — no longer needed for rendering (kept only if overlay cards in Phase 2 need it)
- All the fragile ANSI parsing, line buffering, CLI chrome detection, spinner filtering
- The `chatView` state toggle in user mode (always terminal)

### What Gets Kept
- `ChatBubbleView` remains available in dev mode as an option (view toggle)
- `PtyStreamParser` stays in codebase for potential Phase 2 overlay use
- All the xterm.js infrastructure (`useXtermTerminal`, SSE streaming)
- Suggested actions, mode toggle, actions button

## Implementation

### Phase 1: Clean Terminal in User Mode (Core)
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | frontend | medium | Remove chatView toggle in user mode — always render terminal container instead of ChatBubbleView | `src/dashboard/components/FloatingChat.tsx` |
| 1.2 | frontend | medium | Hide dev-only header elements (PID badge, view toggle, magic button, page context, send shortcut hint) when `isOperationMode` | `src/dashboard/components/FloatingChat.tsx` |
| 1.3 | frontend | low | Add subtle CSS gradient overlay on terminal top (fades startup banner) | `src/dashboard/components/FloatingChat.tsx` |
| 1.4 | frontend | low | Show welcome state with suggested actions when CLI not yet started | `src/dashboard/components/FloatingChat.tsx` |

### Phase 2: Overlay Cards (Enhancement)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Create `ToolApprovalOverlay` — floating card that detects approval prompts in raw stream and shows Allow/Deny buttons | `src/dashboard/components/chat/ToolApprovalOverlay.tsx` |
| 2.2 | frontend | medium | Create `ProgressOverlay` — subtle header pill showing progress percentage | `src/dashboard/components/chat/ProgressOverlay.tsx` |
| 2.3 | frontend | low | Create `ErrorToast` — toast notification for CLI errors with Retry button | `src/dashboard/components/chat/ErrorToast.tsx` |

### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Verify user mode renders terminal correctly, no regressions in dev mode |
| V.2 | validator | low | Test mode toggle switches between simplified and full UI |
| V.3 | architect | low | Verify ADR intent — user mode is visually clean and non-intimidating |

### Completion Criteria
- [x] User mode shows clean terminal output (same as dev mode xterm.js)
- [x] No chat bubble parsing in the rendering path
- [x] Dev-only controls hidden in user mode
- [x] Mode toggle works correctly between simplified and full UI
- [x] Welcome state shows when CLI not started
- [x] All existing dev mode features unaffected
- [x] ADR status updated to Accepted

## Consequences

### Positive
- **Zero parsing bugs** — xterm.js handles all terminal rendering natively
- **Immediate fix** — removes hundreds of lines of fragile regex-based parsing
- **Consistent output** — user sees exactly what the terminal produces, no data loss
- **Maintainable** — no ongoing pattern maintenance as Claude Code output evolves
- **Phase 2 overlays are additive** — they enhance but never block interaction

### Negative
- **Less "chat-like"** — terminal output is not as polished as a native chat UI
- **Terminal aesthetics** — some users may find terminal text less friendly (mitigated by clean UI wrapper and optional overlays)
- **Startup banner visible** — Claude Code's pixel art header shows briefly (mitigated by gradient fade)

### Neutral
- `ChatBubbleView` and `PtyStreamParser` remain in codebase — available for dev mode and potential future use
- The suggested actions, input bar, and mode system are unchanged
- xterm.js is already loaded and working — no new dependencies

## Alternatives Considered

### Alternative 1: Continue Improving Chat Bubble Parser
Rejected. After 6+ iterations adding patterns for cursor positioning, spinner fragments, prompt chars, command echoes, and stats text, the approach is fundamentally fragile. Claude Code's PTY output is designed for terminal rendering, not text parsing. Each Claude Code update could break the parser.

### Alternative 2: Read xterm.js Screen Buffer Instead of Raw PTY
Parse text from `terminal.buffer.active.getLine(y)` after the terminal has processed cursor positioning. This gives clean text but introduces timing complexity (when to read? how to detect new content?) and still requires classification/filtering. More complexity for uncertain gain.

### Alternative 3: Use Claude Code's Structured Output API
If Claude Code exposed structured events (thinking, response text, tool calls) as a separate channel alongside PTY, parsing would be trivial. This doesn't exist today and depends on upstream changes we don't control.

## References

- ADR-047: Operation Mode Chatbot Experience (original chat bubble design)
- `src/dashboard/components/FloatingChat.tsx` — main chat container
- `src/dashboard/hooks/useXtermTerminal.ts` — xterm.js terminal hook
- `src/dashboard/components/chat/ChatBubbleView.tsx` — current chat bubble view
- `src/dashboard/lib/chat/ptyStreamParser.ts` — current PTY parser (to be deprecated)
