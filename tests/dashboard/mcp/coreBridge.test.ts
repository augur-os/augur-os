/**
 * @jest-environment node
 *
 * Unit test: MCPBridge per-module singleton keying.
 *
 * getInstance() does NOT spawn — only connect() does — so this test
 * needs no spawn mock and starts no child processes.
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

import { describe, it, expect, beforeEach, afterEach } from "@jest/globals";
import { MCPBridge } from "@/lib/mcp/connection";

describe("MCPBridge per-module instances", () => {
  beforeEach(() => {
    // Reset static framework singleton (backward-compat field)
    (MCPBridge as unknown as { instance: MCPBridge | null }).instance = null;
    // Reset per-module Map for non-framework singletons
    (MCPBridge as unknown as { instances: Map<string, MCPBridge> }).instances.clear();
  });

  afterEach(() => {
    (MCPBridge as unknown as { instance: MCPBridge | null }).instance = null;
    (MCPBridge as unknown as { instances: Map<string, MCPBridge> }).instances.clear();
  });

  it("returns distinct instances per server module and reuses each", () => {
    const fw1 = MCPBridge.getInstance();
    const fw2 = MCPBridge.getInstance("augur_framework");
    const core1 = MCPBridge.getInstance("augur_core");
    const core2 = MCPBridge.getInstance("augur_core");

    // Framework singleton: no-arg and explicit "augur_framework" must be the same object
    expect(fw1).toBe(fw2);

    // Core singleton: two calls for the same module must return the same object
    expect(core1).toBe(core2);

    // Core and framework are distinct instances
    expect(core1).not.toBe(fw1);

    // Core instance carries the correct serverModule
    expect((core1 as any).serverModule).toBe("augur_core");
  });

  it("framework singleton serverModule is augur_framework", () => {
    const fw = MCPBridge.getInstance();
    expect((fw as any).serverModule).toBe("augur_framework");
  });
});
