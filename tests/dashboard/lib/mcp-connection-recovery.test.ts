/**
 * @jest-environment node
 */

jest.mock("@/lib/paths", () => ({
  AUGUR_ROOT: "/repo",
  AUGUR_PYTHON: "python3",
}));

jest.mock("@/lib/mcp/preflight", () => ({
  resolvePreflightContract: jest.fn(),
  resolveMcpClientId: jest.fn(() => "dashboard-test"),
  scopeDashboardProcessClientId: jest.fn((clientId: string) => clientId),
}));

jest.mock("@/lib/mcp/cleanup", () => ({
  registerCleanupHandlers: jest.fn(),
}));

import { spawn } from "child_process";
import fsSync from "fs";
import path from "path";
import { MCPBridge, resolveMcpPythonPath } from "@/lib/mcp/connection";
import { resolvePreflightContract } from "@/lib/mcp/preflight";

type MutableBridge = MCPBridge & {
  permanentFailure: string | null;
  lastLaunchSignature: string | null;
};

function launchSignature(pythonCmd: string): string {
  return JSON.stringify({
    augurRoot: "/repo",
    pythonCmd,
    runtimeDir: "/state",
    mcpPort: 8081,
    clientId: "dashboard-test",
  });
}

function makeMockProcess() {
  return {
    stdin: {
      write: jest.fn((_message: string, cb?: (error?: Error | null) => void) => {
        cb?.(null);
      }),
    },
    stdout: { on: jest.fn() },
    stderr: { on: jest.fn() },
    on: jest.fn(),
    unref: jest.fn(),
    kill: jest.fn(),
    exitCode: null,
    pid: 4242,
  };
}

describe("MCPBridge permanent failure recovery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (MCPBridge as unknown as { instance: MCPBridge | null }).instance = null;
    jest
      .spyOn(MCPBridge.prototype as unknown as { waitForReady: () => Promise<void> }, "waitForReady")
      .mockResolvedValue(undefined);
    (spawn as jest.Mock).mockReturnValue(makeMockProcess());
  });

  afterEach(() => {
    jest.restoreAllMocks();
    (MCPBridge as unknown as { instance: MCPBridge | null }).instance = null;
    delete (globalThis as typeof globalThis & { __mcp_bridge__?: unknown })
      .__mcp_bridge__;
  });

  it("retries after preflight resolves a different python interpreter", async () => {
    (resolvePreflightContract as jest.Mock).mockReturnValue({
      project_root: "/repo",
      python_path: "/repo/.venv/bin/python3",
      runtime_dir: "/state",
      mcp_port: 8081,
      mcp_client_id: "dashboard-test",
      verify_passed: true,
    });

    const bridge = MCPBridge.getInstance() as MutableBridge;
    bridge.permanentFailure =
      "MCP server failed: missing Python module 'mcp'. Run: make install";
    bridge.lastLaunchSignature = launchSignature("python3");

    await bridge.connect();

    expect(spawn).toHaveBeenCalledWith(
      "/repo/.venv/bin/python3",
      expect.arrayContaining([
        "-m",
        "augur_framework",
        "--client-id",
        "dashboard-test",
      ]),
      expect.objectContaining({
        cwd: "/repo",
        env: expect.objectContaining({
          AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS: "1",
          AUGUR_MCP_INCLUDE_VAULT_TIER_TOOLS: "1",
        }),
      }),
    );
    expect(bridge.getDebugState().permanentFailure).toBeNull();
  });

  it("preserves the cached permanent failure when the launch contract is unchanged", async () => {
    (resolvePreflightContract as jest.Mock).mockReturnValue({
      project_root: "/repo",
      python_path: "python3",
      runtime_dir: "/state",
      mcp_port: 8081,
      mcp_client_id: "dashboard-test",
      verify_passed: true,
    });

    const bridge = MCPBridge.getInstance() as MutableBridge;
    bridge.permanentFailure =
      "MCP server failed: missing Python module 'mcp'. Run: make install";
    bridge.lastLaunchSignature = launchSignature("python3");

    await expect(bridge.connect()).rejects.toThrow(
      "MCP server failed: missing Python module 'mcp'. Run: make install",
    );
    expect(spawn).not.toHaveBeenCalled();
  });

  it("replaces stale development singleton instances after hot reload", () => {
    const originalNodeEnv = process.env.NODE_ENV;
    try {
      process.env.NODE_ENV = "development";
      const staleBridge = { disconnect: jest.fn() };
      (globalThis as typeof globalThis & { __mcp_bridge__?: unknown })
        .__mcp_bridge__ = staleBridge;

      const bridge = MCPBridge.getInstance();

      expect(staleBridge.disconnect).toHaveBeenCalledTimes(1);
      expect(bridge).toBeInstanceOf(MCPBridge);
      expect(
        (globalThis as typeof globalThis & { __mcp_bridge__?: unknown })
          .__mcp_bridge__,
      ).toBe(bridge);
    } finally {
      process.env.NODE_ENV = originalNodeEnv;
    }
  });

  it("filters inherited PYTHONPATH entries that shadow the MCP SDK package", () => {
    const shadowingEntry = path.resolve("/repo/project-brain/capabilities/skills/daemon/scripts");
    const inheritedEntry = path.resolve("/repo/other-tools");
    const existsSpy = jest
      .spyOn(fsSync, "existsSync")
      .mockImplementation(
        (candidate) =>
          path.resolve(String(candidate)) ===
          path.join(shadowingEntry, "mcp", "__init__.py"),
      );

    const resolved = resolveMcpPythonPath(
      path.resolve("/repo"),
      [shadowingEntry, inheritedEntry, shadowingEntry].join(path.delimiter),
    ).split(path.delimiter);

    expect(resolved).toEqual([
      path.join(path.resolve("/repo"), "src", "mcp"),
      path.resolve("/repo"),
      inheritedEntry,
    ]);
    expect(existsSpy).toHaveBeenCalled();
  });
});
