// TODO_CLEANUP: This file is 898 lines — consider splitting into smaller modules
/**
 * ADR-047: Operation Mode Chatbot Experience — PTY Stream Parser
 *
 * State machine that classifies raw PTY output into structured ChatMessage
 * segments for parser consumers. Sits beside the SSE stream and does NOT
 * intercept or modify data flowing to xterm.js.
 *
 * Architecture:
 *   PTY (SSE) ──raw bytes──→ [this parser] ──ChatMessage[]
 *                    │
 *                    └──raw bytes──→ xterm.js (unchanged)
 *
 * Design principle: NEVER BLOCK THE USER.
 * If parsing fails, fall back to raw text (Tier 2) or auto-switch to
 * terminal (Tier 3). The chat input bar always accepts raw PTY input.
 */

import type {
  ParserState,
  ParserEvent,
  ParserEventHandler,
  ChatMessage,
  PromptCard,
  ToolApproval,
  ErrorCard,
  ProgressCard,
  ToolCallSummary,
  FallbackTier,
  MessageStatus,
  PromptType,
  CliParserProfile,
} from "./types";

import {
  classifyLine,
  detectTuiEscapes,
  isCliChrome,
  TUI_ESCAPE_THRESHOLD,
  THINKING_PATTERNS,
} from "./parserPatterns";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default silence duration (ms) before marking streaming message as complete */
const DEFAULT_IDLE_TIMEOUT_MS = 3000;

/** Max lines before collapsing output with "Show full output" */
const MAX_VISIBLE_LINES = 200;

/** Context window: how many previous lines to keep for multi-line detection */
const CONTEXT_WINDOW = 10;

/** Confidence threshold below which we fall back to Tier 2 (raw text) */
const CONFIDENCE_THRESHOLD = 0.7;

/** Max messages to keep in history before trimming old ones */
const MAX_MESSAGES = 500;

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

let messageCounter = 0;

function generateMessageId(): string {
  return `msg_${Date.now()}_${++messageCounter}`;
}

/**
 * Cursor horizontal positioning: \x1b[nG (absolute) and \x1b[nC (forward).
 * Claude Code uses these to place words at specific columns. Replacing with
 * a space (instead of stripping to empty) preserves word boundaries.
 */
const CURSOR_COL_RE = /\x1b\[\d*[GC]/g;

/**
 * Combined regex for stripping remaining ANSI escape sequences and carriage returns.
 */
const ANSI_STRIP_RE =
  /\x1b(?:\[[?>=<!]?[0-9;]*[a-zA-Z~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][0-9A-Za-z]|[>=<~}|])|\r/g;

/**
 * Prompt/bullet characters used by Claude Code for line decoration.
 * ● (U+25CF) = response paragraph bullet
 * ❯ (U+276F) = prompt chevron
 * ▸ (U+25B8) = prompt triangle
 */
const PROMPT_CHAR_TRIM_RE = /^[●❯▸>]+\s*|\s*[❯▸>]+$/g;

function stripAnsi(text: string): string {
  return text
    .replace(CURSOR_COL_RE, " ") // Cursor positioning → space (preserve word gaps)
    .replace(ANSI_STRIP_RE, "") // Strip remaining ANSI codes
    .replace(/  +/g, " "); // Collapse multiple spaces
}

/**
 * Strip leading/trailing box-drawing border characters from content lines.
 * Turns "│ Welcome to Claude Code │" → "Welcome to Claude Code".
 * Uses Unicode Box Drawing range U+2500-U+257F plus common variants.
 */
const BOX_BORDER_TRIM_RE =
  /^[\u2500-\u257F\u2580-\u259F╭╮╯╰]+\s*|\s*[\u2500-\u257F\u2580-\u259F╭╮╯╰]+$/g;

function stripBoxDrawing(text: string): string {
  return text.replace(BOX_BORDER_TRIM_RE, "");
}

// ---------------------------------------------------------------------------
// PtyStreamParser
// ---------------------------------------------------------------------------

export class PtyStreamParser {
  // State
  private state: ParserState = "IDLE";
  private fallbackTier: FallbackTier = "structured";

  // Message accumulation
  private currentMessage: ChatMessage | null = null;
  private messages: ChatMessage[] = [];
  private contentBuffer: string[] = [];

  // Last user message (for command echo detection)
  private lastUserText = "";

  // Context for multi-line detection
  private contextLines: string[] = [];

  // Tier 3 detection
  private consecutiveUnparseableLines = 0;

  // Idle detection
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private idleTimeoutMs = DEFAULT_IDLE_TIMEOUT_MS;

  // Active tool call tracking
  private activeToolCall: ToolCallSummary | null = null;
  private toolCallStartTime = 0;

  // Event handlers (multiple listeners supported)
  private handlers: ParserEventHandler[] = [];

  // CLI profile (for per-CLI pattern overrides)
  private profile: CliParserProfile | null = null;

  // Buffer for partial ANSI sequences split across chunks
  private partialAnsiBuffer = "";

  // Buffer for incomplete lines split across chunks — only process lines
  // after seeing a \n to avoid fragmenting text like "Claude" into "C\na\nl..."
  private lineBuffer = "";

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /** Subscribe to parser events */
  addEventListener(handler: ParserEventHandler): void {
    if (!this.handlers.includes(handler)) {
      this.handlers.push(handler);
    }
  }

  /** Unsubscribe from parser events */
  removeEventListener(handler: ParserEventHandler): void {
    const idx = this.handlers.indexOf(handler);
    if (idx !== -1) {
      this.handlers.splice(idx, 1);
    }
  }

  /** Set the CLI parser profile for pattern overrides */
  setProfile(profile: CliParserProfile): void {
    this.profile = profile;
    // Apply custom idle timeout if specified in profile
    if (profile.idleTimeoutMs !== undefined) {
      this.idleTimeoutMs = profile.idleTimeoutMs;
    }
  }

  /** Set custom idle timeout in milliseconds */
  setIdleTimeout(ms: number): void {
    this.idleTimeoutMs = ms;
  }

  /** Get current parser state */
  getState(): ParserState {
    return this.state;
  }

  /** Get current fallback tier */
  getFallbackTier(): FallbackTier {
    return this.fallbackTier;
  }

  /** Get all accumulated messages */
  getMessages(): ChatMessage[] {
    return [...this.messages];
  }

  /** Get the current in-progress message (if any) */
  getCurrentMessage(): ChatMessage | null {
    return this.currentMessage;
  }

  /**
   * Feed raw PTY data into the parser.
   * Call this with each chunk from the SSE stream.
   *
   * @param rawChunk - Raw PTY data (may contain ANSI codes)
   */
  feed(rawChunk: string): void {
    this.resetIdleTimer();

    // Prepend any buffered partial ANSI sequence from previous chunk
    const data = this.partialAnsiBuffer + rawChunk;
    this.partialAnsiBuffer = "";

    // Check if chunk ends with an incomplete ANSI escape sequence
    // An incomplete sequence starts with \x1b but the terminating character hasn't arrived yet
    const lastEsc = data.lastIndexOf("\x1b");
    if (lastEsc !== -1 && lastEsc >= data.length - 10) {
      // Check if there's a complete sequence after this escape
      const tail = data.slice(lastEsc);
      if (
        !/\x1b(?:\[[?>=<!]?[0-9;]*[a-zA-Z~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][0-9A-Za-z]|[>=<~}|])/.test(
          tail,
        )
      ) {
        // Incomplete — buffer it for next chunk
        this.partialAnsiBuffer = tail;
        const completeData = data.slice(0, lastEsc);
        if (!completeData) return;
        this.processChunk(completeData);
        return;
      }
    }

    this.processChunk(data);
  }

  private processChunk(data: string): void {
    // --- Tier 3 check: TUI detection on raw (pre-strip) data ---
    if (this.fallbackTier !== "terminal" && detectTuiEscapes(data)) {
      this.switchToTerminalFallback("TUI escape sequences detected");
      return;
    }

    // Strip ANSI codes and box-drawing border chars for classification
    const cleaned = stripBoxDrawing(stripAnsi(data));

    // Buffer incomplete lines across chunks. PTY output arrives in tiny
    // fragments (sometimes 1-2 bytes); only process a line once we see
    // a \n confirming it's complete. The last partial segment stays in
    // lineBuffer until the next chunk arrives or idle timer flushes it.
    const combined = this.lineBuffer + cleaned;
    const parts = combined.split("\n");

    // Last element is partial (no trailing \n) — keep buffered
    this.lineBuffer = parts.pop() || "";

    for (const line of parts) {
      this.processLine(line, data);
    }
  }

  /** Flush any buffered partial line (called on idle timeout / message completion) */
  private flushLineBuffer(): void {
    if (this.lineBuffer.trim()) {
      this.processLine(this.lineBuffer, "");
    }
    this.lineBuffer = "";
  }

  /**
   * Notify the parser that the PTY process exited.
   */
  processExit(exitCode: number): void {
    this.clearIdleTimer();
    this.flushLineBuffer();

    if (exitCode !== 0) {
      // Non-zero exit → error
      this.emitError({
        severity: "fatal",
        summary: `Process exited with code ${exitCode}`,
        details: `The CLI process terminated unexpectedly (exit code ${exitCode}).`,
        processExited: true,
        suggestedFix: "Click Retry to restart the assistant.",
      });
    }

    // Complete any in-progress message
    this.completeCurrentMessage();
    this.transition("IDLE");
  }

  /**
   * Handle user response to an interactive prompt.
   * Updates the prompt card to resolved state.
   *
   * @param messageId - The message containing the prompt
   * @param answer - The user's answer
   */
  resolvePrompt(messageId: string, answer: string): void {
    const msg = this.messages.find((m) => m.id === messageId);
    if (msg?.promptCard) {
      msg.promptCard.resolved = true;
      msg.promptCard.answer = answer;
      msg.status = "complete";
    }
  }

  /**
   * Handle user response to a tool approval request.
   */
  resolveToolApproval(
    messageId: string,
    decision: "allow" | "deny" | "always",
  ): void {
    const msg = this.messages.find((m) => m.id === messageId);
    if (msg?.toolApproval) {
      msg.toolApproval.resolved = true;
      msg.toolApproval.decision = decision;
      msg.status = "complete";
    }
  }

  /**
   * Reset parser to initial state. Called when switching CLI
   * or starting a new conversation.
   */
  reset(): void {
    this.clearIdleTimer();
    this.state = "IDLE";
    this.fallbackTier = "structured";
    this.currentMessage = null;
    this.messages = [];
    this.contentBuffer = [];
    this.contextLines = [];
    this.consecutiveUnparseableLines = 0;
    this.activeToolCall = null;
    this.toolCallStartTime = 0;
    this.handlers = [];
    this.partialAnsiBuffer = "";
    this.lineBuffer = "";
    this.lastUserText = "";
    this.idleTimeoutMs = DEFAULT_IDLE_TIMEOUT_MS;
  }

  // ---------------------------------------------------------------------------
  // Core Processing
  // ---------------------------------------------------------------------------

  private processLine(line: string, _rawChunk: string): void {
    let trimmed = line.trim();
    // Check for thinking indicators BEFORE skip filter - these are meaningful states
    // that should never be filtered out even if they look like spinner fragments
    if (THINKING_PATTERNS.some((p) => p.test(trimmed))) {
      this.handleThinking();
      return;
    }
    if (this.shouldSkipLine(trimmed)) return;

    // Strip prompt/bullet characters from line boundaries.
    // ● (U+25CF) = paragraph bullet, ❯/▸/> = prompt chevrons.
    trimmed = trimmed.replace(PROMPT_CHAR_TRIM_RE, "").trim();
    if (!trimmed) return;
    if (this.shouldSkipLine(trimmed)) return;

    // Classify the line
    const match = classifyLine(trimmed, this.contextLines, this.profile?.cliId);
    this.updateContextWindow(trimmed);
    if (this.shouldUseRawTextFallback(match, trimmed)) return;
    if (this.shouldSwitchToTerminalFallback(match, trimmed)) return;
    this.dispatchMatchedCategory(match, trimmed);
  }

  private shouldSkipLine(trimmed: string): boolean {
    if (!trimmed && this.state !== "STREAMING_RESPONSE") return true;
    if (this.fallbackTier === "terminal") return true;
    // Skip decorative lines (box-drawing frames, borders, spinner artifacts)
    // that have no meaningful text content — at least one alphanumeric char required
    if (trimmed && !/[a-zA-Z0-9]/.test(trimmed)) return true;
    // Skip short fragments (≤4 chars) — animation artifacts from cursor-positioned
    // character-by-character rendering (spinner text like "Elucidating" arrives as
    // "lu", "Ec", "ca", "di" etc). Real response text arrives as full sentences.
    if (trimmed.length > 0 && trimmed.length <= 4) return true;
    // Skip single-word lines without spaces — spinner fragments ("Kneading...",
    // "ng...", "Elucidating") are never real response text. Responses always
    // contain spaces (multiple words). Exception: lines with digits may be
    // progress indicators ("Working...77%") — let those through for classifyLine.
    if (trimmed.length <= 30 && !trimmed.includes(" ") && !/\d/.test(trimmed))
      return true;
    // Skip CLI prompt/status chrome (git branch prompt, spinners, keyboard hints)
    // These are terminal UI elements that should not be classified as messages.
    if (trimmed && isCliChrome(trimmed)) return true;
    // Skip command echo — the terminal echoes the user's input back. The user
    // already sees their message in the chat, so the echo is redundant.
    if (this.lastUserText && trimmed.toLowerCase().includes(this.lastUserText))
      return true;
    return false;
  }

  private updateContextWindow(trimmed: string): void {
    if (!trimmed) return;
    this.contextLines.push(trimmed);
    if (this.contextLines.length > CONTEXT_WINDOW) {
      this.contextLines.shift();
    }
  }

  private shouldUseRawTextFallback(
    match: ReturnType<typeof classifyLine>,
    trimmed: string,
  ): boolean {
    if (match.category === "none" || match.confidence >= CONFIDENCE_THRESHOLD) {
      return false;
    }
    this.handleRawTextFallback(trimmed);
    return true;
  }

  private isGarbledLine(trimmed: string): boolean {
    return (
      /[\x00-\x08\x0e-\x1f\x7f]/.test(trimmed) ||
      !/[\w\s.,!?;:'"()\-/\\@#$%^&*+=[\]{}<>~`|]/.test(trimmed)
    );
  }

  private shouldSwitchToTerminalFallback(
    match: ReturnType<typeof classifyLine>,
    trimmed: string,
  ): boolean {
    if (match.category !== "none") {
      this.consecutiveUnparseableLines = 0;
      return false;
    }
    if (!trimmed.length) return false;

    if (!this.isGarbledLine(trimmed)) {
      this.consecutiveUnparseableLines = 0;
      return false;
    }

    this.consecutiveUnparseableLines += 1;
    if (this.consecutiveUnparseableLines < TUI_ESCAPE_THRESHOLD) return false;

    this.switchToTerminalFallback(
      `${TUI_ESCAPE_THRESHOLD} consecutive unclassifiable lines`,
    );
    return true;
  }

  private dispatchMatchedCategory(
    match: ReturnType<typeof classifyLine>,
    trimmed: string,
  ): void {
    const categoryHandlers: Record<string, () => void> = {
      thinking: () => this.handleThinking(),
      tool_approval: () => this.handleToolApproval(match.extracted!),
      tool_call: () => this.handleToolCallStart(match.extracted!.toolName!),
      error: () => this.handleError(match.extracted!.errorMessage!, trimmed),
      progress: () => this.handleProgress(match.extracted!),
      prompt: () => {
        const options = match.extracted!.options || [];
        this.handlePrompt(
          match.extracted!.question!,
          options,
          match.extracted!.defaultIndex,
          this.inferPromptType(options),
        );
      },
    };

    const handler = categoryHandlers[match.category];
    if (handler) {
      handler();
      return;
    }
    this.handleStreamingText(trimmed);
  }

  // ---------------------------------------------------------------------------
  // Handlers for Each Category
  // ---------------------------------------------------------------------------

  private handleThinking(): void {
    // If we were streaming, complete that message first
    if (this.state === "STREAMING_RESPONSE") {
      this.completeCurrentMessage();
    }
    this.transition("THINKING");
  }

  private handleStreamingText(text: string): void {
    if (this.state !== "STREAMING_RESPONSE") {
      // Start a new assistant message
      this.completeCurrentMessage();
      this.currentMessage = this.createMessage("assistant", "", "streaming");
      this.contentBuffer = [];
      this.transition("STREAMING_RESPONSE");
      this.emit({ type: "message_start", role: "assistant" });
    }

    // Append text
    this.contentBuffer.push(text);

    // Enforce line limit
    if (this.contentBuffer.length <= MAX_VISIBLE_LINES) {
      this.currentMessage!.content = this.contentBuffer.join("\n");
    } else {
      // Truncate display but keep full content in buffer
      this.currentMessage!.content =
        this.contentBuffer.slice(0, 20).join("\n") +
        `\n\n--- ${this.contentBuffer.length - 20} more lines (click "Show full output") ---\n\n` +
        this.contentBuffer.slice(-5).join("\n");
    }

    this.emit({ type: "message_chunk", content: text });
  }

  private handlePrompt(
    question: string,
    options: string[],
    defaultIndex: number | undefined,
    type: PromptType,
  ): void {
    // Complete any in-progress streaming
    this.completeCurrentMessage();

    const promptCard: PromptCard = {
      type,
      question,
      options,
      defaultIndex,
      resolved: false,
    };

    const msg = this.createMessage("assistant", question, "awaiting_input");
    msg.promptCard = promptCard;
    this.currentMessage = msg;
    this.messages.push(msg);

    this.transition("AWAITING_INPUT");
    this.emit({ type: "prompt_detected", prompt: promptCard });
  }

  private handleToolApproval(
    extracted: NonNullable<ReturnType<typeof classifyLine>["extracted"]>,
  ): void {
    this.completeCurrentMessage();

    const approval: ToolApproval = {
      toolName: extracted.toolName || "Unknown tool",
      description: extracted.toolDescription || "",
      resolved: false,
    };

    const msg = this.createMessage(
      "assistant",
      `Allow ${approval.toolName}?`,
      "awaiting_input",
    );
    msg.toolApproval = approval;
    this.currentMessage = msg;
    this.messages.push(msg);

    this.transition("AWAITING_INPUT");
    this.emit({ type: "tool_approval_detected", approval });
  }

  private handleToolCallStart(toolName: string): void {
    // If already tracking a tool call, complete it
    this.completeActiveToolCall("success");

    this.activeToolCall = {
      name: toolName,
      displayName: this.friendlyToolName(toolName),
      result: "",
      status: "running",
    };
    this.toolCallStartTime = Date.now();

    this.transition("TOOL_EXECUTING");
    this.emit({
      type: "tool_call_start",
      name: toolName,
      displayName: this.activeToolCall.displayName,
    });
  }

  private handleError(summary: string, rawLine: string): void {
    // If we were streaming, flush the current message first
    if (this.state === "STREAMING_RESPONSE" && this.currentMessage) {
      this.currentMessage.status = "complete";
      this.messages.push(this.currentMessage);
      this.emit({
        type: "message_complete",
        messageId: this.currentMessage.id,
      });
      this.currentMessage = null;
    }

    this.emitError({
      severity: "actionable", // classifyLine determined it's not noise
      summary,
      details: rawLine,
      processExited: false,
    });
  }

  private emitError(error: ErrorCard): void {
    const msg = this.createMessage("system", error.summary, "error");
    msg.errorCard = error;
    this.messages.push(msg);

    this.transition("ERROR");
    this.emit({ type: "error_detected", error });
  }

  private handleProgress(
    extracted: NonNullable<ReturnType<typeof classifyLine>["extracted"]>,
  ): void {
    const progress: ProgressCard = {
      label: extracted.stepLabel || "Working...",
      percentage: extracted.percentage ?? null,
      step:
        extracted.stepCurrent && extracted.stepTotal
          ? {
              current: extracted.stepCurrent,
              total: extracted.stepTotal,
              label: extracted.stepLabel,
            }
          : undefined,
      cancelled: false,
    };

    // Update existing progress card on current message if possible
    if (this.currentMessage?.progressCard) {
      this.currentMessage.progressCard = progress;
    } else {
      // Attach to current message or create system message
      if (this.currentMessage && this.currentMessage.status === "streaming") {
        this.currentMessage.progressCard = progress;
      }
    }

    this.emit({ type: "progress_update", progress });
  }

  // ---------------------------------------------------------------------------
  // Fallback Handlers
  // ---------------------------------------------------------------------------

  private handleRawTextFallback(text: string): void {
    if (this.fallbackTier !== "raw_text") {
      this.fallbackTier = "raw_text";
      this.emit({
        type: "fallback_tier_change",
        tier: "raw_text",
        reason: "Low confidence classification",
      });
    }

    // Render as monospace text inside assistant bubble
    this.handleStreamingText(text);
  }

  private switchToTerminalFallback(reason: string): void {
    this.completeCurrentMessage();
    this.fallbackTier = "terminal";

    this.emit({
      type: "fallback_tier_change",
      tier: "terminal",
      reason,
    });
  }

  /**
   * Exit terminal fallback (called when user clicks "Back to Chat").
   */
  exitTerminalFallback(): void {
    this.fallbackTier = "structured";
    this.consecutiveUnparseableLines = 0;
    this.transition("IDLE");

    this.emit({
      type: "fallback_tier_change",
      tier: "structured",
      reason: "User returned to chat view",
    });
  }

  // ---------------------------------------------------------------------------
  // State Machine
  // ---------------------------------------------------------------------------

  private transition(to: ParserState): void {
    if (this.state === to) return;

    const from = this.state;
    this.state = to;

    this.emit({
      type: "state_change",
      transition: { from, to, timestamp: Date.now() },
    });
  }

  // ---------------------------------------------------------------------------
  // Message Lifecycle
  // ---------------------------------------------------------------------------

  private createMessage(
    role: ChatMessage["role"],
    content: string,
    status: MessageStatus,
  ): ChatMessage {
    return {
      id: generateMessageId(),
      role,
      content,
      timestamp: Date.now(),
      status,
    };
  }

  private completeCurrentMessage(): void {
    if (!this.currentMessage) return;

    // Complete any active tool call
    this.completeActiveToolCall("success");

    this.currentMessage.status = "complete";
    this.currentMessage.content =
      this.contentBuffer.join("\n") || this.currentMessage.content;

    // Only add if not already in messages
    if (!this.messages.includes(this.currentMessage)) {
      this.messages.push(this.currentMessage);
    }

    // Cap message history
    if (this.messages.length > MAX_MESSAGES) {
      this.messages = this.messages.slice(-MAX_MESSAGES);
    }

    this.emit({ type: "message_complete", messageId: this.currentMessage.id });
    this.currentMessage = null;
    this.contentBuffer = [];
  }

  private completeActiveToolCall(status: "success" | "error"): void {
    if (!this.activeToolCall) return;

    this.activeToolCall.status = status;
    this.activeToolCall.durationMs = Date.now() - this.toolCallStartTime;

    // Attach to current message
    if (this.currentMessage) {
      if (!this.currentMessage.toolCalls) {
        this.currentMessage.toolCalls = [];
      }
      this.currentMessage.toolCalls.push(this.activeToolCall);
    }

    this.emit({
      type: "tool_call_complete",
      name: this.activeToolCall.name,
      result: this.activeToolCall.result,
      status,
    });

    this.activeToolCall = null;
  }

  /**
   * Record a user message (called by the chat view when user sends input).
   */
  addUserMessage(
    content: string,
    attachments?: ChatMessage["attachments"],
  ): ChatMessage {
    const msg = this.createMessage("user", content, "complete");
    if (attachments) msg.attachments = attachments;
    this.messages.push(msg);
    this.lastUserText = content.trim().toLowerCase();

    // Cap message history
    if (this.messages.length > MAX_MESSAGES) {
      this.messages = this.messages.slice(-MAX_MESSAGES);
    }

    // Reset fallback tier for next exchange
    if (this.fallbackTier === "raw_text") {
      this.fallbackTier = "structured";
    }

    // ERROR → IDLE recovery: user interaction signals intent to continue
    if (this.state === "ERROR") {
      this.transition("IDLE");
    }

    return msg;
  }

  // ---------------------------------------------------------------------------
  // Idle Detection
  // ---------------------------------------------------------------------------

  private resetIdleTimer(): void {
    this.clearIdleTimer();

    this.idleTimer = setTimeout(() => {
      // No input for idleTimeoutMs — flush any buffered partial line, then mark as complete
      this.flushLineBuffer();
      if (
        this.state === "STREAMING_RESPONSE" ||
        this.state === "THINKING" ||
        this.state === "TOOL_EXECUTING"
      ) {
        this.completeCurrentMessage();
        this.transition("IDLE");
        this.emit({ type: "idle" });
      }
    }, this.idleTimeoutMs);
  }

  private clearIdleTimer(): void {
    if (this.idleTimer) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Utilities
  // ---------------------------------------------------------------------------

  private emit(event: ParserEvent): void {
    for (const handler of this.handlers) {
      handler(event);
    }
  }

  /** Infer prompt type from options list */
  private inferPromptType(options: string[]): PromptType {
    if (options.length === 0) return "free_text";
    if (
      options.length === 2 &&
      (options.includes("Yes") ||
        options.includes("Allow") ||
        options.includes("Continue"))
    ) {
      return "confirm";
    }
    if (options.length > 2) return "multi_choice";
    return "confirm";
  }

  /** Convert tool name to user-friendly label */
  private friendlyToolName(toolName: string): string {
    // Simple transform: kebab-case/snake_case → Title Case
    return toolName
      .replace(/[-_]/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

// ---------------------------------------------------------------------------
// Singleton factory
// ---------------------------------------------------------------------------

let parserInstance: PtyStreamParser | null = null;

/**
 * Get or create the PTY stream parser singleton.
 * The parser persists across chat view opens/closes
 * but resets when the CLI process changes.
 */
export function getPtyStreamParser(): PtyStreamParser {
  if (!parserInstance) {
    parserInstance = new PtyStreamParser();
  }
  return parserInstance;
}

/**
 * Reset the parser singleton (called on CLI switch or new session).
 */
export function resetPtyStreamParser(): void {
  parserInstance?.reset();
  parserInstance = null;
}
