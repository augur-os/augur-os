/**
 * LLM-Assisted Retry Utility for TypeScript (ADR-106).
 *
 * Mirror of src/lib/llm_retry.py for dashboard components.
 * Provides CLI resolution, LLM diagnosis, and JSONL event logging.
 */

import { execSync, execFileSync } from "child_process";
import fsSync from "fs";
import os from "os";
import path from "path";
import yaml from "yaml";
import { AUGUR_ROOT, AUGUR_RUNTIME_DIR, AUGUR_VAULT_CONFIG_DIR } from "./paths";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LLMRetryConfig {
  enabled: boolean;
  triggerAttempt: number;
  timeoutS: number;
  cli: string;
  mode: string;
  components: Record<string, boolean>;
}

export interface RetryAttemptLog {
  attempt: number;
  error: string;
  timestamp: string;
}

export interface LLMDiagnosis {
  rootCause: string;
  suggestion: string;
  shouldRetry: boolean;
  rawResponse: string;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const DEFAULT_CONFIG: LLMRetryConfig = {
  enabled: true,
  triggerAttempt: 3,
  timeoutS: 90,
  cli: "auto",
  mode: "diagnose",
  components: {},
};

export function loadRetryConfig(): LLMRetryConfig {
  const configPath = path.join(AUGUR_ROOT, "config", "system", "llm.yaml");
  try {
    if (!fsSync.existsSync(configPath)) return { ...DEFAULT_CONFIG };
    const raw = fsSync.readFileSync(configPath, "utf-8");
    const data = yaml.parse(raw) ?? {};
    const section = data.llm_retry;
    if (!section || typeof section !== "object") return { ...DEFAULT_CONFIG };
    return {
      enabled: section.enabled ?? true,
      triggerAttempt: section.trigger_attempt ?? 3,
      timeoutS: section.timeout_s ?? 90,
      cli: section.cli ?? "auto",
      mode: section.mode ?? "diagnose",
      components: section.components ?? {},
    };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function isEnabledFor(
  config: LLMRetryConfig,
  component: string,
): boolean {
  return config.enabled && (config.components[component] ?? false);
}

// ---------------------------------------------------------------------------
// CLI resolution
// ---------------------------------------------------------------------------

function whichSync(name: string): string | null {
  try {
    const result = execSync(`which ${name}`, {
      encoding: "utf-8",
      timeout: 5000,
    });
    return result.trim() || null;
  } catch {
    return null;
  }
}

const PRINT_STYLE_RETRY_CLIS = new Set(["claude", "kimi"]);

function getRetryCliCandidates(): string[] {
  const configPath = path.join(AUGUR_VAULT_CONFIG_DIR, "ai", "cli_agents.yaml");
  try {
    if (!fsSync.existsSync(configPath)) return [];
    const raw = fsSync.readFileSync(configPath, "utf-8");
    const data = yaml.parse(raw) ?? {};
    const agents = data?.agents;
    if (!agents || typeof agents !== "object") return [];
    return Object.entries(agents).flatMap(([id, config]) => {
        const cmd = (config as { cmd?: unknown })?.cmd;
        return PRINT_STYLE_RETRY_CLIS.has(id) && Array.isArray(cmd) && cmd.length > 0
          ? [id]
          : [];
      });
  } catch {
    return [];
  }
}

export function resolveCli(cliSetting: string = "auto"): string | null {
  if (cliSetting !== "auto") {
    return whichSync(cliSetting);
  }

  for (const candidate of getRetryCliCandidates()) {
    const resolved = whichSync(candidate);
    if (resolved) return resolved;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Diagnosis prompt
// ---------------------------------------------------------------------------

function buildPrompt(
  component: string,
  attempts: RetryAttemptLog[],
  context: string,
): string {
  const errorHistory = attempts
    .map((a) => `  Attempt ${a.attempt}: ${a.error}`)
    .join("\n");

  const mcpContext =
    component === "mcp_bridge"
      ? `\nArchitecture note: MCPBridge spawns a Python MCP server as a child process via stdio.
If signal is not null, the process was killed by a signal (not a timeout).
Common causes: parent Node.js process restart (HMR), SIGPIPE from broken pipe,
cleanup handler triggered by uncaughtException.
Exit code null with signal SIGTERM = killed by parent cleanup handler.
Exit code null with signal SIGKILL = OOM killer or force kill.\n`
      : "";

  return `You are a systems reliability engineer. A component is failing repeatedly.

Component: ${component}
Total attempts so far: ${attempts.length}
Context: ${context || "none"}
${mcpContext}
Previous attempt errors (most recent last):
${errorHistory || "  (no error details)"}

Analyze the errors and respond with ONLY valid JSON (no markdown fences):
{"root_cause": "one-line root cause", "suggestion": "actionable fix strategy", "should_retry": true_or_false}

If the errors indicate a permanent/config issue, set should_retry to false.
If the errors are transient and a retry might succeed, set should_retry to true.`;
}

function parseDiagnosis(raw: string): LLMDiagnosis {
  let text = raw.trim();
  // Strip markdown fences
  if (text.startsWith("```")) {
    const lines = text.split("\n").filter((l) => !l.startsWith("```"));
    text = lines.join("\n").trim();
  }

  try {
    const data = JSON.parse(text);
    return {
      rootCause: String(data.root_cause ?? ""),
      suggestion: String(data.suggestion ?? ""),
      shouldRetry: Boolean(data.should_retry ?? true),
      rawResponse: raw,
    };
  } catch {
    return {
      rootCause: "",
      suggestion: "",
      shouldRetry: true,
      rawResponse: raw,
    };
  }
}

// ---------------------------------------------------------------------------
// diagnoseWithLLM
// ---------------------------------------------------------------------------

export function diagnoseWithLLM(
  component: string,
  attempts: RetryAttemptLog[],
  context: string = "",
  config?: LLMRetryConfig,
): LLMDiagnosis {
  const cfg = config ?? loadRetryConfig();

  if (!isEnabledFor(cfg, component)) {
    return {
      rootCause: "",
      suggestion: "",
      shouldRetry: true,
      rawResponse: "",
    };
  }

  const cli = resolveCli(cfg.cli);
  if (!cli) {
    return {
      rootCause: "no_cli",
      suggestion: "No CLI binary found for LLM diagnosis",
      shouldRetry: true,
      rawResponse: "",
    };
  }

  const prompt = buildPrompt(component, attempts, context);

  try {
    const raw = execFileSync(
      cli,
      ["--print", "--max-turns", "1", "-p", prompt],
      {
        encoding: "utf-8",
        timeout: cfg.timeoutS * 1000,
      },
    );

    const diagnosis = parseDiagnosis(raw);
    logRetryEvent(component, attempts, diagnosis);
    return diagnosis;
  } catch {
    return {
      rootCause: "exec_error",
      suggestion: "",
      shouldRetry: true,
      rawResponse: "",
    };
  }
}

/**
 * Async wrapper for non-blocking diagnosis (e.g. MCPBridge).
 */
export async function diagnoseWithLLMAsync(
  component: string,
  attempts: RetryAttemptLog[],
  context: string = "",
  config?: LLMRetryConfig,
): Promise<LLMDiagnosis> {
  // Run synchronous call in a microtask to avoid blocking the event loop
  return new Promise((resolve) => {
    setImmediate(() => {
      resolve(diagnoseWithLLM(component, attempts, context, config));
    });
  });
}

// ---------------------------------------------------------------------------
// Event logging (JSONL)
// ---------------------------------------------------------------------------

export function logRetryEvent(
  component: string,
  attempts: RetryAttemptLog[],
  diagnosis: LLMDiagnosis,
): void {
  try {
    const event = {
      timestamp: new Date().toISOString(),
      component,
      attempt_count: attempts.length,
      attempts,
      diagnosis: {
        root_cause: diagnosis.rootCause,
        suggestion: diagnosis.suggestion,
        should_retry: diagnosis.shouldRetry,
      },
      host: os.hostname(),
      pid: process.pid,
    };

    const runtimeDir = AUGUR_RUNTIME_DIR;
    fsSync.mkdirSync(runtimeDir, { recursive: true });
    fsSync.appendFileSync(
      path.join(runtimeDir, "llm_retry_events.jsonl"),
      JSON.stringify(event) + "\n",
    );
  } catch {
    // Must never throw — called from retry paths
  }
}
