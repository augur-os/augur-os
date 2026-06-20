import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseMcpQuery = jest.fn();
const mockMcpCall = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

import McpControlPanel from "@/app/settings/tabs/McpControlPanel";

describe("McpControlPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseMcpQuery.mockReturnValue({
      data: {
        dataDir: "/tmp/augur",
        clients: {
          codex: {
            configPath: "/Users/test/.codex/config.toml",
            exists: true,
            servers: [{ name: "augur", status: "ok" }],
          },
          antigravity: {
            configPath: "/Users/test/.gemini/antigravity/mcp_config.json",
            exists: true,
            servers: [{ name: "augur", status: "ok" }],
          },
        },
        runtime: {
          transport: { transport: "stdio", host: "127.0.0.1", port: 0 },
          processMatches: [],
          portOpen: false,
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    mockMcpCall.mockResolvedValue({ success: true });
  });

  it("renders a runtime reveal button for supported clients", () => {
    render(<McpControlPanel />);

    expect(
      screen.getByLabelText("Reveal Codex runtime folder"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Reveal Antigravity runtime folder"),
    ).toBeInTheDocument();
  });

  it("opens the runtime folder through the dedicated MCP tool", async () => {
    render(<McpControlPanel />);

    fireEvent.click(screen.getByLabelText("Reveal Codex runtime folder"));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith("open-client-runtime-folder", {
        clientId: "codex",
      });
    });
  });

  it("still opens the config target separately", async () => {
    render(<McpControlPanel />);

    fireEvent.click(screen.getByLabelText("Open Codex config file"));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith("system-open", {
        path: "/Users/test/.codex/config.toml",
      });
    });
  });
});
