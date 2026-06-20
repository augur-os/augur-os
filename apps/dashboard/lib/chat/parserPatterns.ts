/**
 * ADR-047: Operation Mode Chatbot Experience
 *
 * Regex pattern library for PTY stream classification.
 * Each pattern set has a category and is ordered by specificity
 * (most specific first → highest confidence).
 *
 * Pattern arrays are evaluated top-to-bottom; first match wins
 * with confidence decreasing by position (1.0 → 0.7 step -0.05).
 */

import type { PatternMatch, PromptType, ErrorSeverity } from "./types";

// ---------------------------------------------------------------------------
// Prompt Detection
// ---------------------------------------------------------------------------

interface PromptPattern {
  regex: RegExp;
  type: PromptType;
  /** Extract default option index from the match */
  extractDefault?: (match: RegExpMatchArray) => number | undefined;
  /** Extract option list from surrounding context */
  extractOptions?: (line: string, context: string[]) => string[];
}

/** Patterns that indicate the terminal is waiting for user input */
export const PROMPT_PATTERNS: PromptPattern[] = [
  // Claude Code specific: "Do you want to [action]? (y/n)"
  {
    regex: /Do you want to (.+)\?\s*\(y\/n\)\s*$/i,
    type: "confirm",
    extractDefault: () => 0, // Yes is default
    extractOptions: () => ["Yes", "No"],
  },
  // Generic y/n with default indicated by case: (Y/n) or (y/N)
  {
    regex: /(.+)\?\s*\(([yY])\/([nN])\)\s*$/,
    type: "confirm",
    extractDefault: (m) => (m[2] === "Y" ? 0 : 1),
    extractOptions: () => ["Yes", "No"],
  },
  // [yes/no] format
  {
    regex: /(.+)\?\s*\[yes\/no\]\s*$/i,
    type: "confirm",
    extractOptions: () => ["Yes", "No"],
  },
  // [y/N] or [Y/n] bracket format
  {
    regex: /(.+)\?\s*\[([yY])\/([nN])\]\s*$/,
    type: "confirm",
    extractDefault: (m) => (m[2] === "Y" ? 0 : 1),
    extractOptions: () => ["Yes", "No"],
  },
  // "Allow [tool] to run [action]?" — tool approval (special prompt)
  {
    regex: /Allow (.+) to (.+)\?\s*$/i,
    type: "confirm",
    extractOptions: () => ["Allow", "Deny"],
  },
  // "Press Enter to continue" — continuation prompt
  {
    regex: /Press Enter to continue/i,
    type: "confirm",
    extractOptions: () => ["Continue"],
  },
  // Numbered list multi-choice (e.g., "1. Option A\n2. Option B")
  // Only triggers when the PREVIOUS context line ended with "?" (a question precedes the list)
  {
    regex: /^\s*1[\.\)]\s+.+$/,
    type: "multi_choice",
    extractOptions: (_line, context) => {
      // Only classify as multi-choice if a question preceded the numbered list
      const prevNonEmpty = [...context]
        .reverse()
        .find((l) => l.trim().length > 0);
      if (!prevNonEmpty || !prevNonEmpty.trim().endsWith("?")) {
        return []; // Not a prompt — no question before the list
      }
      return context.flatMap((line) =>
        /^\s*\d+[\.\)]\s+.+$/.test(line)
          ? [line.replace(/^\s*\d+[\.\)]\s+/, "").trim()]
          : [],
      );
    },
  },
  // "Enter [something]:" — free text input request
  {
    regex: /Enter (.+)\s*:\s*$/i,
    type: "free_text",
    extractOptions: () => [],
  },
  // Generic question ending with "?" — only short, imperative-style prompts
  // Must look like a CLI prompt: starts with a verb or "What/Which/How"
  // and is under 100 chars. Avoids matching chatbot prose responses.
  {
    regex:
      /^(?:What|Which|Where|How|Do|Should|Would|Can|Could|Shall|Select|Choose|Pick|Specify|Provide|Name)\b.{5,95}\?\s*$/,
    type: "free_text",
    extractOptions: () => [],
  },
  // Bare colon prompt (e.g., "Filename: ") — only short lines
  {
    regex: /^.{3,80}:\s*$/,
    type: "free_text",
    extractOptions: () => [],
  },
];

// ---------------------------------------------------------------------------
// Tool Approval Detection (subset of prompts, handled separately)
// ---------------------------------------------------------------------------

interface ToolApprovalPattern {
  regex: RegExp;
  extractToolName: (match: RegExpMatchArray) => string;
  extractDescription: (match: RegExpMatchArray, context: string[]) => string;
}

export const TOOL_APPROVAL_PATTERNS: ToolApprovalPattern[] = [
  // Claude Code: "Do you want to run [tool_name]?"
  {
    regex: /Do you want to (?:run|use|execute)\s+(.+)\?/i,
    extractToolName: (m) => m[1].trim(),
    extractDescription: (_m, ctx) => ctx.slice(-3).join(" ").trim(),
  },
  // "Allow [tool] to [action]"
  {
    regex: /Allow\s+(.+?)\s+to\s+(.+)/i,
    extractToolName: (m) => m[1].trim(),
    extractDescription: (m) => m[2].trim(),
  },
  // "Tool: [name]" header followed by description
  {
    regex: /^Tool:\s+(.+)$/i,
    extractToolName: (m) => m[1].trim(),
    extractDescription: (_m, ctx) => ctx.slice(-2).join(" ").trim(),
  },
];

// ---------------------------------------------------------------------------
// Error Detection
// ---------------------------------------------------------------------------

interface ErrorPattern {
  regex: RegExp;
  severity: ErrorSeverity;
  /** Extract a user-friendly summary from the match */
  extractSummary: (match: RegExpMatchArray, line: string) => string;
}

export const ERROR_PATTERNS: ErrorPattern[] = [
  // Process exit with non-zero code
  {
    regex: /exit code\s+([1-9]\d*)/i,
    severity: "fatal",
    extractSummary: (m) => `Process exited with code ${m[1]}`,
  },
  // FATAL / panic (Go, Rust)
  {
    regex: /^(?:FATAL|panic):\s*(.+)/,
    severity: "fatal",
    extractSummary: (m) => m[1].trim(),
  },
  // Python traceback header
  {
    regex: /Traceback \(most recent call last\)/,
    severity: "fatal",
    extractSummary: () => "Python encountered an unhandled exception",
  },
  // Connection refused
  {
    regex: /(?:Connection refused|ECONNREFUSED)/i,
    severity: "actionable",
    extractSummary: () =>
      "Connection to the service was refused. Is it running?",
  },
  // Permission denied
  {
    regex: /Permission denied/i,
    severity: "actionable",
    extractSummary: (_, line) =>
      `Permission denied: ${line.slice(0, 120).trim()}`,
  },
  // Command not found
  {
    regex: /command not found/i,
    severity: "actionable",
    extractSummary: (_, line) => line.trim().slice(0, 120),
  },
  // File not found / ENOENT
  {
    regex: /(?:No such file or directory|ENOENT)/i,
    severity: "actionable",
    extractSummary: (_, line) => `File not found: ${line.slice(0, 120).trim()}`,
  },
  // Timeout
  {
    regex: /(?:timed?\s*out|ETIMEDOUT|ESOCKETTIMEDOUT)/i,
    severity: "actionable",
    extractSummary: () => "The operation timed out",
  },
  // Generic "Error:" prefix
  {
    regex: /^(?:Error|ERROR):\s*(.+)/,
    severity: "actionable",
    extractSummary: (m) => m[1].trim().slice(0, 200),
  },
  // JS stack trace line (not the error itself, but indicates one happened)
  {
    regex: /^\s+at\s+.+\(.+:\d+:\d+\)/,
    severity: "noise",
    extractSummary: () => "",
  },
  // Warning level
  {
    regex: /^(?:Warning|WARN|⚠):\s*(.+)/i,
    severity: "warning",
    extractSummary: (m) => m[1].trim().slice(0, 200),
  },
  // Deprecation
  {
    regex: /deprecated/i,
    severity: "warning",
    extractSummary: (_, line) => line.trim().slice(0, 200),
  },
];

// ---------------------------------------------------------------------------
// Progress Detection
// ---------------------------------------------------------------------------

interface ProgressPattern {
  regex: RegExp;
  extract: (match: RegExpMatchArray) => {
    percentage: number | null;
    stepCurrent?: number;
    stepTotal?: number;
    stepLabel?: string;
    label?: string;
  };
}

export const PROGRESS_PATTERNS: ProgressPattern[] = [
  // "Step 2 of 5: Analyzing data" or "Step 2/5: ..."
  {
    regex: /Step\s+(\d+)\s+(?:of|\/)\s+(\d+)(?:\s*[:\-]\s*(.+))?/i,
    extract: (m) => ({
      percentage: Math.round((parseInt(m[1]) / parseInt(m[2])) * 100),
      stepCurrent: parseInt(m[1]),
      stepTotal: parseInt(m[2]),
      stepLabel: m[3]?.trim(),
    }),
  },
  // "45%" or "[45%]" or "( 45% )"
  {
    regex: /[\[\(]?\s*(\d{1,3})\s*%\s*[\]\)]?/,
    extract: (m) => ({
      percentage: Math.min(parseInt(m[1]), 100),
    }),
  },
  // Progress bar: "████████░░░░ 60%" or "[========>    ] 60%"
  {
    regex: /[█▓▒░=\->#\s]{4,}\s*(\d{1,3})%/,
    extract: (m) => ({
      percentage: Math.min(parseInt(m[1]), 100),
    }),
  },
  // "[3/10] Processing file..."
  {
    regex: /\[(\d+)\/(\d+)\]\s*(.*)/,
    extract: (m) => ({
      percentage: Math.round((parseInt(m[1]) / parseInt(m[2])) * 100),
      stepCurrent: parseInt(m[1]),
      stepTotal: parseInt(m[2]),
      label: m[3]?.trim(),
    }),
  },
];

// ---------------------------------------------------------------------------
// Tool Call Detection (agent executing a tool, not approval)
// ---------------------------------------------------------------------------

export interface ToolCallPattern {
  regex: RegExp;
  extractName: (match: RegExpMatchArray) => string;
}

export const TOOL_CALL_PATTERNS: ToolCallPattern[] = [
  // Claude Code: "⏺ tool_name" (U+23FA record symbol, NOT ● U+25CF bullet)
  // ● is used for response text bullets ("● Hey. What are we working on?")
  { regex: /^⏺\s+(\S+)/, extractName: (m) => m[1] },
  // "Running: tool_name" or "Executing: tool_name"
  { regex: /^(?:Running|Executing):\s+(\S+)/i, extractName: (m) => m[1] },
  // "[tool] tool_name"
  { regex: /^\[tool\]\s+(\S+)/i, extractName: (m) => m[1] },
];

// ---------------------------------------------------------------------------
// Thinking / Processing Indicators
// ---------------------------------------------------------------------------

export const THINKING_PATTERNS: RegExp[] = [
  /^(?:Thinking|Processing|Analyzing|Working)\.{2,}$/i,
  /^[⏳🤔]/,
  /^\.{3,}$/, // Just dots (Claude Code thinking indicator)
];

// ---------------------------------------------------------------------------
// TUI / Escape Hatch Detection (Tier 3 triggers)
// ---------------------------------------------------------------------------

/** Patterns that indicate heavy TUI rendering — chat view cannot handle these.
 *
 * IMPORTANT: Only include sequences that are truly TUI-specific.
 * Common sequences like clear-to-EOL (\x1b[K), hide cursor (\x1b[?25l),
 * and cursor up/down (\x1b[nA/B) are used by normal CLIs (spinners,
 * progress bars) and must NOT trigger fallback.
 */
const TUI_ESCAPE_PATTERNS: RegExp[] = [
  /\x1b\[\?1049h/, // Alternate screen buffer ON (definitive TUI signal)
  /\x1b\[\?1049l/, // Alternate screen buffer OFF
  /\x1b\[2J/, // Clear entire screen
  // NOTE: Cursor absolute positioning (\x1b[\d+;\d+H) intentionally excluded.
  // Claude Code uses it for its startup header rendering — triggering fallback
  // on it makes the entire chat view empty. Alternate screen buffer is sufficient.
];

/** How many consecutive unparseable lines trigger Tier 3 auto-switch */
export const TUI_ESCAPE_THRESHOLD = 5;

// ---------------------------------------------------------------------------
// Pattern Matching Engine
// ---------------------------------------------------------------------------

/**
 * Lines that are CLI prompt/status chrome, not message content.
 * Matches patterns like:
 *   "Augur(main) ▸▸bypasspermissions..." — CLI prompt line
 *   "❯ hi · Calculating..." — command echo with spinner
 *   "· Calculating... ❯" — spinner/status fragment
 *   "(shift+tabtocycle)" — keyboard shortcut hints
 */
const CLI_CHROME_PATTERNS: RegExp[] = [
  /\(\w+\)\s*[▸❯>]{1,}/, // Git branch prompt: "project(main) ▸▸"
  /[▸❯>]\s*.+[·…]\s*[▸❯>]?\s*$/, // Command echo with spinner dots
  /^[·•]\s*\w+[.…]*\s*[❯▸>]?\s*$/, // Spinner: "· word..." or "· word… ❯"
  /\(shift\+tab/i, // Keyboard shortcut hints
  /bypass\s*permissions/i, // Permission mode indicator
  /^[+*]?\s*\w{1,30}[.…]+(?:\s*\(\w+\))?\s*$/, // Spinner word+dots: "*Recombobulating...", "Kneading...(thinking)"
  /^\(\w+\)\s*$/, // Bare status label: "(thinking)", "(processing)"
  /\(\d+s\s*·\s*[↓↑]\s*\d+\w*\)/, // Stats text: "(38s · ↓ 0tokens)"
  /^\d+s\s*·\s*[↓↑]\s*\d+/, // Bare stats: "38s · ↓ 0tokens"
  // Status bar: version + middot/block separators + path (e.g. "v2.1.42 · Opus 4.6 ▮ ~/dir")
  /v\d+\.\d+.*(?:·|▮).*[~\/]/,
  // Prompt echo: starts with ● and contains — or ends with > ❯ ▸
  /^●.*(?:—|[>❯▸])\s*$/,
  // Suggestion line: "> Try ..." or "❯ Try ..."
  /^[>❯▸]\s*Try\s/i,
  // CLI slash-command echo: "> /command" or "❯ /command"
  /^[>❯▸]\s*\/\w+/,
  // Chrome extension status indicator
  /Chrome\s*enabled/i,
  // Brand symbol at line start (✻/✽ used in Claude Code header)
  /^[✻⊹✽]\s/,
  // Claude Code startup header lines
  /^Claude\s+Code\b/i, // "Claude Code v2.1.42"
  /^(?:Opus|Sonnet|Haiku|Claude)\s+\d/i, // Model identifier: "Opus 4.6 · Claude Max"
  /^Context:\s*\d/i, // "Context: 25% (0.6K/200K)"
  /^(?:Augur|Project)\s*\(/i, // "Augur (main) |" project/branch line
];

export function isCliChrome(trimmed: string): boolean {
  return CLI_CHROME_PATTERNS.some((p) => p.test(trimmed));
}

const PROSE_SKIP_KEYWORDS =
  /(?:error|Error|ERROR|exit code|Traceback|timed?\s*out|ECONNREFUSED|Permission denied|command not found|ENOENT|Warning|WARN|deprecated|Allow\s|Do you want|Press Enter|Step\s+\d|^\s*\d+[\.\)]|^[⏺●◉]|^(?:Running|Executing):)/i;
const PROSE_SHAPE_REGEX = /^[a-zA-Z][a-zA-Z0-9\s.,!;'"()\-/]+$/;

function isSkippableProse(trimmed: string): boolean {
  return (
    trimmed.length > 40 &&
    trimmed.includes(" ") &&
    !trimmed.endsWith("?") &&
    !trimmed.endsWith(":") &&
    !/\.{2,}$/.test(trimmed) &&
    !PROSE_SKIP_KEYWORDS.test(trimmed) &&
    PROSE_SHAPE_REGEX.test(trimmed)
  );
}

function matchThinking(trimmed: string): PatternMatch | null {
  for (const pattern of THINKING_PATTERNS) {
    if (pattern.test(trimmed)) {
      return { category: "thinking", confidence: 0.9 };
    }
  }
  return null;
}

function matchToolApproval(
  trimmed: string,
  contextLines: string[],
): PatternMatch | null {
  for (let i = 0; i < TOOL_APPROVAL_PATTERNS.length; i++) {
    const pattern = TOOL_APPROVAL_PATTERNS[i];
    const match = trimmed.match(pattern.regex);
    if (!match) continue;

    return {
      category: "tool_approval",
      confidence: Math.max(0.7, 1.0 - i * 0.05),
      extracted: {
        toolName: pattern.extractToolName(match),
        toolDescription: pattern.extractDescription(match, contextLines),
      },
    };
  }
  return null;
}

function matchToolCall(trimmed: string): PatternMatch | null {
  for (let i = 0; i < TOOL_CALL_PATTERNS.length; i++) {
    const pattern = TOOL_CALL_PATTERNS[i];
    const match = trimmed.match(pattern.regex);
    if (!match) continue;

    return {
      category: "tool_call",
      confidence: Math.max(0.7, 0.95 - i * 0.05),
      extracted: { toolName: pattern.extractName(match) },
    };
  }
  return null;
}

function matchError(trimmed: string): PatternMatch | null {
  for (let i = 0; i < ERROR_PATTERNS.length; i++) {
    const pattern = ERROR_PATTERNS[i];
    const match = trimmed.match(pattern.regex);
    if (!match) continue;

    if (pattern.severity === "noise") {
      return { category: "none", confidence: 0.3 };
    }

    return {
      category: "error",
      confidence: Math.max(0.7, 1.0 - i * 0.03),
      extracted: {
        errorMessage: pattern.extractSummary(match, trimmed),
      },
    };
  }
  return null;
}

function matchProgress(trimmed: string): PatternMatch | null {
  for (let i = 0; i < PROGRESS_PATTERNS.length; i++) {
    const pattern = PROGRESS_PATTERNS[i];
    const match = trimmed.match(pattern.regex);
    if (!match) continue;

    const data = pattern.extract(match);
    return {
      category: "progress",
      confidence: Math.max(0.7, 0.95 - i * 0.05),
      extracted: {
        percentage: data.percentage ?? undefined,
        stepCurrent: data.stepCurrent,
        stepTotal: data.stepTotal,
        stepLabel: data.stepLabel || data.label,
      },
    };
  }
  return null;
}

function isInvalidColonPrompt(
  trimmed: string,
  pattern: PromptPattern,
): boolean {
  if (
    pattern.type !== "free_text" ||
    !pattern.regex.source.includes(":\\s*$")
  ) {
    return false;
  }
  return trimmed.length > 80 || /^\s*\w+\s*:/.test(trimmed);
}

function matchPrompt(
  trimmed: string,
  contextLines: string[],
): PatternMatch | null {
  if (trimmed.length >= 200) return null;

  for (let i = 0; i < PROMPT_PATTERNS.length; i++) {
    const pattern = PROMPT_PATTERNS[i];
    const match = trimmed.match(pattern.regex);
    if (!match) continue;
    if (isInvalidColonPrompt(trimmed, pattern)) continue;

    const options = pattern.extractOptions
      ? pattern.extractOptions(trimmed, contextLines)
      : [];
    const defaultIdx = pattern.extractDefault
      ? pattern.extractDefault(match)
      : undefined;

    return {
      category: "prompt",
      confidence: Math.max(0.7, 1.0 - i * 0.04),
      extracted: {
        question: trimmed,
        options,
        defaultIndex: defaultIdx,
      },
    };
  }

  return null;
}

/**
 * Classify a single line of cleaned (ANSI-stripped) terminal output.
 *
 * @param line - The cleaned text line to classify
 * @param contextLines - Previous N lines for multi-line pattern detection
 * @param cliId - Active CLI identifier for profile-specific overrides
 * @returns PatternMatch with category, confidence, and extracted data
 */
export function classifyLine(
  line: string,
  contextLines: string[] = [],
  _cliId?: string,
): PatternMatch {
  const trimmed = line.trim();

  if (!trimmed) {
    return { category: "none", confidence: 0 };
  }

  // Check for thinking indicators FIRST - these are meaningful states
  // that should never be filtered out even if they look like spinner fragments
  const thinkingMatch = matchThinking(trimmed);
  if (thinkingMatch) {
    return thinkingMatch;
  }

  // Skip CLI prompt/status chrome (prompt lines, spinners, keyboard hints)
  if (isCliChrome(trimmed)) {
    return { category: "none", confidence: 0 };
  }

  if (isSkippableProse(trimmed)) {
    return { category: "none", confidence: 0 };
  }

  const stages: Array<PatternMatch | null> = [
    matchToolApproval(trimmed, contextLines),
    matchToolCall(trimmed),
    matchError(trimmed),
    matchProgress(trimmed),
    matchPrompt(trimmed, contextLines),
  ];

  for (const stageMatch of stages) {
    if (stageMatch) return stageMatch;
  }

  return { category: "none", confidence: 0 };
}

/**
 * Check raw (pre-ANSI-strip) bytes for TUI escape sequences.
 * Returns true if the output likely comes from a TUI application
 * that the chat view cannot render.
 */
export function detectTuiEscapes(rawChunk: string): boolean {
  return TUI_ESCAPE_PATTERNS.some((p) => p.test(rawChunk));
}
