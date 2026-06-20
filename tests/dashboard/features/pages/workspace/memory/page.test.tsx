/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import MemoryPage from "@/features/pages/workspace/memory/page";

const mockRefreshStats = jest.fn();
const mockRefreshAll = jest.fn();
const mockRefreshWorkspace = jest.fn();
const mockOpenWorkspaceFile = jest.fn();
const mockHandleSearch = jest.fn();
const mockOpenSearchResult = jest.fn();
const mockMcpCall = jest.fn();

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("@/features/pages/workspace/memory/hooks", () => ({
  useMemoryDashboardData: () => ({
    stats: {
      totalDecisions: 42,
      totalPatterns: 9,
      totalPreferences: 7,
      dailyLogs: 12,
      lastCurated: "2026-04-23T10:00:00.000Z",
      recentDecisions: [],
      categoryCounts: { architecture: 4 },
    },
    categories: [],
    sources: {
      memory: {
        exists: true,
        label: "Augur Vault",
        freshness: "stale",
        modifiedAt: "2026-04-23T10:00:00.000Z",
      },
    },
    error: null,
    isStatsLoading: false,
    isWorkspaceLoading: false,
    workspace: {
      rootPath: '/tmp/memory',
      files: [],
    },
    notice: null,
    refreshStats: mockRefreshStats,
    refreshAll: mockRefreshAll,
    refreshWorkspace: mockRefreshWorkspace,
    openWorkspaceFile: mockOpenWorkspaceFile,
  }),
  useMemorySearch: () => ({
    searchQuery: "",
    setSearchQuery: jest.fn(),
    isSearching: false,
    searchResults: [],
    hasSearched: false,
    searchError: null,
    handleSearch: mockHandleSearch,
    openSearchResult: mockOpenSearchResult,
    openingResultPath: null,
    openResultError: null,
  }),
  useWikiMaintenanceData: () => ({
    summary: null,
    candidates: [],
    totalCandidates: 0,
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

jest.mock("@/features/pages/workspace/memory/components/MemorySearchWidget", () => ({
  MemorySearchWidget: () => <div>Memory Search</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/MemoryStatsGrid", () => ({
  MemoryStatsGrid: () => <div>Memory Stats</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/RecentDecisions", () => ({
  RecentDecisions: () => <div>Recent Decisions</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/DecisionCategories", () => ({
  DecisionCategories: () => <div>Decision Categories</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/MemoryInsights", () => ({
  MemoryInsights: () => <div>Memory Insights</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/WikiMaintenancePanel", () => ({
  WikiMaintenancePanel: () => <div>Wiki Maintenance</div>,
}));

jest.mock("@/features/pages/workspace/memory/components/MemoryWorkspacePanel", () => ({
  MemoryWorkspacePanel: () => <div>Memory Workspace</div>,
}));

describe("MemoryPage", () => {
  beforeEach(() => {
    mockRefreshStats.mockReset();
    mockRefreshAll.mockReset();
    mockRefreshWorkspace.mockReset();
    mockOpenWorkspaceFile.mockReset();
    mockHandleSearch.mockReset();
    mockOpenSearchResult.mockReset();
    mockMcpCall.mockReset().mockResolvedValue({ success: true });
  });

  it("keeps memory-specific workbench surfaces on the memory tab", async () => {
    render(<MemoryPage />);

    expect(screen.getByText("Session Memory")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Curate Memory/i })).toBeInTheDocument();
    expect(screen.getByText("Memory Search")).toBeInTheDocument();
    expect(screen.getByText("Memory Stats")).toBeInTheDocument();
    expect(screen.getByText("Recent Decisions")).toBeInTheDocument();
    expect(screen.getByText("Decision Categories")).toBeInTheDocument();
    expect(screen.getByText("Memory Insights")).toBeInTheDocument();
    expect(screen.getByText("Wiki Maintenance")).toBeInTheDocument();
    expect(screen.queryByText("Memory Workspace")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Browse memory files/i })).toHaveAttribute(
      "href",
      "/browse?view=documents",
    );
    expect(screen.queryByText("Open profile")).not.toBeInTheDocument();
    expect(screen.queryByText("Open daily logs")).not.toBeInTheDocument();
  });

  it("curates memory from the dedicated memory workbench", async () => {
    render(<MemoryPage />);

    fireEvent.click(screen.getByRole("button", { name: /Curate Memory/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("memory-curate", {
      days_back: 7,
      archive_processed: false,
    });
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("Memory curated");
    });
  });

  it("summarizes attention, freshness, next actions, and health as a command center", () => {
    render(<MemoryPage />);

    expect(screen.getByText("Command center")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText(/Memory source is marked stale/i)).toBeInTheDocument();
    expect(screen.getByText("Next best actions")).toBeInTheDocument();
    expect(screen.getByText(/Curate the latest seven days/i)).toBeInTheDocument();
    expect(screen.getByText("Memory health")).toBeInTheDocument();
    expect(screen.getByText(/58 curated signals/i)).toBeInTheDocument();
  });
});
