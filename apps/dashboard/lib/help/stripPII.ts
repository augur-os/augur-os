/**
 * Help System - PII Stripping
 *
 * Strips personally identifiable information from help request payloads
 * before they leave the dashboard. Wraps the existing security.ts detection
 * with help-specific path redaction.
 */

import {
  detectPII,
  detectSecrets,
  sanitizeForLogging,
} from "../remote/security";

export interface HelpPayload {
  topic: "bug" | "howto" | "feature" | "performance" | "general";
  description: string;
  context: {
    page: string;
    skill: string | null;
    mode: string;
    browser: string;
  };
  logs?: {
    browserErrors: string[];
  };
  supportToken: string;
  timestamp: string;
  email_notification?: string;
}

export interface StrippedItem {
  type: string;
  severity: "high" | "medium";
  original: string;
}

export interface StripResult {
  cleaned: HelpPayload;
  strippedItems: StrippedItem[];
}

/**
 * Redact absolute file paths that contain usernames.
 * /Users/janedoe/Projects/Augur/... → /[HOME]/Projects/Augur/...
 */
export function redactPaths(text: string): string {
  // macOS/Linux home paths — allow spaces in usernames
  let redacted = text.replace(/\/Users\/[^/]+\//g, "/[HOME]/");
  // Windows home paths — allow spaces in usernames
  redacted = redacted.replace(
    /C:\\Users\\[^\\]+\\/gi, // audit-ignore: regex pattern for PII redaction
    "C:\\[HOME]\\", // audit-ignore: replacement pattern
  );
  // Hostname patterns (e.g., hostname.local)
  redacted = redacted.replace(/\b[a-zA-Z][\w-]*\.local\b/g, "[HOSTNAME].local");
  return redacted;
}

/**
 * Strip PII and secrets from a help payload.
 * Returns both the cleaned payload and a list of what was stripped
 * (for display in the privacy confirmation step).
 */
export function stripPayloadPII(payload: HelpPayload): StripResult {
  const strippedItems: StrippedItem[] = [];

  // Deep clone to avoid mutating original
  const cleaned: HelpPayload = JSON.parse(JSON.stringify(payload));

  // Strip description
  const descPII = detectPII(cleaned.description);
  const descSecrets = detectSecrets(cleaned.description);

  for (const match of descPII) {
    strippedItems.push({
      type: match.type,
      severity: match.severity,
      original: match.value,
    });
  }
  for (const match of descSecrets) {
    strippedItems.push({
      type: match.type,
      severity: "high",
      original: match.value,
    });
  }

  cleaned.description = sanitizeForLogging(cleaned.description);
  cleaned.description = redactPaths(cleaned.description);

  // Strip context page path
  cleaned.context.page = redactPaths(cleaned.context.page);

  // Strip browser errors if present
  if (cleaned.logs?.browserErrors) {
    cleaned.logs.browserErrors = cleaned.logs.browserErrors.map((err) => {
      const errPII = detectPII(err);
      const errSecrets = detectSecrets(err);

      for (const match of errPII) {
        strippedItems.push({
          type: match.type,
          severity: match.severity,
          original: match.value,
        });
      }
      for (const match of errSecrets) {
        strippedItems.push({
          type: match.type,
          severity: "high",
          original: match.value,
        });
      }

      let sanitized = sanitizeForLogging(err);
      sanitized = redactPaths(sanitized);
      return sanitized;
    });
  }

  // Preserve intentional email opt-in (user explicitly chose to include it)
  if (payload.email_notification) {
    cleaned.email_notification = payload.email_notification;
  }

  return { cleaned, strippedItems };
}
