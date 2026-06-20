/**
 * @jest-environment node
 */

import {
  EXEC_ORPHAN_CLEANUP_MS,
  POST,
} from "@/app/api/cli/exec/route";
import { execStore } from "@/app/api/cli/exec/exec-store";
import { pty } from "@/app/api/cli/pty-setup";

jest.mock("@/app/api/cli/cli-config", () => ({
  AUGUR_ROOT: "/augur/root",
  buildCliSpawnEnv: jest.fn(() => ({ PATH: "/mock/path", COLORFGBG: "15;0" })),
  getCliAgentsConfig: jest.fn(() => ({
    claude: {
      cmd: ["claude"],
      print_cmd: ["claude", "-p", "--output-format", "stream-json"],
    },
    codex: {
      cmd: ["codex"],
      print_cmd: ["codex", "exec", "--json"],
    },
  })),
  isNonEmptyString: (value: unknown) =>
    typeof value === "string" && value.length > 0,
  resolveDefaultCliId: jest.fn(() => "claude"),
  resolveSpawnCommand: jest.fn((cmd: string) => `/resolved/${cmd}`),
}));

const mockResolveDefaultCliId = jest.requireMock("@/app/api/cli/cli-config")
  .resolveDefaultCliId as jest.Mock;

const mockPtyProcess = {
  pid: 1234,
  onData: jest.fn(),
  onExit: jest.fn(),
  kill: jest.fn(),
};

jest.mock("@/app/api/cli/pty-setup", () => ({
  pty: {
    spawn: jest.fn(() => mockPtyProcess),
  },
}));

describe("POST /api/cli/exec", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockResolveDefaultCliId.mockReturnValue("claude");
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("returns 400 when prompt is missing", async () => {
    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({}),
      }) as never,
    );

    const data = await response.json();

    expect(response.status).toBe(400);
    expect(data.error).toMatch(/prompt/i);
  });

  it("spawns the default print-mode CLI and returns an exec id", async () => {
    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({ prompt: "Say hi" }),
      }) as never,
    );

    const data = await response.json();

    expect(response.status).toBe(200);
    expect(typeof data.execId).toBe("string");
    expect(data.execId.length).toBeGreaterThan(0);
    expect(pty.spawn).toHaveBeenCalledWith(
      "/resolved/claude",
      ["-p", "--output-format", "stream-json", "--verbose", "Say hi"],
      {
        name: "xterm-256color",
        cols: 200,
        rows: 50,
        cwd: "/augur/root",
        env: { PATH: "/mock/path", COLORFGBG: "15;0" },
      },
    );

    expect(execStore.get(data.execId)).toMatchObject({
      answer: null,
      sessionId: null,
      error: null,
    });
  });

  it("normalizes Claude stream-json print commands for noninteractive execution", async () => {
    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({ prompt: "Say hi" }),
      }) as never,
    );

    expect(response.status).toBe(200);
    expect(pty.spawn).toHaveBeenCalledWith(
      "/resolved/claude",
      expect.arrayContaining(["--output-format", "stream-json", "--verbose"]),
      expect.objectContaining({ cwd: "/augur/root" }),
    );
  });

  it("ignores request cliId and always spawns the configured default CLI", async () => {
    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({ prompt: "Say hi", cliId: "codex" }),
      }) as never,
    );

    const data = await response.json();

    expect(response.status).toBe(200);
    expect(typeof data.execId).toBe("string");
    expect(pty.spawn).toHaveBeenCalledWith(
      "/resolved/claude",
      ["-p", "--output-format", "stream-json", "--verbose", "Say hi"],
      expect.objectContaining({ cwd: "/augur/root" }),
    );
  });

  it("uses the shared default CLI resolver for print-mode execution", async () => {
    mockResolveDefaultCliId.mockReturnValue("codex");

    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({ prompt: "Say hi" }),
      }) as never,
    );

    const data = await response.json();

    expect(response.status).toBe(200);
    expect(typeof data.execId).toBe("string");
    expect(pty.spawn).toHaveBeenCalledWith(
      "/resolved/codex",
      ["exec", "--json", "Say hi"],
      expect.objectContaining({ cwd: "/augur/root" }),
    );
  });

  it("cleans up print-mode executions when no stream ever attaches", async () => {
    jest.useFakeTimers();

    const response = await POST(
      new Request("http://localhost/api/cli/exec", {
        method: "POST",
        body: JSON.stringify({ prompt: "Never streamed" }),
      }) as never,
    );

    const data = await response.json();
    expect(response.status).toBe(200);
    expect(execStore.get(data.execId)).toBeDefined();

    jest.advanceTimersByTime(EXEC_ORPHAN_CLEANUP_MS);

    expect(mockPtyProcess.kill).toHaveBeenCalledTimes(1);
    expect(execStore.get(data.execId)).toBeUndefined();
  });
});
