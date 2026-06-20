import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { extractIssues, useMcpHealth } from "@/hooks/useMcpHealth";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

const emptyRuntime = {
  candidate: null,
  transport: { transport: "stdio", host: "127.0.0.1", port: 0 },
  processMatches: [],
};

function report(overrides: Record<string, unknown>) {
  return {
    configPath: "",
    exists: false,
    servers: [],
    augurServers: [],
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function summaryWithIssue() {
  return {
    generatedAt: "2026-05-13T00:00:00Z",
    clients: {
      codex: report({
        exists: true,
        servers: [
          {
            name: "augur-core",
            command: "python",
            args: [],
            envKeys: [],
            status: "error",
            issues: ["bad python"],
          },
        ],
        augurServers: [
          {
            name: "augur-core",
            command: "python",
            args: [],
            envKeys: [],
            status: "error",
            issues: ["bad python"],
          },
        ],
      }),
    },
    runtime: emptyRuntime,
  };
}

describe("visible surface policy integration", () => {
  const originalEnv = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;

  beforeEach(() => {
    jest.clearAllMocks();
    (mcpCall as jest.Mock).mockResolvedValue(summaryWithIssue());
  });

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    } else {
      process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = originalEnv;
    }
  });

  it("uses runtime-only diagnostics by default", async () => {
    renderHook(() => useMcpHealth({ enablePolling: false, showToasts: false }), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(mcpCall).toHaveBeenCalledWith("get-mcp-diagnostics", {
        params: {
          include_processes: true,
          include_configs: false,
        },
      }),
    );
  });

  it("keeps full config diagnostics opt-in", async () => {
    renderHook(
      () =>
        useMcpHealth({
          enablePolling: false,
          includeConfigs: true,
          showToasts: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() =>
      expect(mcpCall).toHaveBeenCalledWith("get-mcp-diagnostics", {
        params: {
          include_processes: true,
          include_configs: true,
        },
      }),
    );
  });

  it("omits View and Fix Now toast actions when visible mutations are disabled", async () => {
    process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = "no_visible_mutation";

    renderHook(() => useMcpHealth({ enablePolling: false, showToasts: true }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(toast.error).toHaveBeenCalled());

    const toastOptions = (toast.error as jest.Mock).mock.calls[0][1];
    expect(toastOptions.action).toBeUndefined();
    expect(toastOptions.cancel).toBeUndefined();
  });
});

describe("extractIssues", () => {
  it("ignores optional clients that are missing or not configured", () => {
    const issues = extractIssues({
      generatedAt: "2026-05-04T00:00:00Z",
      clients: {
        claudeDesktop: report({ error: "Config file not found." }),
        claudeCode: report({
          exists: true,
          error: "Augur MCP not configured.",
        }),
      },
      runtime: emptyRuntime,
    });

    expect(issues).toEqual([]);
  });

  it("reports configured Augur server issues for the active client", () => {
    const issues = extractIssues({
      generatedAt: "2026-05-04T00:00:00Z",
      clients: {
        codex: report({
          exists: true,
          servers: [
            { name: "other", status: "error", issues: ["ignored"] },
            { name: "augur-core", status: "error", issues: ["bad python"] },
          ],
          augurServers: [
            { name: "augur-core", status: "error", issues: ["bad python"] },
          ],
        }),
      },
      runtime: emptyRuntime,
    });

    expect(issues).toEqual([
      { client: "Codex", server: "augur-core", problems: ["bad python"] },
    ]);
  });
});
