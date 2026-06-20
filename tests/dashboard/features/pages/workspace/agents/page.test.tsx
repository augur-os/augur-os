/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockUseMcpQuery = jest.fn();
const mockUseMcpPoll = jest.fn();
const mockMcpCall = jest.fn();
const mockPush = jest.fn();
const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();

const registryData = { total: 0, agents: [] };
const syncStatusData = { success: true, clients: {} };
const defaultCliData = { default_cli: "" };
const remoteProvidersData = { providers: [] };
const localBackendData = {};

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/lib/mcp/useMcpPoll", () => ({
  useMcpPoll: (...args: unknown[]) => mockUseMcpPoll(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

jest.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

describe("AgentsPage", () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
    mockUseMcpPoll.mockReset();
    mockMcpCall.mockReset();
    mockPush.mockReset();
    mockToastSuccess.mockReset();
    mockToastError.mockReset();

    mockUseMcpPoll.mockImplementation((queryKey: unknown[], tool: string) => {
      if (tool === "agent-registry") {
        return { data: registryData, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "get-sync-status") {
        return { data: syncStatusData, loading: false, error: null, refetch: jest.fn() };
      }
      return { data: undefined, loading: false, error: null, refetch: jest.fn() };
    });

    mockUseMcpQuery.mockImplementation((queryKey: unknown[], tool: string) => {
      if (tool === "get-preferences") {
        return {
          data: defaultCliData,
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "get-settings") {
        return { data: remoteProvidersData, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "get-local-backend-status") {
        return { data: localBackendData, loading: false, error: null, refetch: jest.fn() };
      }
      return { data: undefined, loading: false, error: null, refetch: jest.fn() };
    });
  });

  it("keeps the modal open and reports a routing preference failure", async () => {
    mockMcpCall
      .mockResolvedValueOnce({ success: true })
      .mockResolvedValueOnce({ client_routing: { default_client: "" } })
      .mockResolvedValueOnce({ success: false, error: "routing update failed" });

    const Page = (await import("@/features/pages/workspace/agents/page")).default;
    const user = userEvent.setup();

    render(<Page />);

    await user.click(screen.getByRole("button", { name: "Configure First Agent" }));
    await user.selectOptions(screen.getByLabelText("Client"), "codex");
    await user.type(screen.getByLabelText("Command"), "codex --approval-mode never");
    await user.type(screen.getByLabelText("Default model hint"), "gpt-5");
    await user.click(screen.getByRole("button", { name: "Save Agent" }));

    await waitFor(() => {
      expect(screen.getByText("routing update failed")).toBeInTheDocument();
    });
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Save Agent" })).toBeInTheDocument();
  });

  it("summarizes client readiness, provider readiness, test action, and the first fix in plain outcomes", async () => {
    const issueRegistryData = {
      total: 1,
      agents: [{ id: "codex", source: "project", role: "executor" }],
    };
    const issueSyncData = {
      success: true,
      clients: {
        codex: {
          status: "issues",
          issues: ["Generated command wrappers are stale"],
          synced_skills: ["ai"],
        },
      },
    };
    const issueProviderData = {
      providers: [
        { id: "openai", name: "OpenAI", enabled: true, defaultModel: "gpt-5" },
      ],
    };
    const issueDefaultCliData = { default_cli: "codex" };
    const issueLocalBackendData = {};
    mockUseMcpPoll.mockImplementation((queryKey: unknown[], tool: string) => {
      if (tool === "agent-registry") {
        return {
          data: issueRegistryData,
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "get-sync-status") {
        return {
          data: issueSyncData,
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return { data: undefined, loading: false, error: null, refetch: jest.fn() };
    });
    mockUseMcpQuery.mockImplementation((queryKey: unknown[], tool: string) => {
      if (tool === "get-preferences") {
        return { data: issueDefaultCliData, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "get-settings") {
        return {
          data: issueProviderData,
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "get-local-backend-status") {
        return { data: issueLocalBackendData, loading: false, error: null, refetch: jest.fn() };
      }
      return { data: undefined, loading: false, error: null, refetch: jest.fn() };
    });
    const Page = (await import("@/features/pages/workspace/agents/page")).default;

    render(<Page />);

    expect(screen.getByText("Client readiness")).toBeInTheDocument();
    expect(screen.getByText("Provider readiness")).toBeInTheDocument();
    expect(screen.getByText("Test now")).toBeInTheDocument();
    expect(screen.getByText("Fix this")).toBeInTheDocument();
    expect(screen.getByText("0/1 local routes ready")).toBeInTheDocument();
    expect(screen.getByText("0/1 providers ready")).toBeInTheDocument();
    expect(screen.getByText("Set API keys for enabled providers to unlock API execution.")).toBeInTheDocument();
    expect(screen.getByText("Generated command wrappers are stale")).toBeInTheDocument();
  });
});
