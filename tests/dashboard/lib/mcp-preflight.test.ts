jest.mock("child_process", () => ({
  spawnSync: jest.fn(),
}));

jest.mock("fs", () => ({
  __esModule: true,
  default: {
    existsSync: jest.fn(),
  },
  existsSync: jest.fn(),
}));

jest.mock("@/lib/paths", () => ({
  AUGUR_ROOT: "/repo",
}));

import { spawnSync } from "child_process";
import fsSync from "fs";
import path from "path";
import {
  resolveMcpClientId,
  resolvePreflightPython,
  resolvePreflightContract,
  scopeDashboardProcessClientId,
} from "@/lib/mcp/preflight";

describe("mcp preflight client ids", () => {
  const originalEnv = process.env.AUGUR_MCP_CLIENT_ID;
  const originalAugurRoot = process.env.AUGUR_ROOT;
  const originalAugurPython = process.env.AUGUR_PYTHON;
  const originalCwd = process.cwd;
  const originalPlatform = Object.getOwnPropertyDescriptor(process, "platform");

  const mockExistsSync = fsSync.existsSync as jest.Mock;

  function expectedFallbackPython(): string {
    return process.platform === "win32" ? "python" : "python3";
  }

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.AUGUR_MCP_CLIENT_ID;
    } else {
      process.env.AUGUR_MCP_CLIENT_ID = originalEnv;
    }
    if (originalAugurRoot === undefined) {
      delete process.env.AUGUR_ROOT;
    } else {
      process.env.AUGUR_ROOT = originalAugurRoot;
    }
    if (originalAugurPython === undefined) {
      delete process.env.AUGUR_PYTHON;
    } else {
      process.env.AUGUR_PYTHON = originalAugurPython;
    }
    if (originalPlatform) {
      Object.defineProperty(process, "platform", originalPlatform);
    }
    process.cwd = originalCwd;
    jest.clearAllMocks();
  });

  it("scopes dashboard client ids to the current process", () => {
    expect(scopeDashboardProcessClientId("dashboard-augur-deadbeef", 4242)).toBe(
      "dashboard-augur-deadbeef-p4242",
    );
    expect(
      scopeDashboardProcessClientId("dashboard-augur-deadbeef-p1111", 4242),
    ).toBe("dashboard-augur-deadbeef-p4242");
  });

  it("leaves non-dashboard client ids unchanged", () => {
    expect(scopeDashboardProcessClientId("codex-thread-123", 4242)).toBe(
      "codex-thread-123",
    );
  });

  it("normalizes explicit dashboard env ids through the process scope", () => {
    process.env.AUGUR_MCP_CLIENT_ID = "dashboard-augur-deadbeef";
    expect(resolveMcpClientId()).toBe(`dashboard-augur-deadbeef-p${process.pid}`);
  });

  it("runs worktree preflight from the repo root instead of dashboard cwd", () => {
    delete process.env.AUGUR_ROOT;
    process.cwd = () => "/repo/apps/dashboard";
    const expectedRoot = path.resolve("/repo");
    (spawnSync as jest.Mock).mockReturnValue({
      stdout: '{"verify_passed":true}',
      stderr: "",
    });

    resolvePreflightContract();

    expect(spawnSync).toHaveBeenCalledWith(
      expectedFallbackPython(),
      [
        path.join(expectedRoot, "scripts", "worktree_preflight.py"),
        "--root",
        expectedRoot,
        "--profile",
        "mcp",
        "--repair",
      ],
      expect.objectContaining({
        cwd: expectedRoot,
      }),
    );
  });

  it("uses the resolved worktree root when AUGUR_ROOT is inherited from another checkout", () => {
    process.env.AUGUR_ROOT = "/stale/augur-worktree";
    process.cwd = () => "/repo/apps/dashboard";
    const expectedRoot = path.resolve("/repo");
    (spawnSync as jest.Mock).mockReturnValue({
      stdout: '{"verify_passed":true}',
      stderr: "",
    });

    resolvePreflightContract();

    expect(spawnSync).toHaveBeenCalledWith(
      expectedFallbackPython(),
      [
        path.join(expectedRoot, "scripts", "worktree_preflight.py"),
        "--root",
        expectedRoot,
        "--profile",
        "mcp",
        "--repair",
      ],
      expect.objectContaining({
        cwd: expectedRoot,
      }),
    );
  });

  it("preserves dashboard instance metadata from preflight stdout", () => {
    (spawnSync as jest.Mock).mockReturnValue({
      stdout: JSON.stringify({
        verify_passed: true,
        instance_id: "worktree:task-2",
        instance_kind: "worktree",
        browser_mode: "headless_only",
        heal_policy: "validation_only",
        visibility_policy: "no_visible_mutation",
        lifecycle_dir: "C:\\runtime\\daemon\\dashboard\\worktrees\\task-2",
        build_lock_dir: "C:\\runtime\\locks\\dashboard\\worktrees\\task-2",
        browser_artifact_dir: "C:\\runtime\\browser-verification\\worktrees\\task-2",
      }),
      stderr: "",
    });

    const contract = resolvePreflightContract();

    expect(contract).toEqual(
      expect.objectContaining({
        instance_id: "worktree:task-2",
        instance_kind: "worktree",
        browser_mode: "headless_only",
        heal_policy: "validation_only",
        visibility_policy: "no_visible_mutation",
        lifecycle_dir: "C:\\runtime\\daemon\\dashboard\\worktrees\\task-2",
        build_lock_dir: "C:\\runtime\\locks\\dashboard\\worktrees\\task-2",
        browser_artifact_dir: "C:\\runtime\\browser-verification\\worktrees\\task-2",
      }),
    );
  });

  it("prefers live AUGUR_ROOT when dashboard cwd is inside that checkout", () => {
    const liveRoot = path.join(path.parse(process.cwd()).root, "live-augur");
    process.env.AUGUR_ROOT = liveRoot;
    process.cwd = () => path.join(liveRoot, "apps", "dashboard");
    (spawnSync as jest.Mock).mockReturnValue({
      stdout: '{"verify_passed":true}',
      stderr: "",
    });

    resolvePreflightContract();

    expect(spawnSync).toHaveBeenCalledWith(
      expectedFallbackPython(),
      [
        path.join(liveRoot, "scripts", "worktree_preflight.py"),
        "--root",
        liveRoot,
        "--profile",
        "mcp",
        "--repair",
      ],
      expect.objectContaining({
        cwd: liveRoot,
      }),
    );
  });

  it("prefers AUGUR_PYTHON for worktree preflight", () => {
    process.env.AUGUR_PYTHON = path.join("/repo", ".venv", "Scripts", "python.exe");
    expect(resolvePreflightPython("/repo")).toBe(process.env.AUGUR_PYTHON);
  });

  it("prefers the Windows virtualenv interpreter over Store aliases", () => {
    Object.defineProperty(process, "platform", { value: "win32" });
    process.env.AUGUR_PYTHON =
      "C:\\Users\\tester\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe";
    const venvPython = path.join("/repo", ".venv", "Scripts", "python.exe");
    mockExistsSync.mockImplementation((candidate: string) => candidate === venvPython);

    expect(resolvePreflightPython("/repo")).toBe(venvPython);
  });
});
