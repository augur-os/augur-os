// Compiled to scripts/dist/setup-mcp.mjs by build-scripts.mjs
/**
 * Auto-configure MCP servers for a safe dashboard bootstrap target.
 *
 * Called automatically during `npm run dev` and `npm run build`.
 * Uses configure_mcp.py --auto for silent, idempotent setup.
 * Defaults to the repo-local generic target to avoid macOS prompting for
 * protected app-container access during dashboard startup.
 *
 * Set AUGUR_DASHBOARD_SETUP_MCP=all to configure every client, or set it to a
 * concrete configure_mcp.py --client value such as codex-cli.
 */

import { spawn } from "child_process";
import { existsSync } from "fs";
import { dirname } from "path";
import { fileURLToPath } from "url";
import { resolveSetupMcpInvocation, resolveSetupMcpPaths } from "./setup-mcp-paths";

const scriptFilename = fileURLToPath(import.meta.url);
const scriptDir = dirname(scriptFilename);

const { repoRoot, configureScript } = resolveSetupMcpPaths(scriptDir);

async function setupMcp(): Promise<void> {
  // Check if configure script exists
  if (!existsSync(configureScript)) {
    console.log("[setup-mcp] configure_mcp.py not found, skipping MCP setup");
    return;
  }

  // Find Python interpreter
  const pythonCandidates = ["python3", "python"];
  let pythonCmd = "python3";

  for (const candidate of pythonCandidates) {
    try {
      const result = await runCommand(candidate, ["--version"]);
      if (result.success) {
        pythonCmd = candidate;
        break;
      }
    } catch {
      // Continue to next candidate
    }
  }

  const invocation = resolveSetupMcpInvocation(repoRoot);
  if (!invocation.enabled) {
    console.log("[setup-mcp] MCP setup disabled by AUGUR_DASHBOARD_SETUP_MCP");
    return;
  }

  // Run configure_mcp.py --auto (silent auto-apply)
  console.log(`[setup-mcp] Checking MCP configuration (${invocation.label})...`);

  const result = await runCommand(pythonCmd, [
    configureScript,
    ...invocation.args,
  ]);

  if (!result.success) {
    console.warn(
      "[setup-mcp] MCP setup had issues (non-fatal):",
      result.stderr,
    );
  } else if (result.stdout.includes("updated")) {
    console.log("[setup-mcp]", result.stdout.trim());
  }
  // Silent on success with no changes needed
}

interface CommandResult {
  success: boolean;
  stdout: string;
  stderr: string;
}

function runCommand(cmd: string, args: string[]): Promise<CommandResult> {
  return new Promise((resolve) => {
    const proc = spawn(cmd, args, {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        AUGUR_ROOT: repoRoot,
        AUGUR_CORE: repoRoot,
        AUGUR_REPO: repoRoot,
        PYTHONPATH: repoRoot,
      },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout?.on("data", (data) => {
      stdout += data.toString();
    });
    proc.stderr?.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      resolve({ success: code === 0, stdout, stderr });
    });

    proc.on("error", (err) => {
      resolve({ success: false, stdout: "", stderr: err.message });
    });
  });
}

setupMcp().catch((err) => {
  console.error("[setup-mcp] Error:", err);
  // Non-fatal - don't block dev server
});

export { setupMcp };
