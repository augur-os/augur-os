/**
 * Shared health check protocol for Augur platform plugins (ADR-437).
 *
 * All plugins use the same health check:
 * 1. Check install dir exists
 * 2. Check MCP server reachable
 * 3. Check dashboard reachable
 * 4. Read last sync timestamp from state dir
 */

import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export interface AugurHealth {
  installed: boolean;
  mcp_healthy: boolean;
  dashboard_running: boolean;
  last_sync: string | null;
}

export function getInstallDir(): string {
  return process.env.AUGUR_DIR || path.join(os.homedir(), "Projects", "Augur");
}

export function getStateDir(): string {
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "Augur", "state");
  }
  // Linux/other: use XDG
  const xdgState = process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(xdgState, "augur");
}

export function detectInstalled(): boolean {
  const dir = getInstallDir();
  return fs.existsSync(dir) && fs.existsSync(path.join(dir, ".git"));
}

export async function checkMcpHealth(port: number = 3001): Promise<boolean> {
  try {
    const resp = await fetch(`http://localhost:${port}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function checkDashboardHealth(port: number = 3000): Promise<boolean> {
  try {
    const resp = await fetch(`http://localhost:${port}`, {
      signal: AbortSignal.timeout(3000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export function readLastSync(): string | null {
  const stateFile = path.join(getStateDir(), "install-source.json");
  if (!fs.existsSync(stateFile)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
    return data.installed_at || null;
  } catch {
    return null;
  }
}

export async function fullHealthCheck(
  dashboardPort: number = 3000,
  mcpPort: number = 3001,
): Promise<AugurHealth> {
  const installed = detectInstalled();
  if (!installed) {
    return { installed: false, mcp_healthy: false, dashboard_running: false, last_sync: null };
  }

  const [mcp_healthy, dashboard_running] = await Promise.all([
    checkMcpHealth(mcpPort),
    checkDashboardHealth(dashboardPort),
  ]);

  return {
    installed,
    mcp_healthy,
    dashboard_running,
    last_sync: readLastSync(),
  };
}
