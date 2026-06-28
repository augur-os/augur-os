/**
 * MCP Bridge Preflight
 *
 * Resolves MCP client identity and runs preflight contract checks
 * before connecting to the MCP server.
 */

import { spawnSync } from "child_process";
import { createHash } from "crypto";
import fsSync from "fs";
import path from "path";
import { AUGUR_ROOT } from "../paths";
import { emitHealEvent } from "../self-heal-event";

const isTestEnv =
  process.env.NODE_ENV === "test" || process.env.JEST_WORKER_ID !== undefined;

const log = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.log(...args);
  }
};

export type PreflightContract = {
  project_root?: string;
  runtime_dir?: string;
  python_path?: string;
  mcp_port?: number;
  mcp_client_id?: string;
  instance_id?: string;
  instance_kind?: "main" | "worktree" | "isolated";
  browser_mode?: "visible_allowed" | "headless_only" | "isolated_visible";
  heal_policy?: "enabled" | "validation_only" | "disabled";
  visibility_policy?: "visible_allowed" | "no_visible_mutation";
  lifecycle_dir?: string;
  build_lock_dir?: string;
  browser_artifact_dir?: string;
  verify_passed?: boolean;
  incidents_detected?: Array<Record<string, unknown>>;
};

export function scopeDashboardProcessClientId(
  clientId: string,
  pid: number = process.pid,
): string {
  const normalized = clientId.trim();
  if (!normalized.startsWith("dashboard-")) {
    return normalized;
  }

  const base = normalized.replace(/-p\d+$/, "");
  return `${base}-p${pid}`;
}

export function resolveMcpClientId(): string {
  const explicit = (process.env.AUGUR_MCP_CLIENT_ID || "").trim();
  if (explicit) {
    return scopeDashboardProcessClientId(explicit);
  }

  // Prefer cwd so worktree-local dashboard instances get isolated MCP client IDs
  // even if AUGUR_ROOT is inherited from a parent shell.
  const root = (process.cwd() || process.env.AUGUR_ROOT || AUGUR_ROOT).trim();
  const rootBase =
    path
      .basename(root)
      .replace(/[^a-zA-Z0-9_-]/g, "-")
      .toLowerCase() || "dashboard";
  const rootHash = createHash("sha1").update(root).digest("hex").slice(0, 8);
  return scopeDashboardProcessClientId(`dashboard-${rootBase}-${rootHash}`);
}

function isWindowsStorePythonAlias(candidate: string): boolean {
  const normalized = candidate.replace(/\\/g, "/").toLowerCase();
  return normalized.includes("/microsoft/windowsapps/python");
}

export function resolvePreflightPython(fallbackRoot: string): string {
  const explicit = process.env.AUGUR_PYTHON?.trim();
  if (explicit && !isWindowsStorePythonAlias(explicit)) {
    return explicit;
  }

  const candidates =
    process.platform === "win32"
      ? [
          path.join(fallbackRoot, ".venv", "Scripts", "python.exe"),
          path.join(fallbackRoot, ".venv", "Scripts", "python3.exe"),
          path.join(fallbackRoot, ".venv", "bin", "python3"),
          path.join(fallbackRoot, ".venv", "bin", "python"),
        ]
      : [
          path.join(fallbackRoot, ".venv", "bin", "python3"),
          path.join(fallbackRoot, ".venv", "bin", "python"),
          path.join(fallbackRoot, ".venv", "Scripts", "python.exe"),
        ];

  for (const candidate of candidates) {
    if (fsSync.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function isInsideRoot(candidateRoot: string | undefined, cwd: string): boolean {
  if (!candidateRoot?.trim()) {
    return false;
  }
  const root = path.resolve(candidateRoot.trim());
  const relative = path.relative(root, path.resolve(cwd));
  return relative === "" || (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function resolvePreflightRoot(): string {
  const cwd = process.cwd();
  const envRoot = process.env.AUGUR_ROOT?.trim();
  const bundledRoot = AUGUR_ROOT?.trim();

  if (isInsideRoot(envRoot, cwd)) {
    return path.resolve(envRoot!);
  }
  if (isInsideRoot(bundledRoot, cwd)) {
    return path.resolve(bundledRoot!);
  }

  return (bundledRoot || envRoot || cwd).trim();
}

export function resolvePreflightContract(): PreflightContract {
  const fallbackRoot = resolvePreflightRoot();
  const scriptPath = path.join(
    fallbackRoot,
    "scripts",
    "worktree_preflight.py",
  );
  const preflightPython = resolvePreflightPython(fallbackRoot);

  // @spawn-exempt: MCP-server preflight/bootstrap check — part of establishing the
  // MCP transport, which cannot itself be routed through MCP. See ADR-817.
  const result = spawnSync(
    preflightPython,
    [scriptPath, "--root", fallbackRoot, "--profile", "mcp", "--repair"],
    {
      cwd: fallbackRoot,
      env: process.env,
      encoding: "utf-8",
    },
  );

  if (!result.stdout?.trim()) {
    emitHealEvent({
      source: "MCPBridge/preflight",
      category: "bootstrap",
      severity: "medium",
      message: `Preflight produced no JSON output${result.stderr ? `: ${result.stderr.trim()}` : ""}`,
    });
    return {};
  }

  try {
    const parsed = JSON.parse(result.stdout) as PreflightContract;
    if (parsed.verify_passed === false) {
      emitHealEvent({
        source: "MCPBridge/preflight",
        category: "bootstrap",
        severity: "medium",
        message: "MCP preflight completed with unresolved requirements",
        context: {
          incidents: parsed.incidents_detected ?? [],
        },
      });
    }
    return parsed;
  } catch (error) {
    emitHealEvent({
      source: "MCPBridge/preflight",
      category: "bootstrap",
      severity: "medium",
      message: `Failed to parse MCP preflight output: ${String(error)}`,
      context: {
        stdout: result.stdout.slice(0, 1000),
        stderr: result.stderr.slice(0, 1000),
      },
    });
    return {};
  }
}
