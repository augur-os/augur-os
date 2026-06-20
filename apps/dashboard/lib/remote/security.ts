/**
 * Remote Providers - Security Gates
 *
 * Security utilities for validating data before sending to remote LLM providers.
 * Includes PII detection, secrets scanning, and action whitelist validation.
 */

import type { ProviderId, SecuritySettings, ExecutionContext } from "./types";

// =============================================================================
// PII Detection Patterns
// =============================================================================

const PII_PATTERNS: Array<{
  name: string;
  pattern: RegExp;
  severity: "high" | "medium";
}> = [
  // High severity - very sensitive
  { name: "SSN", pattern: /\b\d{3}-\d{2}-\d{4}\b/, severity: "high" },
  {
    name: "Credit Card",
    pattern: /\b(?:\d{4}[-\s]?){3}\d{4}\b/,
    severity: "high",
  },
  {
    name: "Bank Account",
    pattern: /\b\d{8,17}\b(?=.*(?:account|routing|iban))/i,
    severity: "high",
  },
  { name: "Passport", pattern: /\b[A-Z]{1,2}\d{6,9}\b/i, severity: "high" },

  // Medium severity - personal but less sensitive
  {
    name: "Email",
    pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/,
    severity: "medium",
  },
  {
    name: "Phone",
    pattern: /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/,
    severity: "medium",
  },
  {
    name: "IP Address",
    pattern: /\b(?:\d{1,3}\.){3}\d{1,3}\b/,
    severity: "medium",
  },
  {
    name: "Date of Birth",
    pattern:
      /\b(?:dob|birth(?:day|date)?)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b/i,
    severity: "medium",
  },
];

// =============================================================================
// Secrets Detection Patterns
// =============================================================================

const SECRETS_PATTERNS: Array<{ name: string; pattern: RegExp }> = [
  // API Keys - Generic patterns
  {
    name: "Generic API Key",
    pattern: /\b(?:api[_-]?key|apikey)[:\s=]+['"]?[A-Za-z0-9_\-]{20,}['"]?/i,
  },
  { name: "Bearer Token", pattern: /\bBearer\s+[A-Za-z0-9_\-\.]+/i },

  // Provider-specific keys
  { name: "OpenAI Key", pattern: /\bsk-[A-Za-z0-9]{20,}/i },
  { name: "Anthropic Key", pattern: /\bsk-ant-[A-Za-z0-9\-]{20,}/i },
  { name: "AWS Key", pattern: /\bAKIA[0-9A-Z]{16}\b/ },
  {
    name: "AWS Secret",
    pattern: /\b[A-Za-z0-9\/+=]{40}\b(?=.*(?:aws|secret))/i,
  },
  {
    name: "GitHub Token",
    pattern: /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b/,
  },
  { name: "Slack Token", pattern: /\bxox[baprs]-[A-Za-z0-9\-]+/ },
  {
    name: "Stripe Key",
    pattern: /\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}\b/,
  },
  { name: "Google API Key", pattern: /\bAIza[A-Za-z0-9_\-]{35}\b/ },

  // Generic secrets
  {
    name: "Private Key",
    pattern: /-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----/,
  },
  { name: "Password in URL", pattern: /(?:password|pwd|pass)[=:][^&\s]{4,}/i },
  {
    name: "Connection String",
    pattern: /(?:mongodb|postgres|mysql|redis):\/\/[^\s]+:[^\s]+@/i,
  },
  {
    name: "JWT Token",
    pattern:
      /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/,
  },
];

// =============================================================================
// Prompt Injection Patterns (attempts to manipulate remote execution)
// =============================================================================

const INJECTION_PATTERNS: Array<{ name: string; pattern: RegExp }> = [
  {
    name: "Provider bypass",
    pattern: /(?:use|switch|call).*(?:remote|cloud).*provider/i,
  },
  {
    name: "API key extraction",
    pattern: /(?:show|reveal|output|print).*(?:api[_\s]?key|secret|token)/i,
  },
  {
    name: "Security bypass",
    pattern: /(?:bypass|ignore|disable|skip).*(?:security|validation|check)/i,
  },
  {
    name: "System prompt leak",
    pattern: /(?:ignore|forget).*(?:previous|system|instructions)/i,
  },
];

function globalRegex(pattern: RegExp): RegExp {
  const flags = new Set(pattern.flags);
  flags.add("g");
  flags.add("i");
  return new RegExp(pattern.source, Array.from(flags).sort().join(""));
}

const PII_MATCHERS = PII_PATTERNS.map(({ name, pattern, severity }) => ({
  name,
  regex: globalRegex(pattern),
  severity,
}));

const SECRET_MATCHERS = SECRETS_PATTERNS.map(({ name, pattern }) => ({
  name,
  regex: globalRegex(pattern),
}));

const INJECTION_MATCHERS = INJECTION_PATTERNS.map(({ name, pattern }) => ({
  name,
  regex: globalRegex(pattern),
}));

// =============================================================================
// Detection Results
// =============================================================================

export interface PIIMatch {
  type: string;
  value: string;
  severity: "high" | "medium";
  index: number;
}

export interface SecretMatch {
  type: string;
  value: string;
  index: number;
}

export interface InjectionMatch {
  type: string;
  value: string;
  index: number;
}

export interface SecurityScanResult {
  safe: boolean;
  pii: PIIMatch[];
  secrets: SecretMatch[];
  injections: InjectionMatch[];
  warnings: string[];
  blockers: string[];
}

// =============================================================================
// Detection Functions
// =============================================================================

/**
 * Scan text for PII patterns
 */
export function detectPII(text: string): PIIMatch[] {
  const matches: PIIMatch[] = [];

  for (const { name, regex, severity } of PII_MATCHERS) {
    regex.lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({
        type: name,
        value: maskSensitive(match[0]),
        severity,
        index: match.index,
      });
    }
  }

  return matches;
}

/**
 * Scan text for secrets/credentials
 */
export function detectSecrets(text: string): SecretMatch[] {
  const matches: SecretMatch[] = [];

  for (const { name, regex } of SECRET_MATCHERS) {
    regex.lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({
        type: name,
        value: maskSensitive(match[0]),
        index: match.index,
      });
    }
  }

  return matches;
}

/**
 * Scan text for prompt injection attempts
 */
export function detectInjection(text: string): InjectionMatch[] {
  const matches: InjectionMatch[] = [];

  for (const { name, regex } of INJECTION_MATCHERS) {
    regex.lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({
        type: name,
        value: match[0],
        index: match.index,
      });
    }
  }

  return matches;
}

/**
 * Mask sensitive values for display (show first/last few chars)
 */
function maskSensitive(value: string): string {
  if (value.length <= 8) {
    return "*".repeat(value.length);
  }
  return `${value.slice(0, 3)}${"*".repeat(value.length - 6)}${value.slice(-3)}`;
}

// =============================================================================
// Security Gate Functions
// =============================================================================

/**
 * Perform full security scan on input text
 */
export function scanForSensitiveData(
  text: string,
  settings: SecuritySettings,
): SecurityScanResult {
  const pii = detectPII(text);
  const secrets = detectSecrets(text);
  const injections = detectInjection(text);

  const warnings: string[] = [];
  const blockers: string[] = [];

  // Process PII findings
  if (pii.length > 0 && settings.warnOnPii) {
    const highSeverity = pii.filter((p) => p.severity === "high");
    const mediumSeverity = pii.filter((p) => p.severity === "medium");

    if (highSeverity.length > 0) {
      warnings.push(
        `Found ${highSeverity.length} high-sensitivity PII: ${highSeverity.map((p) => p.type).join(", ")}`,
      );
    }
    if (mediumSeverity.length > 0) {
      warnings.push(
        `Found ${mediumSeverity.length} medium-sensitivity PII: ${mediumSeverity.map((p) => p.type).join(", ")}`,
      );
    }
  }

  // Process secrets findings (always block)
  if (secrets.length > 0 && settings.blockOnSecrets) {
    blockers.push(
      `Detected ${secrets.length} potential secrets: ${secrets.map((s) => s.type).join(", ")}`,
    );
  }

  // Process injection attempts (always block)
  if (injections.length > 0) {
    blockers.push(
      `Detected ${injections.length} potential prompt injection attempts`,
    );
  }

  return {
    safe: blockers.length === 0,
    pii,
    secrets,
    injections,
    warnings,
    blockers,
  };
}

/**
 * Validate that an action button is allowed to use remote execution
 */
function validateActionButton(
  actionButton: { mode?: string; allowedProviders?: ProviderId[] } | null,
  providerId: ProviderId,
): { allowed: boolean; reason?: string } {
  if (!actionButton) {
    return { allowed: false, reason: "No action button context provided" };
  }

  if (actionButton.mode !== "remote") {
    return {
      allowed: false,
      reason: `Action button mode is "${actionButton.mode || "default"}", not "remote"`,
    };
  }

  if (
    actionButton.allowedProviders &&
    !actionButton.allowedProviders.includes(providerId)
  ) {
    return {
      allowed: false,
      reason: `Provider "${providerId}" is not in the allowed providers list`,
    };
  }

  return { allowed: true };
}

/**
 * Check if input path is in sensitive folders list
 */
function isInSensitiveFolder(
  filePath: string,
  sensitiveFolders: string[],
): boolean {
  const normalizedPath = filePath.replace(/^~/, process.env.HOME || "");

  for (const folder of sensitiveFolders) {
    const normalizedFolder = folder.replace(/^~/, process.env.HOME || "");
    if (normalizedPath.startsWith(normalizedFolder)) {
      return true;
    }
  }

  return false;
}

/**
 * Full security gate check for remote execution
 */
function canExecuteRemote(
  context: ExecutionContext,
  settings: SecuritySettings,
): { allowed: boolean; warnings: string[]; blockers: string[] } {
  const warnings: string[] = [];
  const blockers: string[] = [];

  // Gate 1: Validate action button
  const actionValidation = validateActionButton(
    context.actionButton,
    context.provider,
  );
  if (!actionValidation.allowed) {
    blockers.push(actionValidation.reason || "Action not allowed");
  }

  // Gate 2: Scan for sensitive data
  const scanResult = scanForSensitiveData(context.input, settings);
  warnings.push(...scanResult.warnings);
  blockers.push(...scanResult.blockers);

  // Gate 3: Check budget limits (placeholder - would need usage tracking)
  if (context.estimatedCost > (context.actionButton.maxCostUsd || Infinity)) {
    blockers.push(
      `Estimated cost ($${context.estimatedCost.toFixed(4)}) exceeds limit ($${context.actionButton.maxCostUsd})`,
    );
  }

  return {
    allowed: blockers.length === 0,
    warnings,
    blockers,
  };
}

/**
 * Sanitize text by removing detected secrets (for logging purposes)
 */
export function sanitizeForLogging(text: string): string {
  let sanitized = text;

  // Remove secrets
  for (const { regex } of SECRET_MATCHERS) {
    regex.lastIndex = 0;
    sanitized = sanitized.replace(regex, "[REDACTED]");
  }

  // Mask high-severity PII
  for (const { regex, severity } of PII_MATCHERS) {
    if (severity === "high") {
      regex.lastIndex = 0;
      sanitized = sanitized.replace(regex, "[PII_REDACTED]");
    }
  }

  return sanitized;
}
