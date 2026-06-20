/**
 * ADR-157 Decision 5: Quiet Mode Output Filter
 *
 * Filters raw PTY output to suppress verbose CLI traces in operation mode.
 * Applied in the SSE stream path before data reaches the client.
 */

export type VerbosityLevel = "quiet" | "normal" | "verbose";

/**
 * Patterns to suppress in quiet mode.
 * Each pattern matches a single line of cleaned (ANSI-stripped) output.
 */
const QUIET_SUPPRESS_PATTERNS: RegExp[] = [
  // Tool-use traces (Claude Code style)
  /^⏳\s/,
  /^✓\s(Completed|Ran|Read|Wrote|Edited)/,
  /^⎿\s/,
  /^│\s/,
  // Thinking indicators
  /^Thinking\.{2,}/i,
  /^\s*\.{3,}\s*$/,
  // Permission prompts (already auto-approved in embedded mode)
  /Allow\s+(Read|Write|Edit|Bash|Glob|Grep|Task)/i,
  /\(Y\/n\)/,
  // File diff blocks
  /^[+-]{3}\s[ab]\//,
  /^@@\s/,
  /^diff --git/,
  // Progress spinners (single char spinner frames)
  /^[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s/,
  // Tool call metadata
  /^Running\s+\w+\.\.\./i,
  /^Tool call:/i,
  /^Input:/i,
  /^Output \(\d+ lines?\):/i,
];

/**
 * Patterns to always keep regardless of verbosity level.
 */
const ALWAYS_KEEP_PATTERNS: RegExp[] = [
  // Errors
  /error/i,
  /Error:/,
  /failed/i,
  // User-facing questions
  /\?\s*$/,
  // Progress for long ops (simplified status)
  /^\[\d+\/\d+\]/,
  /\d+%/,
];

function shouldSuppressLine(line: string): boolean {
  const trimmed = line.trim();
  if (trimmed.length === 0) return false;

  // Always keep lines matching keep patterns
  for (const pattern of ALWAYS_KEEP_PATTERNS) {
    if (pattern.test(trimmed)) return false;
  }

  // Suppress lines matching quiet patterns
  for (const pattern of QUIET_SUPPRESS_PATTERNS) {
    if (pattern.test(trimmed)) return true;
  }

  return false;
}

/**
 * Filter PTY output based on verbosity level.
 *
 * @param raw - Raw text output (ANSI codes should be stripped before calling)
 * @param level - Verbosity level
 * @returns Filtered text with suppressed lines removed
 */
export function filterOutput(raw: string, level: VerbosityLevel): string {
  if (level === "verbose") return raw;
  if (level === "normal") return raw;

  // Quiet mode: suppress verbose tool traces
  const lines = raw.split("\n");
  const kept = lines.filter((line) => !shouldSuppressLine(line));

  // Collapse consecutive empty lines
  const collapsed: string[] = [];
  let prevEmpty = false;
  for (const line of kept) {
    const isEmpty = line.trim().length === 0;
    if (isEmpty && prevEmpty) continue;
    collapsed.push(line);
    prevEmpty = isEmpty;
  }

  return collapsed.join("\n");
}

/**
 * Filter raw PTY data (with ANSI codes) for quiet mode.
 * This operates on the raw stream before base64 encoding.
 * Less precise than cleaned text filtering but avoids decoding overhead.
 */
export function filterRawOutput(raw: string, level: VerbosityLevel): string {
  if (level !== "quiet") return raw;

  // For raw mode, we do a lighter-weight filter on common verbose patterns.
  // We can't split on \n as cleanly due to ANSI, but we can remove known
  // verbose sequences that appear at line boundaries.
  return raw
    .replace(/⏳[^\n]*\n/g, "")
    .replace(/✓\s*(Completed|Ran|Read|Wrote|Edited)[^\n]*\n/g, "")
    .replace(/⎿[^\n]*\n/g, "")
    .replace(/Thinking\.{2,}[^\n]*\n/gi, "");
}
