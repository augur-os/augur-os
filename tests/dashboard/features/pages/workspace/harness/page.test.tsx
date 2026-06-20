/**
 * @jest-environment jsdom
 */
import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockUseMcpQuery = jest.fn();
const mockMcpCall = jest.fn();
const mockRunAction = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
  }),
}));

const readyPayload = {
  success: true,
  state: "ready",
  snapshot: {
    generated_at: "2026-04-19T10:00:00Z",
    capabilities: [
      {
        id: "skill:knowledge",
        type: "skill",
        label: "knowledge",
        hub: "workspace",
        owner_skill: "knowledge",
        source_path: "project-brain/capabilities/skills/knowledge/SKILL.md",
        summary: "Search and curate Augur memory.",
        tags: [],
        status: "mapped",
      },
      {
        id: "mcp_tool:memory-search",
        type: "mcp_tool",
        label: "memory-search",
        hub: "workspace",
        owner_skill: "knowledge",
        source_path: "project-brain/capabilities/skills/knowledge/scripts/mcp.py",
        summary: "Search memory sources.",
        tags: [],
        status: "mapped",
      },
      {
        id: "dashboard_page:workspace-memory",
        type: "dashboard_page",
        label: "Memory page",
        hub: "workspace",
        owner_skill: "knowledge",
        source_path: "apps/dashboard/features/pages/workspace/memory/page.tsx",
        summary: "Memory dashboard page.",
        tags: [],
        status: "mapped",
      },
    ],
    relationships: [],
    diagnostics: [
      {
        id: "diagnostic:missing-mcp-tool:missing-tool",
        severity: "warning",
        family: "dashboard_mcp_wiring",
        reason: "Skill declares MCP tool 'missing-tool' but no @mcp.tool registration was found.",
        affected_capability_ids: ["mcp_tool:missing-tool"],
        source_path: "project-brain/capabilities/skills/ai/SKILL.md",
        recommended_action: {
          kind: "dispatch_ide_repair",
          label: "Ask IDE agent to repair missing MCP tool wiring",
        },
      },
    ],
    actions: [],
    provenance: {
      source_counts: { skills: 1, mcp_tool_registrations: 0 },
      partial_failures: [],
    },
  },
  actions: [
    { kind: "refresh_snapshot", label: "Refresh snapshot", direct: true },
    { kind: "dispatch_ide_repair", label: "Ask IDE agent to repair", direct: false },
  ],
};

const managerPayload = {
  success: true,
  generated_at: "2026-05-25T18:00:00Z",
  tiers: ["global", "personal", "project"],
  tier_details: [
    { key: "global", label: "Global", brain_id: "augur-core", root: "/tmp/core", writable: false },
    { key: "personal", label: "User", brain_id: "personal", root: "/tmp/vault", writable: true },
    { key: "project", label: "Project", brain_id: "project-repo", root: "/tmp/repo/project-brain", writable: true },
  ],
  groups: {
    skills: {
      label: "Skills",
      effective: 2,
      shadowed: ["shared"],
      entries: [
        {
          id: "skills:shared",
          capability_type: "skills",
          name: "shared",
          owner: "augur",
          owner_label: "Augur-managed",
          winner_tier: "project",
          winner_tier_label: "Project",
          winner_brain_id: "project-repo",
          winner_path: "/tmp/repo/project-brain/capabilities/skills/shared",
          tiers: [
            { tier: "global", tier_label: "Global", brain_id: "augur-core", path: "/tmp/core/capabilities/skills/shared", status: "shadowed", owner: "augur" },
            { tier: "project", tier_label: "Project", brain_id: "project-repo", path: "/tmp/repo/project-brain/capabilities/skills/shared", status: "effective", owner: "augur" },
          ],
          shadowed: ["global"],
          shadowed_entries: [
            { tier: "global", tier_label: "Global", brain_id: "augur-core", path: "/tmp/core/capabilities/skills/shared" },
          ],
          actions: {
            promote: { enabled: false, tool: "harness-promote-capability", reason: "Already Augur-managed" },
            demote: { enabled: true, tool: "harness-demote-capability", reason: null },
          },
        },
        {
          id: "skills:core-only",
          capability_type: "skills",
          name: "core-only",
          owner: "augur",
          owner_label: "Augur-managed",
          winner_tier: "global",
          winner_tier_label: "Global",
          winner_brain_id: "augur-core",
          winner_path: "/tmp/core/capabilities/skills/core-only",
          tiers: [
            { tier: "global", tier_label: "Global", brain_id: "augur-core", path: "/tmp/core/capabilities/skills/core-only", status: "effective", owner: "augur" },
          ],
          shadowed: [],
          shadowed_entries: [],
          actions: {
            promote: { enabled: false, tool: "harness-promote-capability", reason: "Already Augur-managed" },
            demote: { enabled: false, tool: "harness-demote-capability", reason: "Global tier is read-only" },
          },
        },
      ],
    },
  },
};

function payloadWithCapabilities(total: number) {
  return {
    ...readyPayload,
    snapshot: {
      ...readyPayload.snapshot,
      capabilities: Array.from({ length: total }, (_, index) => ({
        id: `mcp_tool:capability-${index}`,
        type: "mcp_tool",
        label: `Capability ${index}`,
        hub: "workspace",
        owner_skill: "knowledge",
        source_path: `project-brain/capabilities/skills/knowledge/scripts/capability-${index}.py`,
        summary: `Capability ${index} summary.`,
        tags: [],
        status: "mapped",
      })),
      diagnostics: [],
    },
  };
}

describe("BrainHarnessPage", () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
    mockMcpCall.mockReset();
    mockRunAction.mockReset();
  });

  it("renders readiness, capabilities, diagnostics, and provenance", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: readyPayload,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;

    render(<Page />);

    expect(screen.getByText("Harness readiness")).toBeInTheDocument();
    expect(screen.getByText("Developer diagnostic")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Harness readiness", level: 1 })).not.toBeInTheDocument();
    expect(screen.getByText("3 mapped")).toBeInTheDocument();
    expect(screen.getByText("knowledge")).toBeInTheDocument();
    expect(screen.getAllByText(/missing-tool/).length).toBeGreaterThan(0);
    expect(screen.getByText("project-brain/capabilities/skills/knowledge/SKILL.md")).toBeInTheDocument();
    expect(screen.getByText("Blockers")).toBeInTheDocument();
    expect(screen.getByText("1 warning needs review")).toBeInTheDocument();
    expect(screen.getByText("Affected capabilities")).toBeInTheDocument();
    expect(screen.getByText("missing-tool")).toBeInTheDocument();
    expect(screen.getByText("Repair action")).toBeInTheDocument();
    expect(screen.getByText("Ask IDE agent to repair missing MCP tool wiring")).toBeInTheDocument();
  });

  it("provides capability search and type filters before the capability list", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: readyPayload,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);

    expect(screen.getByLabelText("Search capabilities")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Filter capabilities by type mcp_tool" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Filter capabilities by type mcp_tool" }));

    expect(screen.getByText("memory-search")).toBeInTheDocument();
    expect(screen.queryByText("Memory page")).not.toBeInTheDocument();
  });

  it("renders the tiered harness manager with effective and shadowed rows", async () => {
    mockUseMcpQuery.mockImplementation((_key, tool) => ({
      data: tool === "harness-manager-snapshot" ? managerPayload : readyPayload,
      loading: false,
      error: null,
      refetch: jest.fn(),
    }));
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);

    expect(screen.getByText("Harness manager")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show effective capabilities" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Filter manager by Global tier" })).toBeInTheDocument();
    expect(screen.getByText("shared")).toBeInTheDocument();
    expect(screen.getAllByText("Project").length).toBeGreaterThan(0);
    expect(screen.getByText("Shadowed by Global")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Demote shared to Codex" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Filter manager by Global tier" }));

    expect(screen.getByText("core-only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Demote core-only to Codex" })).toBeDisabled();
  });

  it("keeps the unfiltered capability map bounded until the user narrows it", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: payloadWithCapabilities(35),
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;

    render(<Page />);

    expect(screen.getByText("24 of 35 capabilities shown")).toBeInTheDocument();
    expect(screen.getByText("Capability 0")).toBeInTheDocument();
    expect(screen.queryByText("Capability 34")).not.toBeInTheDocument();
    expect(screen.getByText("Use search or a type filter to inspect the remaining 11 capabilities.")).toBeInTheDocument();
  });

  it("shows generate action when no snapshot exists", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        success: true,
        state: "missing",
        snapshot: null,
        actions: [{ kind: "refresh_snapshot", label: "Refresh snapshot", direct: true }],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;

    render(<Page />);

    expect(screen.getByText("Harness snapshot has not been generated yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate snapshot" })).toBeInTheDocument();
  });

  it("refreshes snapshot through MCP instead of an IDE action", async () => {
    const refetch = jest.fn();
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch });
    mockMcpCall.mockResolvedValue({ success: true });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Refresh snapshot" }));

    await waitFor(() => expect(mockMcpCall).toHaveBeenCalledWith("refresh-brain-harness-snapshot", {}));
    expect(mockRunAction).not.toHaveBeenCalled();
    expect(refetch).toHaveBeenCalled();
  });

  it("disables refresh actions while a snapshot refresh is in progress", async () => {
    const refetch = jest.fn();
    let resolveRefresh: (() => void) | null = null;
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch });
    mockMcpCall.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    const refreshButton = screen.getByRole("button", { name: "Refresh snapshot" });
    const repairButton = screen.getByRole("button", { name: "Ask IDE agent to repair" });

    await user.click(refreshButton);

    await waitFor(() => expect(refreshButton).toBeDisabled());
    await waitFor(() => expect(repairButton).toBeDisabled());

    resolveRefresh?.();
    await waitFor(() => expect(refreshButton).not.toBeDisabled());
    await waitFor(() => expect(repairButton).not.toBeDisabled());
    expect(refetch).toHaveBeenCalled();
  });

  it("shows refresh failure and recovers controls after MCP error", async () => {
    const refetch = jest.fn();
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch });
    mockMcpCall.mockRejectedValue(new Error("snapshot service unavailable"));
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    const refreshButton = screen.getByRole("button", { name: "Refresh snapshot" });
    await user.click(refreshButton);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("snapshot service unavailable"),
    );
    await waitFor(() => expect(refreshButton).not.toBeDisabled());
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to refresh harness snapshot");
  });

  it("dispatches repair work through IDE action runner", async () => {
    mockUseMcpQuery.mockReturnValue({ data: readyPayload, loading: false, error: null, refetch: jest.fn() });
    const Page = (await import("@/features/pages/workspace/harness/page")).default;
    const user = userEvent.setup();

    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Ask IDE agent to repair" }));

    expect(mockRunAction).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "brain-harness-repair",
        dispatch: "ide",
        page: "/workspace/harness",
      }),
    );
  });
});
