/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrainOverviewHome } from "@/features/pages/workspace/overview/BrainOverviewHome";

const mockUseMemoryDashboardData = jest.fn();
const mockUseWikiMaintenanceData = jest.fn();
const mockUseBrainInbox = jest.fn();
const mockUseBrainInsights = jest.fn();

jest.mock("@/features/pages/workspace/memory/hooks", () => ({
  useMemoryDashboardData: () => mockUseMemoryDashboardData(),
  useWikiMaintenanceData: () => mockUseWikiMaintenanceData(),
}));

jest.mock("@/features/pages/workspace/inbox/hooks", () => ({
  useBrainInbox: () => mockUseBrainInbox(),
}));

jest.mock("@/features/pages/workspace/insights/hooks", () => ({
  useBrainInsights: () => mockUseBrainInsights(),
}));

describe("BrainOverviewHome", () => {
  beforeEach(() => {
    mockUseMemoryDashboardData.mockReturnValue({
      stats: {
        totalDecisions: 42,
        totalPatterns: 9,
        totalPreferences: 7,
        dailyLogs: 12,
        lastCurated: "2026-04-20T10:00:00.000Z",
        recentDecisions: [],
        categoryCounts: { architecture: 4, workflow: 3 },
      },
      sources: {
        memory: {
          exists: true,
          label: "Augur Vault",
          modifiedAt: "2026-04-23T10:00:00.000Z",
        },
        profile: {
          exists: true,
          label: "Human API Profile",
          modifiedAt: "2026-04-15T10:00:00.000Z",
        },
        daily: {
          exists: true,
          label: "Daily Logs",
          modifiedAt: "2026-04-22T10:00:00.000Z",
        },
      },
      error: null,
      isStatsLoading: false,
      isWorkspaceLoading: false,
      refreshStats: jest.fn(),
    });
    mockUseWikiMaintenanceData.mockReturnValue({
      summary: {
        avgQualityScore: 0.82,
        rewriteCandidates: 2,
        avgOutgoingLinksPerPage: 3.5,
        isolatedPages: 1,
      },
      candidates: [],
      totalCandidates: 2,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    });
    mockUseBrainInbox.mockReturnValue({
      totals: { newFiles: 7, documents: 3, trash: 2, failed: 1 },
      folders: [
        {
          id: "downloads",
          name: "Downloads",
          path: "~/Downloads",
          enabled: true,
          counts: { new_files: 7, document_candidates: 3, trash_candidates: 2, failed: 1 },
        },
      ],
      loading: false,
      error: null,
    });
    mockUseBrainInsights.mockReturnValue({
      latestRuns: [
        {
          id: "run_1",
          status: "success",
          started_at: "2026-04-24T10:00:00.000Z",
          insights: [{ title: "Receipts are ready", summary: "Three receipts can be reviewed." }],
        },
      ],
      wikiStatus: {
        compiler: {
          sources_pending_or_changed: 4,
          current: false,
        },
      },
      wikiUpdateAction: {
        id: "prepare-incremental-batch",
        tool: "wiki-update",
      },
      loading: false,
      error: null,
      errors: [],
    });
  });

  afterEach(() => {
    mockUseMemoryDashboardData.mockReset();
    mockUseWikiMaintenanceData.mockReset();
    mockUseBrainInbox.mockReset();
    mockUseBrainInsights.mockReset();
  });

  it("renders the two-zone overview with Workspace Actions and Needs Attention", () => {
    render(<BrainOverviewHome />);

    // Component text updated from "Brain Actions" -> "Workspace Actions"
    expect(screen.getByText("Workspace Actions")).toBeInTheDocument();
    expect(screen.getByText("Needs Attention")).toBeInTheDocument();

    // Removed surfaces should no longer be present.
    expect(screen.queryByText("Brain Brief")).not.toBeInTheDocument();
    expect(screen.queryByText("Continue Working")).not.toBeInTheDocument();
    expect(screen.queryByText("Daily Cockpit")).not.toBeInTheDocument();
    expect(screen.queryByText("Memory Workbench")).not.toBeInTheDocument();
  });

  it("hides the Needs Attention zone when nothing needs attention", () => {
    const fresh = new Date().toISOString();
    mockUseMemoryDashboardData.mockReturnValue({
      stats: {
        totalDecisions: 42,
        totalPatterns: 9,
        totalPreferences: 7,
        dailyLogs: 12,
        lastCurated: fresh,
        recentDecisions: [],
        categoryCounts: {},
      },
      sources: {
        memory: { exists: true, label: "Augur Vault", modifiedAt: fresh },
        profile: { exists: true, label: "Human API Profile", modifiedAt: fresh },
        daily: { exists: true, label: "Daily Logs", modifiedAt: fresh },
      },
      error: null,
      isStatsLoading: false,
      isWorkspaceLoading: false,
      refreshStats: jest.fn(),
    });
    mockUseWikiMaintenanceData.mockReturnValue({
      summary: {
        avgQualityScore: 0.95,
        rewriteCandidates: 0,
        avgOutgoingLinksPerPage: 4,
        isolatedPages: 0,
      },
      candidates: [],
      totalCandidates: 0,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<BrainOverviewHome />);

    // Workspace Actions always renders; the attention zone renders only when
    // there is something wrong — no empty/reassurance card.
    expect(screen.getByText("Workspace Actions")).toBeInTheDocument();
    expect(screen.queryByText("Needs Attention")).not.toBeInTheDocument();
    expect(screen.queryByText("No immediate Brain blockers")).not.toBeInTheDocument();
  });

  it("renders the five brain action cards pointing at kept routes", () => {
    render(<BrainOverviewHome />);

    expect(screen.getByRole("heading", { name: "Memory" }).closest("a")).toHaveAttribute(
      "href",
      "/workspace/memory",
    );
    expect(screen.getByRole("heading", { name: "Review" }).closest("a")).toHaveAttribute(
      "href",
      "/workspace/memory-review",
    );
    expect(screen.getByRole("heading", { name: "Inbox" }).closest("a")).toHaveAttribute(
      "href",
      "/workspace/inbox",
    );
    expect(screen.getByRole("heading", { name: "Insights" }).closest("a")).toHaveAttribute(
      "href",
      "/workspace/insights",
    );
    expect(screen.getByRole("heading", { name: "Daily Logs" }).closest("a")).toHaveAttribute(
      "href",
      "/workspace/daily-logs",
    );

    // No card should point at the removed routes.
    const links = screen.getAllByRole("link");
    for (const link of links) {
      const href = link.getAttribute("href");
      expect(href).not.toBe("/workspace/search");
      expect(href).not.toBe("/workspace/workspace");
      expect(href).not.toBe("/workspace/wiki");
      expect(href).not.toBe("/workspace/search");
      expect(href).not.toBe("/workspace/wiki");
    }
  });

  it("surfaces live brain signals on the action cards", () => {
    render(<BrainOverviewHome />);

    // Memory card summarises decision count.
    expect(screen.getByText("42 decisions")).toBeInTheDocument();
    // Inbox card summarises new file count.
    expect(screen.getByText("7 new files")).toBeInTheDocument();
  });

  it("uses loading copy instead of fake zero counts while live signals are pending", () => {
    mockUseMemoryDashboardData.mockReturnValue({
      stats: null,
      sources: undefined,
      error: null,
      isStatsLoading: true,
      isWorkspaceLoading: true,
      refreshStats: jest.fn(),
    });
    mockUseBrainInbox.mockReturnValue({
      totals: undefined,
      folders: [],
      loading: true,
      error: null,
    });
    mockUseBrainInsights.mockReturnValue({
      latestRuns: [],
      wikiStatus: null,
      wikiUpdateAction: null,
      loading: true,
      error: null,
      errors: [],
    });

    render(<BrainOverviewHome />);

    // Component updated: "Loading live Brain signals" -> "Loading live workspace signals"
    expect(screen.getByText("Loading live workspace signals")).toBeInTheDocument();
    expect(screen.getByText("Loading memory")).toBeInTheDocument();
    expect(screen.getByText("Loading inbox")).toBeInTheDocument();
    expect(screen.getByText("Loading insights")).toBeInTheDocument();
    expect(screen.queryByText("0 decisions")).not.toBeInTheDocument();
    expect(screen.queryByText("0 new files")).not.toBeInTheDocument();
  });
});
