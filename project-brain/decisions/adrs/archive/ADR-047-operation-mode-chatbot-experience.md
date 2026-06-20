---
status: Implemented
date: '2026-02-06'
deciders:
- Augur Team
related: []
hub: null
tags:
- operation
- mode
- chatbot
- experience
superseded_by: null
---

# ADR-047: Operation Mode Chatbot Experience

**Updated**: 2026-02-10
**Extends**: ADR-036 (Chat vs Action Bar Partition)

## Context

The FloatingChat window currently presents the same terminal-centric UI regardless of mode. In **operation mode**, the user — who may not be a developer — sees:

1. **Raw xterm.js terminal** with CLI process output, escape codes, and tool-call logs
2. **MCP Tools popover** listing all ~59 tools (including `file-read`, `switch-mcp-context`, `get-mcp-diagnostics`, etc.) with no filtering
3. **CLI selector** showing 7 agent backends (claude, codex, gemini, etc.)
4. **Developer jargon** throughout: "MCP", "chain", "PTY", process status indicators

This is intimidating for operation mode. Users familiar with ChatGPT, Gemini, or standard chatbots expect:
- A clean message thread (bubbles/cards), not a terminal
- Discoverable actions as buttons or suggestions, not raw tool names
- Natural language throughout — no protocol names or system internals

Meanwhile, `mcp_tool_groups.yaml` v2.0 already defines page-specific tool scoping, but this config is **not enforced** — the `/api/mcp/tools/list` endpoint returns all tools unfiltered.

## Decision

Transform the operation-mode chat into a **chatbot-first experience** with three layers of change:

### Layer 1: Visual — Chat Thread Instead of Terminal

| Element | Current (Both Modes) | Operation Mode (New) | Dev Mode (Unchanged) |
|---------|---------------------|---------------------|---------------------|
| Message display | xterm.js terminal | Chat bubbles (user right, assistant left) | xterm.js terminal |
| Input | Textarea → PTY stdin | Chat input bar with send button | Textarea → PTY stdin |
| Tool execution | Visible in terminal stream | Hidden; show result as a card/summary | Visible in terminal |
| Thinking/loading | Terminal cursor blink | Typing indicator (three dots) | Terminal cursor |
| Errors | Raw stderr in terminal | Friendly error card with retry button | Raw stderr |

**New ChatView type**: Add `'chat'` to the existing `ChatView` union (`'terminal' | 'action-dialog' | 'actions-list' | 'chat'`). Operation mode defaults to `'chat'`; dev mode defaults to `'terminal'`.

**Message format**: Introduce a `ChatMessage` type:
```typescript
type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  toolCalls?: { name: string; result: string; status: 'success' | 'error' }[];
  attachments?: FileAttachment[];
};
```

The underlying CLI process still runs — the chat view is a **presentation layer** that parses CLI output into structured messages. Users can always switch to terminal view via the mode toggle.

### Layer 2: Commands — Mode-Aware & Page-Aware Filtering

**Enforce `mcp_tool_groups.yaml` in the API:**

```
GET /api/mcp/tools/list?page=/career&mode=operation
```

**Filtering rules:**

| Filter | Logic |
|--------|-------|
| Page-aware | Only return tools in the `pages[pathname].groups` from `mcp_tool_groups.yaml` + `core_tools` |
| Mode-aware | In operation mode, hide infrastructure tools (see exclusion list below) |
| User-friendly names | Map tool IDs to display labels (e.g., `execute-chain` → "Run Workflow") |

**Operation mode exclusion list** (tools hidden from the popover):

| Category | Hidden Tools |
|----------|-------------|
| MCP internals | `switch-mcp-context`, `preload-mcp-context`, `get-mcp-context-stats`, `list-mcp-tools`, `get-mcp-diagnostics`, `test-mcp-connection` |
| File system | `file-read`, `file-write`, `file-list`, `file-search`, `file-read-multi`, `file-info` |
| System/config | `get-path-config`, `update-path-config`, `cleanup-path`, `get-config` |
| Developer tools | `get-ide-status`, `get-chat-session`, `save-performance-metric`, `get-performance-metrics` |
| Agent internals | `load-module`, `list-services` |

**Operation mode visible tools** (examples per page):

| Page | Visible Actions |
|------|----------------|
| /career | "Search Jobs", "Update Resume", "Prep Interview" |
| /health | "Log Meal", "Check Metrics", "Suggest Workout" |
| /finance | "Review Budget", "Track Expense", "Generate Report" |
| / (Home) | "Check Inbox", "Review Notifications", "Quick Task" |

These map to existing `dashboard.yaml` actions and `mcp_tool_groups.yaml` page configs.

### Layer 3: Interaction — Chatbot Patterns

**Replace "MCP Tools" button with contextual suggestions:**

| Current | New (Operation Mode) |
|---------|---------------------|
| "MCP Tools" button → flat list of 59 tools | "Actions" button → page-scoped action cards with icons and descriptions |
| User types raw tool name | User clicks action card or types natural language |
| No onboarding | First-open shows 2-3 suggested actions based on current page |

**Rename UI labels:**

| Current Label | Operation Mode Label |
|---------------|---------------------|
| MCP Tools | Actions |
| CLI Selector | Assistant |
| Process: running | (hidden — no process indicator) |
| Terminal | Chat |
| Execute Chain | Run Workflow |
| Data Context | (hidden) |

**Suggested actions strip**: Below the chat input, show 2-3 pill buttons for the most common actions on the current page. These rotate based on time of day and usage patterns.

**CLI selector simplification**: In operation mode, show only the primary CLI (claude) and hide the multi-agent selector. Advanced users can switch to dev mode to access other agents.

### Layer 4: Interactive Terminal Scenarios in Chat View

The hardest design challenge: the underlying CLI process is interactive. Claude Code, Codex, and other agents ask questions, request confirmations, stream partial output, and emit errors — all through raw PTY. The chat view must handle every scenario without dropping the user into a raw terminal.

**Current state**: Zero structured parsing. Everything flows as raw bytes through xterm.js. The `outputBuffer` strips ANSI codes but does not parse structure. There is no concept of "the agent is asking a question" vs "the agent is thinking" vs "the agent hit an error."

#### 4.1 Stream Parser Architecture

Introduce a **PTY Stream Parser** (`lib/chat/ptyStreamParser.ts`) that sits between the SSE stream and the ChatBubbleView. It maintains a state machine:

```
┌─────────┐    raw bytes    ┌──────────────┐   ChatMessage[]   ┌────────────────┐
│  PTY    │ ──────────────→ │ Stream Parser │ ────────────────→ │ ChatBubbleView │
│ (SSE)   │                 │ (state machine│                   │                │
└─────────┘                 └──────────────┘                   └────────────────┘
                                   │
                                   ↓ fallback
                            ┌──────────────┐
                            │ Raw Terminal  │  (escape hatch)
                            │ (xterm.js)   │
                            └──────────────┘
```

**Parser states:**

| State | Detection Heuristic | Chat View Renders |
|-------|--------------------|--------------------|
| `THINKING` | Output starts with tool-call markers, no user-facing text yet | Typing indicator (animated dots) |
| `STREAMING_RESPONSE` | Continuous text output without prompt markers | Assistant bubble, live-updating |
| `AWAITING_INPUT` | Line ends with `?`, `(y/n)`, `>`, `:`, or known prompt patterns | Interactive prompt card (see 4.2) |
| `TOOL_EXECUTING` | Tool name + spinner/progress markers detected | Collapsible "Working on..." card |
| `ERROR` | stderr markers, stack traces, known error patterns | Error card (see 4.4) |
| `IDLE` | No output for >2s after completion signal | Ready state, show suggested actions |

**Detection patterns** (regex-based, tuned per CLI):

```typescript
const PROMPT_PATTERNS = [
  /\?\s*$/,                          // Ends with ?
  /\(y\/n\)\s*$/i,                   // (y/n) confirmation
  /\(Y\/n\)\s*$/,                    // (Y/n) with default
  /\[yes\/no\]\s*$/i,                // [yes/no]
  />\s*$/,                           // Bare prompt >
  /:\s*$/,                           // Ends with colon (input expected)
  /\d+\.\s+.+\n.*\d+\.\s+/,         // Numbered list (multi-choice)
  /Press Enter to continue/i,        // Continuation prompt
  /Do you want to/i,                 // Claude Code tool approval
  /Allow .+ to run/i,               // Permission request
  /Enter .+ :/i,                    // Text input request
];

const ERROR_PATTERNS = [
  /Error:/i,
  /FATAL/,
  /panic:/,
  /Traceback \(most recent/,        // Python
  /at .+\(.+:\d+:\d+\)/,            // JS stack trace
  /Permission denied/i,
  /command not found/,
  /Connection refused/i,
  /ECONNREFUSED/,
  /ENOENT/,
  /exit code [1-9]/i,
];
```

#### 4.2 Interactive Prompts → Inline Prompt Cards

When the parser detects `AWAITING_INPUT`, render an **Inline Prompt Card** instead of expecting the user to type into a terminal:

**Yes/No Confirmations:**
```
┌─────────────────────────────────────────────┐
│ 🤖 Assistant                                │
│                                             │
│ I'd like to update your resume with the     │
│ new job description. Should I proceed?      │
│                                             │
│  ┌─────────┐  ┌──────────┐                  │
│  │   Yes   │  │    No    │                  │
│  └─────────┘  └──────────┘                  │
└─────────────────────────────────────────────┘
```

**Multi-Choice Questions:**
```
┌─────────────────────────────────────────────┐
│ 🤖 Assistant                                │
│                                             │
│ Which format do you want for the report?    │
│                                             │
│  ○ PDF document                             │
│  ○ Markdown file                            │
│  ○ Email draft                              │
│  ○ Summary only                             │
│                                             │
│          ┌──────────┐                       │
│          │  Select  │                       │
│          └──────────┘                       │
└─────────────────────────────────────────────┘
```

**Free-Text Input:**
```
┌─────────────────────────────────────────────┐
│ 🤖 Assistant                                │
│                                             │
│ What company name should I use for the      │
│ cover letter?                               │
│                                             │
│  ┌───────────────────────────────────┐      │
│  │ Type your answer...               │      │
│  └───────────────────────────────────┘      │
│          ┌──────────┐                       │
│          │  Submit  │                       │
│          └──────────┘                       │
└─────────────────────────────────────────────┘
```

**Implementation**: When user clicks a button or submits text, the chat view sends the corresponding keystrokes to the PTY via the existing `sendRawKey` API (same mechanism as terminal focus mode, but through structured UI).

```typescript
// User clicks "Yes" on a y/n prompt
async function handlePromptResponse(response: string) {
  await fetch(`/api/cli?action=sendRawKey`, {
    method: 'POST',
    body: JSON.stringify({ cliId, key: response + '\r' })
  });
  // Parser transitions: AWAITING_INPUT → THINKING or STREAMING_RESPONSE
}
```

#### 4.3 Tool Approval → Consent Cards

Claude Code and other agents frequently ask: *"Do you want me to run [tool]?"* These are a special case of interactive prompts that must be clearly surfaced.

**Tool Approval Card:**
```
┌─────────────────────────────────────────────┐
│ 🔧 Action Required                         │
│                                             │
│ The assistant wants to:                     │
│ ┌─────────────────────────────────────────┐ │
│ │ 📄 Read file: ~/Documents/resume.pdf   │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│  ┌───────────┐  ┌──────────┐  ┌─────────┐  │
│  │  Allow    │  │  Deny    │  │ Always  │  │
│  └───────────┘  └──────────┘  └─────────┘  │
└─────────────────────────────────────────────┘
```

**Detection**: Match patterns like `Do you want to`, `Allow .+ to`, `Tool: .+`, Claude Code's specific permission format. Maps to the existing `ExecutionConsentModal` pattern but rendered inline in chat bubbles.

**"Always Allow" option**: Sends the trust command to the CLI (e.g., Claude Code's `--dangerously-skip-permissions` or per-tool trust), persisted in session.

#### 4.4 Errors → Friendly Error Cards

Raw stderr in a terminal is meaningful to developers. In chat view, errors are translated into actionable cards.

**Error Severity Classification:**

| Severity | Detection | Chat View Rendering |
|----------|-----------|---------------------|
| **Fatal** | Process exit code > 0, `FATAL`, `panic:` | Red card with error summary + "Restart" button |
| **Actionable** | `Permission denied`, `not found`, `Connection refused` | Orange card with explanation + suggested fix |
| **Warning** | `Warning:`, `deprecated`, non-blocking issues | Yellow inline note within assistant message |
| **Noise** | Debug logs, verbose output, ANSI garbage | Hidden entirely — not shown in chat view |

**Fatal Error Card:**
```
┌─────────────────────────────────────────────┐
│ ❌ Something went wrong                     │
│                                             │
│ The assistant couldn't complete the task.   │
│ Connection to the service was refused.      │
│                                             │
│  ┌──────────┐  ┌────────────────┐           │
│  │  Retry   │  │ Show Details ▸ │           │
│  └──────────┘  └────────────────┘           │
└─────────────────────────────────────────────┘
```

**"Show Details"** expands to show the raw error text (sanitized — PII/paths redacted using existing `stripPII.ts` and `security.ts`). Power users get context without being overwhelmed by default.

**Retry behavior**: Re-sends the last user message to the PTY. If the process crashed, spawns a new CLI process first.

#### 4.5 Long-Running Operations → Progress Cards

Some operations (file processing, API calls, chain execution) take 10-60+ seconds. Terminal shows a spinner or streaming dots. Chat view needs better feedback.

**Progress Card:**
```
┌─────────────────────────────────────────────┐
│ ⏳ Working on it...                         │
│                                             │
│ Analyzing your calendar for next week       │
│ ████████████░░░░░░░░ 60%                    │
│                                             │
│ Step 2 of 3: Checking conflicts             │
│                                             │
│          ┌──────────┐                       │
│          │  Cancel  │                       │
│          └──────────┘                       │
└─────────────────────────────────────────────┘
```

**Progress detection**: Parse percentage patterns (`\d+%`), step indicators (`Step \d+ of \d+`), and known tool output formats. When no structured progress is available, show an indeterminate animation with the last meaningful text line.

**Cancel**: Sends SIGINT (`Ctrl+C`) to the PTY, then shows "Cancelled" status on the card.

#### 4.6 Unparseable Output → Graceful Fallback

The parser will encounter output it cannot classify. **The golden rule: never lose user information.**

**Fallback strategy (3 tiers):**

| Tier | Condition | Behavior |
|------|-----------|----------|
| 1. Best effort | Parser has ~70%+ confidence in classification | Render as the detected type (bubble, card, etc.) |
| 2. Raw text block | Output doesn't match any pattern but is readable | Render as monospace text block inside assistant bubble |
| 3. Terminal escape hatch | Output contains heavy ANSI, TUI rendering, or interactive cursors | Auto-switch to xterm.js terminal view with a banner: *"Switched to terminal view for this response. [Back to Chat]"* |

**Tier 3 triggers** (auto-switch to terminal):
- Cursor movement escape sequences (TUI apps like `vim`, `htop`)
- Screen clear / alternate buffer activation
- More than 5 unparseable lines in sequence
- Claude Code's Ink-based interactive UI elements

**Banner after auto-switch:**
```
┌─────────────────────────────────────────────┐
│ 💻 Showing terminal view for this response  │
│                              [Back to Chat] │
└─────────────────────────────────────────────┘
│                                             │
│  (xterm.js terminal renders here)           │
│                                             │
```

When the interaction completes, the chat view resumes automatically for the next exchange.

#### 4.7 Multi-Turn Conversations → Thread Continuity

Chatbot users expect a scrollable history. The current terminal scrollback is raw — mixing user input, tool calls, system messages, and output.

**Chat history structure:**

```typescript
type ChatThread = {
  messages: ChatMessage[];
  // Each message can contain nested interactive elements
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  // Interactive elements rendered within the message
  promptCard?: PromptCard;       // y/n, multi-choice, text input
  toolApproval?: ToolApproval;   // consent card
  errorCard?: ErrorCard;         // error with retry
  progressCard?: ProgressCard;   // long-running operation
  toolCalls?: ToolCallSummary[]; // collapsed tool execution summaries
  attachments?: FileAttachment[];
  // State tracking
  status: 'complete' | 'streaming' | 'awaiting_input' | 'error';
};
```

**Resolved prompts**: After a user answers an interactive prompt, the card collapses to show the answer inline:
```
🤖 Which format for the report?
   ✓ You selected: PDF document
```

This keeps history clean and scannable.

#### 4.8 Parser Configuration Per CLI

Different CLI agents (Claude Code, Codex, Gemini CLI) have different output formats. The parser uses a **CLI profile** system:

```typescript
type CliParserProfile = {
  cliId: string;                    // 'claude' | 'codex' | 'gemini' | etc.
  promptPatterns: RegExp[];         // Override/extend default patterns
  errorPatterns: RegExp[];
  toolApprovalPattern?: RegExp;     // CLI-specific approval format
  progressPattern?: RegExp;         // CLI-specific progress format
  streamingDelimiter?: string;      // How the CLI separates messages
  supportsStructuredOutput: boolean;// Can output JSON instead of text
};
```

**Initial profiles**: Ship with `claude` and `codex` profiles. Other CLIs fall back to generic pattern matching. Profiles stored in `config/dashboard/cli_parser_profiles.yaml`.

## Implementation Plan

### Phase 1: PTY Stream Parser (Core Engine) — DONE
1. ~~Build `ptyStreamParser.ts` state machine with `THINKING | STREAMING_RESPONSE | AWAITING_INPUT | TOOL_EXECUTING | ERROR | IDLE` states~~
2. ~~Implement regex-based detection for prompts, errors, progress, tool approvals~~
3. ~~Create CLI parser profiles for `claude` and `codex` (YAML config)~~
4. ~~Build fallback tier system (best-effort → raw block → terminal escape hatch)~~
5. ~~Wire parser between existing SSE stream (`useXtermTerminal.ts`) and new chat view~~
6. ~~**Test**: 44 pattern tests + 36 parser tests (all passing)~~

### Phase 2: Mode-Aware Tool Filtering (Backend) — DONE
1. ~~Update `/api/mcp/tools/list` to accept `page` and `mode` query params~~
2. ~~Load `mcp_tool_groups.yaml` and filter tools by page groups~~
3. ~~Apply operation-mode exclusion list (30+ hidden tools)~~
4. ~~Add `displayName` and `category` fields to tool response~~
5. ~~Create `config/dashboard/tool_display_names.yaml` for user-friendly labels~~
6. ~~**Test**: 21 tool filter tests (all passing)~~

### Phase 3: Chat View + Interactive Cards (Frontend) — DONE
1. ~~Add `'chat'` to `ChatView` type in `chatStore.ts`~~
2. ~~Create `ChatBubbleView.tsx` component (message thread with bubbles)~~
3. ~~Build interactive card components: `PromptCard`, `ToolApprovalCard`, `ErrorCard`, `ProgressCard`~~
4. ~~Implement prompt response handler (button click → `sendRawKey` to PTY)~~
5. ~~Implement auto-switch to terminal view (Tier 3 fallback) with "Back to Chat" banner~~
6. ~~Implement resolved-prompt collapsing (card → inline summary after answer)~~
7. ~~Default to `'chat'` view when `mode === 'operation'`~~
8. ~~Add view toggle in FloatingChat header (Chat ↔ Terminal)~~

### Phase 4: Auto-Mode Switching + Toggle Button — DONE
1. ~~Read `useModeStore().mode` in FloatingChat; auto-default to `'chat'` when operation mode~~
2. ~~Add Chat/Terminal toggle button in header (MessageSquare ↔ Terminal icons)~~
3. ~~Toggle only visible in chat/terminal views (not action-dialog/actions-list)~~
4. ~~Active view highlighted with accent color~~
5. ~~**Test**: 6 new FloatingChat tests (auto-default, toggle, chat view rendering)~~

### Phase 5: Polish & Resilience — DONE
1. E2E testing with live CLI process (tune parser patterns against real Claude/Codex output) — deferred to live validation
2. ~~Usage-based action suggestions (smarter SuggestedActions selection)~~
3. ~~First-open onboarding tooltip~~
4. ~~PII/path redaction in error details (reuse `stripPII.ts` + `security.ts`)~~
5. ~~File attachment preview in chat bubbles~~
6. ~~Rename UI labels per mode (MCP Tools → Actions, CLI Selector → Assistant)~~

## Files Created

| File | Purpose | Tests |
|------|---------|-------|
| `lib/chat/types.ts` | 22 types: `ChatMessage`, `ChatThread`, `PromptCard`, `ErrorCard`, `ProgressCard`, `CliParserProfile`, `ParserEvent`, `PatternMatch`, etc. | — |
| `lib/chat/parserPatterns.ts` | Regex pattern library: 9 prompt, 3 tool-approval, 12 error, 4 progress, 3 tool-call, 7 thinking, 8 TUI-escape patterns. `classifyLine()` engine. | 44 tests |
| `lib/chat/ptyStreamParser.ts` | State machine: 6 states, idle detection, 3-tier fallback, singleton factory. | 36 tests |
| `lib/chat/index.ts` | Public API re-exports. | — |
| `lib/server/toolFilter.ts` | Server-side tool filtering: mode-aware exclusion (30+ tools), page-aware scoping, core_tools exempt from limits. | 21 tests |
| `components/chat/ChatBubbleView.tsx` | Main container: message thread, parser subscription, input bar, prompt/approval handlers, suggested actions, terminal fallback. | — |
| `components/chat/ChatMessageBubble.tsx` | Individual message bubble: user (right/violet), assistant (left/avatar), system (centered). Inline cards for prompt/approval/error/progress. | — |
| `components/chat/PromptCard.tsx` | Interactive prompt: confirm (y/n), multi-choice (radio), free-text (input). Collapses after resolution. | — |
| `components/chat/ToolApprovalCard.tsx` | Tool consent card: Allow / Deny / Always buttons. Amber theme. | — |
| `components/chat/ErrorCard.tsx` | Error display: 4 severities (fatal/actionable/warning/noise). Retry + Show Details. | — |
| `components/chat/ProgressCard.tsx` | Progress: determinate (bar) and indeterminate (pulse). Step info, Cancel. | — |
| `components/chat/TerminalFallbackBanner.tsx` | "Showing terminal view" banner with "Back to Chat" button. | — |
| `components/chat/SuggestedActions.tsx` | 2-3 contextual action pills below chat input. | — |
| `config/dashboard/tool_display_names.yaml` | Friendly labels, categories (assistant/knowledge/workflow/inbox/system), icons. | — |
| `config/dashboard/cli_parser_profiles.yaml` | Per-CLI regex configs for 7 CLIs. | — |

## Files Modified

| File | Change |
|------|--------|
| `lib/stores/chatStore.ts` | Added `'chat'` to `ChatView` union, `terminalFallbackActive` flag, `setTerminalFallbackActive` action |
| `components/FloatingChat.tsx` | Import ChatBubbleView + useModeStore. Auto-default to chat in operation mode. Chat/Terminal toggle button. Render ChatBubbleView when `chatView === 'chat'`. Wire terminal fallback transitions. Phase 5: mode-aware labels (MCP Tools→Actions, CLI Selector→Assistant), hide Data/PID in operation mode. |
| `app/api/mcp/tools/list/route.ts` | Accept `page`/`mode` query params. Backward compatible (no params = unfiltered). Returns `FilteredTool[]` with `meta`. |
| `components/chat/ErrorCard.tsx` | Phase 5: Sanitize error details via `sanitizeForLogging()` before rendering. |
| `components/chat/ChatMessageBubble.tsx` | Phase 5: File type icons (image/video/audio/PDF/archive) and formatted file size in attachment preview. |
| `components/chat/SuggestedActions.tsx` | Phase 5: Usage-based ranking (localStorage click tracking + time-of-day bias). |
| `components/chat/ChatBubbleView.tsx` | Phase 5: First-open onboarding tooltip with quick tips, dismissible via localStorage flag. |

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/dashboard/unit/chat/parserPatterns.test.ts` | 44 | Passing |
| `tests/dashboard/unit/chat/ptyStreamParser.test.ts` | 36 | Passing |
| `tests/dashboard/unit/chat/toolFilter.test.ts` | 21 | Passing |
| `tests/dashboard/components/FloatingChat.test.tsx` | 33 (22 existing + 6 Phase 4 + 5 Phase 5) | Passing |
| `tests/dashboard/components/chat/Phase5.test.tsx` | 10 | Passing |
| **Total** | **144** | **All passing** |

## Risk: Interactive Scenarios & Edge Cases

The PTY stream parser is the riskiest component. Here are the known edge cases and how each is handled:

| Scenario | Risk | Mitigation |
|----------|------|------------|
| **Parser misclassifies output** (e.g., treats normal text as a prompt) | User sees a button card when they should see a text bubble | Tier 2 fallback: if confidence < 70%, render as monospace text block. User is never blocked. |
| **Agent asks a question the parser doesn't recognize** | Question scrolls by as plain text; no button appears | Chat input bar is always active. User types answer normally (sent as PTY input). Same outcome, just less polished. |
| **Agent uses TUI / ncurses** (e.g., Claude Code's Ink interface) | Chat view renders garbled escape sequences | Tier 3 auto-switch: detect alternate screen buffer / cursor movement → switch to xterm.js terminal with "Back to Chat" banner. |
| **Two prompts in rapid succession** | Parser creates two PromptCards; user answers the wrong one | Queue prompts sequentially. Second card disabled until first is answered. Only one `AWAITING_INPUT` state at a time. |
| **Error mid-stream** (error occurs while assistant is still typing) | Streaming bubble + error card appear simultaneously | Flush current streaming bubble as complete (truncated), then show error card below it. |
| **User clicks Retry on error but process is dead** | sendRawKey fails because PTY exited | Retry handler checks process status first. If exited, spawns new CLI process via `/api/cli` POST, then re-sends the last user message. |
| **Long response with no clear end signal** | Streaming bubble never "finishes" | 3-second silence after last byte → mark message as complete. Idle timeout transitions parser to `IDLE` state. |
| **Agent outputs JSON/YAML data** | Parser tries to classify structured data as a prompt (e.g., YAML line ending with `:`) | Apply colon-prompt detection only to short lines (<100 chars). Multiline blocks are classified as `STREAMING_RESPONSE`. |
| **Password or sensitive input requested** | Chat view might render plaintext input field for a password | Detect password patterns (`password:`, `secret:`, `token:`) → render masked input field. Also: PII filter from `security.ts` blocks known sensitive patterns from being stored in chat history. |
| **User switches mode mid-conversation** | Chat history exists in bubble view; terminal has different scrollback | Both views share the same PTY process. Chat history (ChatMessage[]) is maintained in `chatStore`. Terminal scrollback is independent (xterm.js buffer). Switching views doesn't lose data in either. |
| **Extremely long output** (e.g., agent dumps a full file) | Chat bubble becomes enormous, slow to render | After 200 lines, collapse with "Show full output" expander. First 20 lines visible by default. |

### Design Principle: Never Block the User

If the parser fails or misclassifies, the user must **always** be able to:
1. Type in the chat input bar (sent as raw PTY input — works regardless of parser state)
2. Click "Switch to Terminal" to see raw xterm.js (the PTY data is always flowing to both views)
3. Click "Retry" or "Cancel" on any card

The chat view is **additive** — it renders cards on top of the existing PTY data flow. It never intercepts, modifies, or blocks PTY input/output. The worst case is an ugly text block or an auto-switch to terminal — never a dead end.

## Consequences

### Positive
- Operation mode feels like a familiar chatbot — no terminal intimidation
- Tool discovery scoped to what's relevant on the current page
- Infrastructure/dev tools completely hidden from non-dev users
- Existing `mcp_tool_groups.yaml` config finally enforced (designed but unused since v2.0)
- Dev mode unchanged — power users keep their terminal

### Negative
- Two rendering paths (chat view + terminal view) increase maintenance surface
- PTY → ChatMessage parsing is inherently lossy — some formatting lost in chat view
- Users in operation mode may not discover advanced features without switching to dev mode
- Additional config file (`tool_display_names.yaml`) to maintain

### Neutral
- Underlying CLI process model unchanged — chat view is a presentation layer only
- Dev mode UI completely unaffected
- Mode toggle still accessible via ⌘⇧D or chat header

## Alternatives Considered

### Alternative 1: Fully Replace Terminal with Chat in Both Modes

Replace xterm.js entirely with a web-based chat thread. Rejected because:
- Dev users need real terminal capabilities (scroll back, escape codes, process control)
- Would break the existing ADR-034 PTY architecture
- Loses the power-user workflow that dev mode serves

### Alternative 2: Just Filter the Tools List, Keep Terminal UI

Only apply tool filtering without changing the visual presentation. Rejected because:
- Even with filtered tools, the terminal UX is still foreign to chatbot users
- Raw CLI output with MCP protocol messages remains visible
- Doesn't address the core problem: it looks like a developer tool, not an assistant

### Alternative 3: Build a Separate Chat Page Instead of Modifying FloatingChat

Create a `/chat` page with full chatbot UI, separate from FloatingChat. Rejected because:
- Duplicates the interaction surface (exactly what ADR-036 tried to eliminate)
- FloatingChat is already the established interaction point
- Navigation between a chat page and FloatingChat would be confusing

## References

- ADR-034: CLI Chat Window with File Attachment
- ADR-035: CLI Chat Enhancements
- ADR-036: Chat vs Action Bar Partition
- ADR-017: Unified Context Management & Mode Separation
- `config/dashboard/mcp_tool_groups.yaml` — existing page-scoped tool config (unused)
- `src/dashboard/components/FloatingChat.tsx` — current chat implementation
- `src/dashboard/app/api/mcp/tools/list/route.ts` — unfiltered tools endpoint
