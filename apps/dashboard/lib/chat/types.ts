/**
 * ADR-047: Operation Mode Chatbot Experience
 *
 * Type definitions for the PTY stream parser.
 * These types bridge the gap between raw terminal output and
 * structured chatbot UI elements.
 */

import type { AttachedFile } from "@/lib/stores/chatStore";

// ---------------------------------------------------------------------------
// Parser State Machine
// ---------------------------------------------------------------------------

/** States the PTY stream parser can be in */
export type ParserState =
  | "IDLE"
  | "THINKING"
  | "STREAMING_RESPONSE"
  | "AWAITING_INPUT"
  | "TOOL_EXECUTING"
  | "ERROR";

/** Transitions emitted by the parser when state changes */
export interface ParserTransition {
  from: ParserState;
  to: ParserState;
  timestamp: number;
  /** Raw text that triggered this transition (for debugging) */
  trigger?: string;
}

// ---------------------------------------------------------------------------
// Chat Messages (structured output from parser)
// ---------------------------------------------------------------------------

export type MessageRole = "user" | "assistant" | "system";

export type MessageStatus =
  | "complete"
  | "streaming"
  | "awaiting_input"
  | "error"
  | "cancelled";

/** Prompt types the parser can detect */
export type PromptType = "confirm" | "multi_choice" | "free_text";

/** An interactive prompt detected in assistant output */
export interface PromptCard {
  type: PromptType;
  /** The question text extracted from terminal output */
  question: string;
  /** Available choices (for confirm: ['Yes','No'], for multi_choice: parsed options) */
  options: string[];
  /** Default option index, if detectable (e.g., Y/n → 0) */
  defaultIndex?: number;
  /** Whether the user has already answered (card collapses to show answer) */
  resolved: boolean;
  /** The answer the user selected (set after resolution) */
  answer?: string;
}

/** A tool approval request detected in assistant output */
export interface ToolApproval {
  /** Name of the tool/action the agent wants to run */
  toolName: string;
  /** Human-readable description of what it will do */
  description: string;
  /** Whether the user has responded */
  resolved: boolean;
  /** User's decision */
  decision?: "allow" | "deny" | "always";
}

/** Error card severity levels */
export type ErrorSeverity = "fatal" | "actionable" | "warning" | "noise";

/** An error detected in terminal output */
export interface ErrorCard {
  severity: ErrorSeverity;
  /** User-friendly summary (e.g., "Connection to the service was refused") */
  summary: string;
  /** Raw error text (sanitized, shown on "Show Details" expand) */
  details: string;
  /** Whether the process exited due to this error */
  processExited: boolean;
  /** Suggested fix, if determinable */
  suggestedFix?: string;
}

/** Progress info for long-running operations */
export interface ProgressCard {
  /** Human-readable label (e.g., "Analyzing your calendar") */
  label: string;
  /** 0-100 percentage, or null for indeterminate */
  percentage: number | null;
  /** Step info if available (e.g., "Step 2 of 3") */
  step?: { current: number; total: number; label?: string };
  /** Whether the operation was cancelled by the user */
  cancelled: boolean;
}

/** Summary of a tool call (collapsed in chat history) */
export interface ToolCallSummary {
  name: string;
  /** User-friendly display name */
  displayName: string;
  /** Brief result summary */
  result: string;
  status: "success" | "error" | "running";
  /** Duration in milliseconds */
  durationMs?: number;
}

/** A single message in the chat thread */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  status: MessageStatus;

  // Interactive elements (at most one active at a time)
  promptCard?: PromptCard;
  toolApproval?: ToolApproval;
  errorCard?: ErrorCard;
  progressCard?: ProgressCard;

  // Collapsed tool executions within this message
  toolCalls?: ToolCallSummary[];

  // File attachments (carried over from user message)
  attachments?: AttachedFile[];
}

/** The full chat thread state */
export interface ChatThread {
  messages: ChatMessage[];
  /** Current parser state (drives UI indicators like typing dots) */
  parserState: ParserState;
  /** Whether the terminal fallback view is active (Tier 3) */
  terminalFallbackActive: boolean;
}

// ---------------------------------------------------------------------------
// Fallback Tiers
// ---------------------------------------------------------------------------

/** Which rendering tier the parser has selected for current output */
export type FallbackTier =
  | "structured" // Tier 1: High confidence — render as cards/bubbles
  | "raw_text" // Tier 2: Readable but unclassified — monospace block
  | "terminal"; // Tier 3: Heavy ANSI/TUI — switch to xterm.js

// ---------------------------------------------------------------------------
// CLI Parser Profiles
// ---------------------------------------------------------------------------

/** Per-CLI regex configuration for the stream parser */
export interface CliParserProfile {
  cliId: string;
  /** Override/extend default prompt detection patterns */
  promptPatterns?: RegExp[];
  /** Override/extend default error detection patterns */
  errorPatterns?: RegExp[];
  /** CLI-specific tool approval pattern */
  toolApprovalPattern?: RegExp;
  /** CLI-specific progress output pattern */
  progressPattern?: RegExp;
  /** How this CLI separates distinct messages in output */
  streamingDelimiter?: string;
  /** Whether this CLI can output structured JSON */
  supportsStructuredOutput: boolean;
  /** Custom idle timeout in milliseconds (default: 3000) */
  idleTimeoutMs?: number;
}

// ---------------------------------------------------------------------------
// Parser Events (emitted to the chat view)
// ---------------------------------------------------------------------------

/** Events the parser emits as it processes the PTY stream */
export type ParserEvent =
  | { type: "message_start"; role: MessageRole }
  | { type: "message_chunk"; content: string }
  | { type: "message_complete"; messageId: string }
  | { type: "prompt_detected"; prompt: PromptCard }
  | { type: "tool_approval_detected"; approval: ToolApproval }
  | { type: "tool_call_start"; name: string; displayName: string }
  | {
      type: "tool_call_complete";
      name: string;
      result: string;
      status: "success" | "error";
    }
  | { type: "error_detected"; error: ErrorCard }
  | { type: "progress_update"; progress: ProgressCard }
  | { type: "state_change"; transition: ParserTransition }
  | { type: "fallback_tier_change"; tier: FallbackTier; reason: string }
  | { type: "idle" };

/** Callback for receiving parser events */
export type ParserEventHandler = (event: ParserEvent) => void;

// ---------------------------------------------------------------------------
// Pattern Match Result (internal to parser)
// ---------------------------------------------------------------------------

/** Result of running detection patterns against a line/chunk */
export interface PatternMatch {
  /** Which pattern category matched */
  category:
    | "prompt"
    | "error"
    | "tool_approval"
    | "progress"
    | "tool_call"
    | "thinking"
    | "none";
  /** Confidence 0-1 (below 0.7 → fall back to Tier 2 raw text) */
  confidence: number;
  /** Extracted data from the match */
  extracted?: {
    question?: string;
    options?: string[];
    defaultIndex?: number;
    errorMessage?: string;
    errorDetails?: string;
    toolName?: string;
    toolDescription?: string;
    percentage?: number;
    stepCurrent?: number;
    stepTotal?: number;
    stepLabel?: string;
  };
}
