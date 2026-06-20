/**
 * MCP Bridge Diagnostics
 *
 * Permanent failure diagnosis from stderr output and LLM-assisted
 * reconnection diagnosis (ADR-106).
 */

const isTestEnv =
  process.env.NODE_ENV === "test" || process.env.JEST_WORKER_ID !== undefined;

const log = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.log(...args);
  }
};

const warn = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.warn(...args);
  }
};

/**
 * Diagnose permanent failures from stderr output.
 * Returns a user-friendly error message, or null if the failure is transient.
 */
export function diagnosePermanentFailure(stderr: string): string | null {
  // Missing Python dependencies
  const moduleMatch = stderr.match(
    /ModuleNotFoundError: No module named '([^']+)'/,
  );
  if (moduleMatch) {
    return (
      `MCP server failed: missing Python module '${moduleMatch[1]}'. ` +
      `Run: make install  (or: uv pip install -e src/mcp)`
    );
  }

  // augur-mcp's own dependency check message
  if (stderr.includes("Missing required dependencies:")) {
    const depsMatch = stderr.match(/Missing required dependencies: (.+)/);
    return (
      `MCP server failed: missing dependencies${depsMatch ? `: ${depsMatch[1]}` : ""}. ` +
      `Run: make install`
    );
  }

  // Python not found
  if (
    stderr.includes("No such file or directory") &&
    stderr.includes("python")
  ) {
    return (
      "MCP server failed: Python not found. " +
      "Run: make install  (creates .venv with correct Python)"
    );
  }

  // SyntaxError — wrong Python version or corrupt code
  if (stderr.includes("SyntaxError:")) {
    return (
      "MCP server failed: Python syntax error (possibly wrong Python version). " +
      "Requires Python >=3.10."
    );
  }

  // Lock contention is transient — the other process may die or release.
  // Do NOT treat as permanent failure; let reconnect logic retry with --force.

  return null;
}

/**
 * ADR-106: Trigger async LLM diagnosis when reconnect attempts hit threshold.
 * Non-blocking — does not delay the reconnection attempt.
 * Fires at most once per recovery session to avoid wasting API calls.
 */
export function tryLLMDiagnosis(
  reconnectAttempts: number,
  reconnectAttemptLogs: Array<{ attempt: number; error: string; timestamp: string }>,
  lastStderrOutput: string,
  diagnosisAttempted: boolean,
): boolean {
  if (diagnosisAttempted) return false;

  try {
    // Dynamic import to avoid hard dependency
    const {
      loadRetryConfig,
      isEnabledFor,
      diagnoseWithLLMAsync,
    } = require("../llm-retry");
    const config = loadRetryConfig();
    if (reconnectAttempts !== config.triggerAttempt) return false;
    if (!isEnabledFor(config, "mcp_bridge")) return false;

    diagnoseWithLLMAsync(
      "mcp_bridge",
      reconnectAttemptLogs,
      `stderr: ${lastStderrOutput.slice(0, 500)}`,
      config,
    )
      .then((diagnosis: { suggestion?: string; shouldRetry?: boolean }) => {
        if (diagnosis.suggestion) {
          log(`[MCPBridge] LLM diagnosis: ${diagnosis.suggestion}`);
        }
        if (diagnosis.shouldRetry === false) {
          warn(
            "[MCPBridge] LLM suggests issue may be permanent — reconnection continues regardless",
          );
        }
      })
      .catch(() => {
        // Never block reconnection
      });

    return true; // diagnosis was attempted
  } catch {
    // Module not available — skip silently
    return false;
  }
}
