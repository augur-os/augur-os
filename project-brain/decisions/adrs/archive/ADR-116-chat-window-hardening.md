---
status: Implemented
date: '2026-02-12'
deciders: []
related: []
hub: null
tags:
- chat
- window
- hardening
- production
- dev
superseded_by: null
---

# ADR-116: Chat Window Hardening — Production & Dev Mode

**Driver**: Manual audit of FloatingChat + ChatBubbleView
**Composite Score**: 61/100 (moderate-rebuild)
**Scope**: Global floating chat window across all dashboard pages

## Context

The chat window is the primary interaction surface for both operation-mode users (chatbot bubble) and dev-mode users (multi-agent terminal). ADR-047 established the architecture (PTY parser, 3-tier fallback, mode-aware views). This ADR hardens the implementation across all 10 dimensions with emphasis on multi-agent workflows in dev mode.

### Audit Summary

| # | Dimension | Score | Status |
|---|-----------|-------|--------|
| 1 | UI Compliance | 72 | needs-work |
| 2 | Component Coverage | 80 | passing |
| 3 | API Completeness | 65 | needs-work |
| 4 | Mode Differentiation | 75 | needs-work |
| 5 | Parser Robustness | 70 | needs-work |
| 6 | User Value | 55 | critical |
| 7 | Error Handling | 60 | needs-work |
| 8 | Accessibility | 35 | critical |
| 9 | Performance | 60 | needs-work |
| 10 | Wow Effect | 40 | critical |

### Critical Issues (Score < 50)
- **Accessibility (35)**: No ARIA roles/labels, no focus trap, no keyboard navigation, color-only status indicators, no reduced-motion support
- **Wow Effect (40)**: No markdown rendering, no code blocks, no typing animations, no voice, no conversation memory

### Needs-Work Issues (Score 50-75)
- **User Value (55)**: Suggested actions vanish after first message; no copy/share; no message search; magic button raw prompt visible
- **Error Handling (60)**: No auto-recovery from CLI crashes; no offline detection; no retry backoff
- **Performance (60)**: Unbounded message array; full re-render per parser event; no virtualization
- **API Completeness (65)**: No message persistence; no conversation export; no rate limiting
- **Parser Robustness (70)**: Single handler slot; aggressive 3s idle timeout; no ERROR state recovery
- **UI Compliance (72)**: Fixed 700px width; no responsive breakpoints; inconsistent toolbar spacing
- **Mode Differentiation (75)**: Terminal focus mode confusing in operation; MCP tools button stale-check
- **Component Coverage (80)**: Missing markdown renderer and code syntax highlighting

## Decision

Harden the chat window in 4 phases, ordered by impact. Multi-agent dev-mode workflows are prioritized alongside the production chatbot experience.

## Wow Effect: All Four Features

1. **Markdown + Code Blocks** — Render assistant messages with full CommonMark + syntax-highlighted fenced code blocks
2. **Smart Conversation Memory** — Persist threads across sessions with search, stars, and export
3. **Streaming Animations** — Character-level typing, smooth transitions, ambient thinking indicators
4. **Voice Input/Output** — Microphone button (Web Speech API) with optional TTS responses

## Implementation Plan

### Phase 1: Foundation (Accessibility + Parser Hardening)
**Target**: Accessibility 35→80, Parser 70→90

#### 1.1 Accessibility Overhaul
- Add `role="log"` and `aria-live="polite"` to messages container
- Add `aria-label` to all interactive buttons (start/stop, send, attach, view toggle, enlarge, minimize, close)
- Add `role="status"` to CLI status indicator with text alternative (not color-only)
- Implement focus trap within chat window when open (Tab cycles through interactive elements)
- Add `aria-describedby` linking prompt/approval cards to their parent message
- Support `prefers-reduced-motion`: disable `animate-bounce`, `animate-pulse`, `animate-spin`
- Add keyboard shortcuts: `Escape` closes chat (already works in terminal focus), `Tab` navigates, `Enter` on suggested actions
- Screen reader announcements for state changes (CLI started/stopped, new message, error)

#### 1.2 Parser Hardening
- **Multiple event handlers**: Change `onEvent(handler)` to `addEventListener(handler)` / `removeEventListener(handler)` pattern (array of handlers)
- **Configurable idle timeout**: Make `IDLE_TIMEOUT_MS` configurable per CLI profile (slow LLMs need 8-10s)
- **ERROR state recovery**: After ERROR, transition back to IDLE on next user message (currently stuck)
- **ANSI strip regex audit**: Test against real Claude Code, Codex, and Kimi output samples to ensure no over-stripping
- **Graceful chunk boundary handling**: Buffer partial ANSI sequences split across SSE chunks

#### 1.3 Error Handling Hardening
- Add offline/network detection: show banner when `navigator.onLine === false` or fetch fails
- CLI health polling: ping `/api/cli?cliId=X` every 30s when chat is open; auto-restart if stale
- Retry with exponential backoff for failed `sendMessage` calls (max 3 retries, 1s/2s/4s)
- Show reconnection status in header ("Reconnecting..." with spinner)

**Files touched**: `ChatBubbleView.tsx`, `FloatingChat.tsx`, `ptyStreamParser.ts`, `ErrorCard.tsx`, `SuggestedActions.tsx`, `ToolApprovalCard.tsx`, `PromptCard.tsx`, `ProgressCard.tsx`, `TerminalFallbackBanner.tsx`, `chatStore.ts`

### Phase 2: User Value + Mode Differentiation
**Target**: User Value 55→85, Mode Differentiation 75→90

#### 2.1 Markdown Rendering (Wow Effect #1)
- Install `react-markdown` + `remark-gfm` + `rehype-highlight` (plugin dep in dashboard package.json)
- Create `MarkdownMessage.tsx` component wrapping `react-markdown` with:
  - Fenced code blocks with syntax highlighting (highlight.js, dark theme)
  - Inline code with monospace background
  - Tables, lists, blockquotes styled to match GlassCard theme
  - Link sanitization (no javascript: URIs)
  - Image rendering disabled (security)
- Replace `<div className="whitespace-pre-wrap">{message.content}</div>` in `ChatMessageBubble.tsx` with `<MarkdownMessage content={message.content} />`
- Add "Copy code" button to fenced code blocks
- Add "Copy message" button on hover for any assistant message

#### 2.2 Streaming Animations (Wow Effect #3)
- Character-by-character reveal for assistant message chunks (16ms interval, ~60 chars/sec)
- Smooth height transition on message container (CSS `transition: height 200ms ease`)
- Replace bouncing dots with a subtle pulsing gradient bar for thinking state
- Add fade-in animation for new messages (`opacity 0→1` over 150ms)
- All animations respect `prefers-reduced-motion` (instant reveal, no transitions)

#### 2.3 Enhanced User Value
- **Persistent suggested actions**: Show actions strip below input always (not just on empty chat), collapsed to icons after first message
- **Copy message**: Hover reveals copy button on assistant messages; copies as markdown
- **Message search**: `Cmd+F` within chat opens inline search bar, highlights matching messages
- **Magic button cleanup**: Show a "Analyzing page..." card instead of raw prompt text; hide the prompt from message history

#### 2.4 Mode Differentiation Polish
- **Operation mode**: Hide terminal focus mode entirely (no click-to-focus on terminal pane); auto-switch back from terminal to chat after TUI content ends
- **Dev mode multi-agent**:
  - Show agent avatar/color per CLI (not just "A" for all)
  - Agent status badges in dropdown ("running", "idle", "error") with live update
  - Split-view option: show 2 agents side-by-side (half-width each) for comparison
  - Quick-switch hotkey: `Cmd+1` through `Cmd+7` to switch agents

**Files touched**: New `MarkdownMessage.tsx`, `ChatMessageBubble.tsx`, `ChatBubbleView.tsx`, `FloatingChat.tsx`, `SuggestedActions.tsx`, `chatStore.ts`

### Phase 3: Performance + API Completeness
**Target**: Performance 60→85, API 65→85

#### 3.1 Message Virtualization
- Implement windowed rendering for messages (react-window or custom IntersectionObserver-based)
- Only render messages within viewport ± 5 buffer messages
- Add scroll-to-bottom button when user scrolls up (with unread count badge)
- Limit in-memory messages to 500 (older messages available via API pagination)

#### 3.2 Render Optimization
- Memoize `ChatMessageBubble` with `React.memo` + stable key
- Debounce parser event handler (batch updates within 16ms frame)
- Lazy-load MCP tools popover content (don't mount until opened)
- Memoize `ChatSidePopover` position calculation (only update on resize, not scroll)
- Move portal position from inline style to CSS transform (GPU-accelerated)

#### 3.3 API Completeness
- **Message persistence**: `POST /api/chat/messages` — save messages to `runtime/chat/` as JSONL per session
- **Conversation history**: `GET /api/chat/history` — list recent sessions with preview
- **Message export**: `POST /api/chat/export` — export conversation as markdown file
- **Rate limiting**: Debounce stdin sends to max 1 per 200ms (prevent paste-flooding)
- **Session recovery**: On chat open, check for active session and resume (load messages from JSONL)

**Files touched**: `ChatBubbleView.tsx`, `ChatMessageBubble.tsx`, `FloatingChat.tsx`, `useCliChat.ts`, new API routes in `app/api/chat/`

### Phase 4: Smart Memory + Voice (Wow Effects #2 & #4)
**Target**: Wow Effect 40→90, Composite 61→85+

#### 4.1 Conversation Memory (Wow Effect #2)
- Persist conversation threads to `runtime/chat/threads/` as JSONL files
- Thread list sidebar (slide-in from left within chat window)
- Star/pin important messages within a thread
- Full-text search across all threads (ripgrep-powered API endpoint)
- Auto-title threads based on first user message (truncated to 50 chars)
- Thread export as markdown with metadata header

#### 4.2 Voice Input/Output (Wow Effect #4)
- Microphone button next to attach button (Web Speech API `SpeechRecognition`)
- Real-time transcription displayed in textarea as user speaks
- Visual audio level indicator (small bar animation while recording)
- Optional TTS for assistant responses (Web Speech API `SpeechSynthesis`)
- TTS toggle in chat header (speaker icon)
- Graceful degradation: hide mic button if `SpeechRecognition` unsupported

#### 4.3 UI Compliance Final Pass
- Replace fixed `w-[700px]` with responsive: `w-full sm:w-[700px]` + mobile full-screen overlay
- Add GlassCard-style `backdrop-blur` to chat window border
- Normalize toolbar spacing: consistent `gap-1.5` across all toolbar rows
- Add subtle box-shadow depth levels: minimized pill → standard → enlarged

**Files touched**: New `ThreadSidebar.tsx`, `VoiceInput.tsx`, `ChatBubbleView.tsx`, `FloatingChat.tsx`, `chatStore.ts`, new API routes

## Team Splitting

| Agent | Responsibilities | Phase |
|-------|-----------------|-------|
| **developer** (Python/API) | API routes (persistence, history, export, rate limiting), parser hardening, voice TTS endpoint | P1.2, P1.3, P3.3, P4.1 API |
| **frontend** (React/UI) | Accessibility, markdown rendering, animations, virtualization, voice UI, responsive, memory UI | P1.1, P2.1-2.4, P3.1-3.2, P4.1 UI, P4.2, P4.3 |

## Test Plan

- [ ] Accessibility: axe-core audit passes with 0 violations on chat window
- [ ] Accessibility: full keyboard navigation (Tab through all controls, Enter activates, Escape closes)
- [ ] Parser: feed 10+ real CLI output samples (Claude, Codex, Kimi) — all classified correctly
- [ ] Parser: ERROR → IDLE recovery on user message
- [ ] Parser: partial ANSI chunk handling (split escape sequence across 2 feeds)
- [ ] Markdown: renders headers, lists, code blocks, tables, links correctly
- [ ] Markdown: XSS prevention (script tags, javascript: URIs stripped)
- [ ] Streaming: character reveal at ~60 chars/sec, respects reduced-motion
- [ ] Performance: 500 messages renders in < 16ms (virtual scroll)
- [ ] Performance: no memory leak after 1000 message cycles
- [ ] Voice: mic button appears only when SpeechRecognition available
- [ ] Voice: transcription populates textarea in real-time
- [ ] Memory: thread persisted to disk, reloads on next open
- [ ] Memory: search finds messages across threads
- [ ] Mode: operation mode hides terminal focus, dev tools, PID badge
- [ ] Mode: dev mode agent switching with Cmd+1-7 hotkeys
- [ ] Mobile: chat fills viewport width on screens < 768px
- [ ] Offline: banner appears when network drops, hides on reconnect
- [ ] API: rate limiting caps stdin to 1 send per 200ms

## User Notes

Multi-agent focus: Dev mode multi-agent switching is the primary use case. Agent-specific avatars, status indicators, split-view comparison, and quick-switch hotkeys are prioritized alongside operation-mode polish.

## Consequences

- `react-markdown` + `rehype-highlight` added to dashboard dependencies (~40KB gzipped)
- `react-window` or custom virtualizer adds ~5KB
- Voice features increase Chrome permission prompts (microphone access)
- JSONL message persistence adds disk usage in `runtime/chat/` (mitigated by 14-day retention)
- Split-view in dev mode doubles the xterm.js instances (memory consideration)

## Related

- ADR-047: Operation Mode Chatbot Experience (foundation)
- ADR-035: Embedded Action Dialog
- ADR-036: Mode-Aware Navigation
- ADR-078: Magic Button & Insights
