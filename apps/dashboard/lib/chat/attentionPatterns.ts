/**
 * Attention pattern detection — ADR-160
 *
 * Detects CLI output lines that require user intervention
 * (prompts, errors, process signals).
 */

const ATTENTION_PATTERNS: RegExp[] = [
  /\?\s*$/, // Line ending with ?
  /\(y\/n\)/i, // y/n prompt
  /\[Y\/n\]/, // [Y/n] prompt
  /\[y\/N\]/, // [y/N] prompt
  /continue\?/i, // continue prompt
  /press enter/i, // press enter prompt
  /waiting for input/i, // explicit input wait
  /permission denied/i, // access error
  /SIGTERM|SIGKILL|killed/i, // process signals
  /Do you want to proceed/i, // common CLI prompt
  /Are you sure/i, // confirmation prompt
];

/**
 * Returns true if the given line matches any attention pattern,
 * indicating user intervention may be needed.
 */
export function detectAttention(line: string): boolean {
  return ATTENTION_PATTERNS.some((pattern) => pattern.test(line));
}

/**
 * Error patterns that indicate the agent has failed (not just needs attention).
 */
const ERROR_PATTERNS: RegExp[] = [
  /^Error:/i,
  /^fatal:/i,
  /Traceback \(most recent call last\)/,
  /UnhandledPromiseRejection/,
  /ECONNREFUSED/,
  /ETIMEDOUT/,
];

export function detectError(line: string): boolean {
  return ERROR_PATTERNS.some((pattern) => pattern.test(line));
}
