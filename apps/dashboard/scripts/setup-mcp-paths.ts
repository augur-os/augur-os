import path from "path";

import { getDashboardRoot } from "./lib/path-utils";

export interface SetupMcpInvocation {
  enabled: boolean;
  args: string[];
  label: string;
}

export function resolveSetupMcpPaths(dirname: string): {
  dashboardDir: string;
  repoRoot: string;
  configureScript: string;
} {
  const dashboardDir = getDashboardRoot(dirname);
  const repoRoot = path.resolve(dashboardDir, "..", "..");
  return {
    dashboardDir,
    repoRoot,
    configureScript: path.resolve(repoRoot, "scripts", "configure_mcp.py"),
  };
}

export function resolveSetupMcpInvocation(
  repoRoot: string,
  env: Record<string, string | undefined> = process.env,
): SetupMcpInvocation {
  const rawMode = env.AUGUR_DASHBOARD_SETUP_MCP?.trim();
  const mode = rawMode?.toLowerCase();

  if (mode === "0" || mode === "false" || mode === "off" || mode === "none" || mode === "skip") {
    return {
      enabled: false,
      args: [],
      label: "disabled",
    };
  }

  if (mode === "1" || mode === "true" || mode === "on" || mode === "all") {
    return {
      enabled: true,
      args: ["--repo-root", repoRoot, "--auto"],
      label: "all clients",
    };
  }

  const client = rawMode && rawMode.length > 0 ? rawMode : "generic";
  return {
    enabled: true,
    args: ["--repo-root", repoRoot, "--auto", "--client", client],
    label: client,
  };
}
