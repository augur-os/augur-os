/**
 * @jest-environment node
 */
import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import path from "path";

// --- MCPBridge mock (must come before any import that loads actions) ---
const mockCall = jest.fn();

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: (...a: unknown[]) => mockCall(...a),
  MCPBridge: class {
    static parseJSON(result: { content?: Array<{ type: string; text: string }> }) {
      const text = result.content?.[0]?.text ?? "{}";
      return JSON.parse(text);
    }
    static extractText(result: { content?: Array<{ type: string; text: string }> }) {
      return result.content?.[0]?.text ?? "";
    }
  },
}));

// --- Server-side deps ---
jest.mock("@/lib/auth/server-action", () => ({
  auth: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/lib/paths", () => ({
  AUGUR_ROOT: "/tmp/augur-test",
  getSkillSubPath: jest.fn((_skill: string, _sub: string) => "/tmp/augur-test/voice-memos"),
}));

jest.mock("fs/promises", () => ({
  stat: jest.fn(),
  readFile: jest.fn(),
  mkdir: jest.fn().mockResolvedValue(undefined),
  unlink: jest.fn(),
}));

jest.mock("yaml", () => ({
  parse: jest.fn(() => ({
    items: [{ audio_path: path.resolve("/tmp/augur-test/test.m4a") }],
  })),
}));

// Keep child_process.spawn available (used by openWorkspaceFile helpers not being migrated)
jest.mock("child_process", () => ({
  spawn: jest.fn(() => {
    const ee = { once: jest.fn() };
    return ee;
  }),
}));

jest.mock("@/lib/server/spawn", () => ({
  runCommand: jest.fn(),
}));

// Helper: build a successful MCP tool result
function mcpSuccess() {
  return {
    isError: false as const,
    content: [{ type: "text" as const, text: JSON.stringify({ success: true }) }],
  };
}

// Helper: build a failed MCP tool result (tool error flag)
function mcpError(msg = "mcp error") {
  return {
    isError: true as const,
    content: [{ type: "text" as const, text: msg }],
  };
}

// Helper: build a tool result that returns success:false in JSON
function mcpSuccessFalse(msg = "tool said no") {
  return {
    isError: false as const,
    content: [{ type: "text" as const, text: JSON.stringify({ success: false, error: msg }) }],
  };
}

describe("actions open* route through system-open MCP, not spawn", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let fsMock: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let actions: typeof import("@/app/actions");

  beforeEach(async () => {
    mockCall.mockReset();
    jest.resetModules();

    // Re-mock fs/promises each time (jest.resetModules clears module registry)
    jest.mock("fs/promises", () => ({
      stat: jest.fn(),
      readFile: jest.fn(),
      mkdir: jest.fn().mockResolvedValue(undefined),
      unlink: jest.fn(),
    }));

    // Re-import actions after resetting modules
    actions = await import("@/app/actions");
    fsMock = (await import("fs/promises")) as unknown as { stat: jest.MockedFunction<() => Promise<unknown>>; readFile: jest.MockedFunction<() => Promise<unknown>> };
  });

  // ─── openFile ─────────────────────────────────────────────────────────────

  it("openFile dispatches to system-open MCP tool with the resolved path", async () => {
    const testPath = "/tmp/augur-test/example.md";
    fsMock.stat.mockResolvedValue({ isFile: () => true, isDirectory: () => false });
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openFile(testPath);

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toMatch(/system-open/);
    expect(args["target"]).toBe(path.resolve(testPath));
    expect(result).toEqual({ success: true });
  });

  it("openFile returns error when MCP call has isError=true", async () => {
    fsMock.stat.mockResolvedValue({ isFile: () => true, isDirectory: () => false });
    mockCall.mockResolvedValue(mcpError("something went wrong"));

    const result = await actions.openFile("/tmp/augur-test/example.md");

    expect(result).toEqual({ success: false, error: "Failed to open file in editor" });
  });

  it("openFile returns error when MCP returns success:false", async () => {
    fsMock.stat.mockResolvedValue({ isFile: () => true, isDirectory: () => false });
    mockCall.mockResolvedValue(mcpSuccessFalse("File not found"));

    const result = await actions.openFile("/tmp/augur-test/example.md");

    expect(result).toEqual({ success: false, error: "File not found" });
  });

  // ─── openFileInSystem ─────────────────────────────────────────────────────

  it("openFileInSystem dispatches to system-open MCP tool with the resolved path", async () => {
    const testPath = "/tmp/augur-test/photo.png";
    fsMock.stat.mockResolvedValue({ isFile: () => true, isDirectory: () => false });
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openFileInSystem(testPath);

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toMatch(/system-open/);
    expect(args["target"]).toBe(path.resolve(testPath));
    expect(result).toEqual({ success: true });
  });

  // ─── openDirectoryInSystem ────────────────────────────────────────────────

  it("openDirectoryInSystem dispatches to system-open MCP tool with the resolved dir", async () => {
    const testDir = "/tmp/augur-test";
    fsMock.stat.mockResolvedValue({ isFile: () => false, isDirectory: () => true });
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openDirectoryInSystem(testDir);

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toMatch(/system-open/);
    expect(String(args["target"])).toContain("/tmp/augur-test");
    expect(result).toEqual({ success: true });
  });

  // ─── openRepoInEditor ─────────────────────────────────────────────────────

  it("openRepoInEditor dispatches to system-open MCP tool with AUGUR_ROOT", async () => {
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openRepoInEditor();

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toMatch(/system-open/);
    expect(args["target"]).toBe("/tmp/augur-test");
    expect(result).toEqual({ success: true });
  });

  // ─── settings URL functions ────────────────────────────────────────────────

  it("openScreenRecordingSettings dispatches system-open with the settings URL on macOS", async () => {
    // Skip on non-macOS (the function returns early with an error)
    if (process.platform !== "darwin") {
      return;
    }
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openScreenRecordingSettings();

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toBe("system-open");
    expect(String(args["target"])).toContain("x-apple.systempreferences");
    expect(String(args["target"])).toContain("Privacy_ScreenCapture");
    expect(result).toEqual({ success: true });
  });

  it("openMicrophoneSettings dispatches system-open with the microphone settings URL on macOS", async () => {
    if (process.platform !== "darwin") {
      return;
    }
    mockCall.mockResolvedValue(mcpSuccess());

    const result = await actions.openMicrophoneSettings();

    expect(mockCall).toHaveBeenCalled();
    const [tool, args] = mockCall.mock.calls[0] as [string, Record<string, unknown>];
    expect(tool).toBe("system-open");
    expect(String(args["target"])).toContain("Privacy_Microphone");
    expect(result).toEqual({ success: true });
  });
});
