/**
 * @jest-environment node
 */
import path from "path";

import { resolveSetupMcpPaths } from "@/scripts/setup-mcp-paths";
import { resolveSetupMcpInvocation } from "@/scripts/setup-mcp-paths";

describe("setup-mcp path resolution", () => {
  it("resolves repo root from compiled scripts/dist directory", () => {
    const repoRoot = path.join(path.sep, "repo");
    const compiledDir = path.join(repoRoot, "apps", "dashboard", "scripts", "dist");

    expect(resolveSetupMcpPaths(compiledDir)).toEqual({
      dashboardDir: path.join(repoRoot, "apps", "dashboard"),
      repoRoot,
      configureScript: path.join(repoRoot, "scripts", "configure_mcp.py"),
    });
  });

  it("resolves repo root from source scripts directory", () => {
    const repoRoot = path.join(path.sep, "repo");
    const sourceDir = path.join(repoRoot, "apps", "dashboard", "scripts");

    expect(resolveSetupMcpPaths(sourceDir)).toEqual({
      dashboardDir: path.join(repoRoot, "apps", "dashboard"),
      repoRoot,
      configureScript: path.join(repoRoot, "scripts", "configure_mcp.py"),
    });
  });
});

describe("setup-mcp invocation policy", () => {
  it("defaults to the repo-local generic MCP config during dashboard bootstrap", () => {
    const invocation = resolveSetupMcpInvocation("/repo", {});

    expect(invocation).toEqual({
      enabled: true,
      args: ["--repo-root", "/repo", "--auto", "--client", "generic"],
      label: "generic",
    });
  });

  it("only configures every app client when explicitly requested", () => {
    const invocation = resolveSetupMcpInvocation("/repo", {
      AUGUR_DASHBOARD_SETUP_MCP: "all",
    });

    expect(invocation).toEqual({
      enabled: true,
      args: ["--repo-root", "/repo", "--auto"],
      label: "all clients",
    });
  });

  it("can disable dashboard bootstrap MCP setup", () => {
    const invocation = resolveSetupMcpInvocation("/repo", {
      AUGUR_DASHBOARD_SETUP_MCP: "none",
    });

    expect(invocation).toEqual({
      enabled: false,
      args: [],
      label: "disabled",
    });
  });
});
