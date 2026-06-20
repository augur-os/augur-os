import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InsightsPage from "@/features/pages/workspace/insights/page";

const mockRefetch = jest.fn();
const mockUseMcpQuery = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

const mockMcpCall = jest.fn(async () => ({ success: true }));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

const mockClipboard = {
  writeText: jest.fn(() => Promise.resolve()),
};

function setInsightsQuery(overrides: Record<string, unknown> = {}) {
  mockUseMcpQuery.mockReturnValue({
    data: {
      success: true,
      latest_runs: [
        {
          id: "run_1",
          status: "success",
          started_at: "2026-04-24T10:00:00.000Z",
          files_seen: 3,
          files_moved: 2,
          files_indexed: 2,
          files_failed: 1,
          insights: [
            {
              title: "Health paperwork grouped",
              summary: "Two files support one claim.",
              sources: ["/vault/documents/health/claim.pdf"],
              next_actions: ["Review receipt"],
            },
          ],
        },
      ],
      wiki_status: {
        verdict: "structure_ok_compile_backlog",
        structure: { pages: 12, missing_links: ["x"], orphan_pages: [] },
        compiler: {
          sources_total: 10,
          sources_compiled_with_concepts: 6,
          sources_pending_or_changed: 4,
          current: false,
        },
        coverage: {
          concept_coverage_ratio: 0.6,
          top_uncovered_source_families: [{ family: "inbox", total: 5, uncovered: 2 }],
        },
        index: { indexed: true, wiki_rag_entries: 9 },
        batches: { batch_count: 2, needs_update: true },
        compounding_health: {
          concept_page_count: 7,
          average_sources_per_concept_page: 4.2,
          thin_page_count: 3,
          target_sources_per_page: "10-15",
        },
        actions: [
          {
            id: "prepare-incremental-batch",
            reason: "needs update",
            tool: "wiki-update",
            inputs: { limit: 20 },
          },
        ],
      },
      retained_ask_outcomes: [{ question: "What did I learn?", summary: "Keep reimbursements together." }],
      retained_ask_clusters: [],
      ask_outcomes: [{ question: "What did I learn?", summary: "Keep reimbursements together." }],
      ask_clusters: [],
      errors: [],
      ...overrides,
    },
    loading: false,
    error: null,
    refetch: mockRefetch,
  });
}

function setInsightsQueryState(overrides: Record<string, unknown> = {}) {
  mockUseMcpQuery.mockReturnValue({
    data: null,
    loading: false,
    error: null,
    refetch: mockRefetch,
    ...overrides,
  });
}

describe("Brain Insights page", () => {
  beforeEach(() => {
    mockMcpCall.mockClear();
    mockRefetch.mockClear();
    mockUseMcpQuery.mockReset();
    mockClipboard.writeText.mockClear();
    window.localStorage.clear();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: mockClipboard,
    });
    setInsightsQuery();
  });

  it("queries the committed brain-insights MCP tool", () => {
    render(<InsightsPage />);

    expect(mockUseMcpQuery).toHaveBeenCalledWith(["brain-insights"], "brain-insights", "live");
  });

  it("renders wiki status, insights, and next actions", () => {
    render(<InsightsPage />);

    expect(screen.getByText("Brain Insights")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Brain Insights" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Brain Insights" })).not.toBeInTheDocument();
    expect(screen.getByText("Health paperwork grouped")).toBeInTheDocument();
    expect(screen.getByText("Review receipt")).toBeInTheDocument();
    expect(screen.getByText("structure_ok_compile_backlog")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("/vault/documents/health/claim.pdf")).toBeInTheDocument();
    expect(screen.getByText("run_1")).toBeInTheDocument();
  });

  it("surfaces MCP success false as an alert", () => {
    setInsightsQuery({
      success: false,
      latest_runs: [],
      errors: ["ask sync data missing", "wiki status unavailable"],
    });

    render(<InsightsPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("ask sync data missing");
    expect(screen.getByRole("alert")).toHaveTextContent("wiki status unavailable");
  });

  it("does not show stale loading sections after the query has failed", () => {
    setInsightsQueryState({ loading: true, error: "Unknown tool: brain-insights" });

    const { container } = render(<InsightsPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("Unknown tool: brain-insights");
    expect(screen.queryByText(/Loading Brain insights/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Loading inbox runs/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Loading retained ask outcomes/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Loading ask clusters/i)).not.toBeInTheDocument();
    expect(container.querySelectorAll("main")).toHaveLength(0);
  });

  it("runs wiki-update from the prepared action without claiming compilation is complete", async () => {
    render(<InsightsPage />);

    await userEvent.click(screen.getByRole("button", { name: /prepare wiki update/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("wiki-update", { limit: 20 });
    expect(screen.queryByText(/compilation complete/i)).not.toBeInTheDocument();
  });

  it("turns a healthy empty wiki state into next useful actions", () => {
    setInsightsQuery({
      latest_runs: [],
      wiki_status: {
        verdict: "healthy",
        healthy: true,
        structure: { pages: 35, missing_links: [], orphan_pages: [] },
        compiler: {
          sources_total: 648,
          sources_compiled_with_concepts: 391,
          sources_pending_or_changed: 0,
          current: true,
        },
        coverage: {
          concept_coverage_ratio: 0.6,
          top_uncovered_source_families: [],
        },
        index: { indexed: true, wiki_rag_entries: 71 },
        batches: { batch_count: 0, needs_update: false },
        compounding_health: {
          concept_page_count: 35,
          average_sources_per_concept_page: 11.17,
          thin_page_count: 0,
          target_sources_per_page: "8-15",
        },
        actions: [],
      },
      retained_ask_outcomes: [],
      retained_ask_clusters: [],
      ask_outcomes: [],
      ask_clusters: [],
    });

    render(<InsightsPage />);

    expect(screen.getByText("Wiki is current")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open wiki browse/i })).toHaveAttribute("href", "/browse?category=wiki");
    expect(screen.getByRole("link", { name: /scan brain inbox/i })).toHaveAttribute("href", "/workspace/inbox");
  });

  it("deduplicates retained ask outcomes before rendering", () => {
    setInsightsQuery({
      retained_ask_outcomes: [
        { question: "What did I learn?", summary: "Keep reimbursements together." },
        { question: "What did I learn?", summary: "Keep reimbursements together." },
        { question: "What did I learn?", summary: "Route the follow-up through wiki maintenance." },
        { question: "Where should the wiki live?", summary: "Use the configured vault wiki path." },
      ],
      ask_outcomes: [],
    });

    render(<InsightsPage />);

    expect(screen.getAllByText("What did I learn?")).toHaveLength(1);
    expect(screen.getByText("Where should the wiki live?")).toBeInTheDocument();
  });

  it("keeps long retained ask outcomes collapsed until requested", async () => {
    const longSummary = `${"A long retained outcome sentence. ".repeat(16)}Final specific detail.`;
    setInsightsQuery({
      retained_ask_outcomes: [{ question: "What should stay compact?", summary: longSummary }],
      ask_outcomes: [],
    });

    render(<InsightsPage />);

    expect(screen.getByText(/A long retained outcome sentence/)).toBeInTheDocument();
    expect(screen.queryByText(/Final specific detail/)).not.toBeInTheDocument();

    const expandButton = screen.getByRole("button", { name: /show full outcome/i });
    expect(expandButton).toHaveClass("min-h-[44px]");
    await userEvent.click(expandButton);

    expect(screen.getByText(/Final specific detail/)).toBeInTheDocument();
  });

  it("ranks insights by impact and marks changes since the previous visit", async () => {
    window.localStorage.setItem("brain-insights:last-visit", "2026-04-23T09:00:00.000Z");
    setInsightsQuery({
      latest_runs: [
        {
          id: "older_run",
          status: "success",
          started_at: "2026-04-23T08:00:00.000Z",
          files_failed: 0,
          insights: [
            {
              title: "Low impact older note",
              summary: "Already reviewed.",
              impact_score: 0.1,
              created_at: "2026-04-23T08:00:00.000Z",
              sources: [],
              next_actions: [],
            },
          ],
        },
        {
          id: "new_run",
          status: "success",
          started_at: "2026-04-24T12:00:00.000Z",
          files_failed: 2,
          insights: [
            {
              title: "Critical reimbursement follow-up",
              summary: "Two new reimbursement files failed intake and need a focused review.",
              impact_score: 0.95,
              created_at: "2026-04-24T12:00:00.000Z",
              sources: ["/vault/inbox/reimbursement.pdf"],
              next_actions: ["Open the inbox run and resolve the failed files."],
            },
          ],
        },
      ],
    });

    render(<InsightsPage />);

    expect(await screen.findByText("1 change since last visit")).toBeInTheDocument();
    expect(screen.getByText("New since last visit")).toBeInTheDocument();
    expect(screen.getByText("High impact")).toBeInTheDocument();

    const critical = screen.getByText("Critical reimbursement follow-up");
    const older = screen.getByText("Low impact older note");
    expect(
      critical.compareDocumentPosition(older) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("offers real insight actions for expanding and copying without dead promote buttons", async () => {
    const longSummary = `${"The insight includes concrete reimbursement context. ".repeat(12)}Final source-backed action.`;
    setInsightsQuery({
      latest_runs: [
        {
          id: "run_2",
          status: "success",
          started_at: "2026-04-24T12:00:00.000Z",
          insights: [
            {
              title: "Copyable reimbursement insight",
              summary: longSummary,
              impact_score: 0.8,
              created_at: "2026-04-24T12:00:00.000Z",
              sources: ["/vault/inbox/reimbursement.pdf"],
              next_actions: ["Review receipt"],
            },
          ],
        },
      ],
    });

    render(<InsightsPage />);

    expect(screen.queryByText(/Final source-backed action/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /show full insight/i }));
    expect(screen.getByText(/Final source-backed action/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /copy insight summary/i }));
    expect(mockClipboard.writeText).toHaveBeenCalledWith(longSummary);
    expect(screen.queryByRole("button", { name: /promote/i })).not.toBeInTheDocument();
  });

  it("shows airplane/local agent counters from latest inbox run", () => {
    setInsightsQuery({
      latest_runs: [
        {
          id: "run_airplane",
          status: "partial_success",
          airplane_mode: true,
          cloud_calls: 0,
          local_agent_calls: 1,
          files_seen: 2,
          files_moved: 1,
          files_indexed: 1,
          files_needing_review: 1,
          insights: [],
        },
      ],
    });

    render(<InsightsPage />);

    expect(screen.getByText("run_airplane")).toBeInTheDocument();
    expect(screen.getByText(/Airplane mode/i)).toBeInTheDocument();
    expect(screen.getByText(/Cloud calls: 0/i)).toBeInTheDocument();
    expect(screen.getByText(/Local agent calls: 1/i)).toBeInTheDocument();
  });

  it("shows demo RAG proof from the wiki index status", () => {
    setInsightsQuery({
      wiki_status: {
        verdict: "healthy",
        healthy: true,
        structure: { pages: 35, missing_links: [], orphan_pages: [] },
        compiler: {
          sources_total: 648,
          sources_compiled_with_concepts: 391,
          sources_pending_or_changed: 0,
          current: true,
        },
        coverage: {
          concept_coverage_ratio: 0.6,
          top_uncovered_source_families: [],
        },
        index: {
          indexed: true,
          wiki_rag_entries: 9,
          demo_query: "investor demo meeting",
          demo_hit_count: 1,
          demo_ready: true,
          demo_hits: [{ file: "vault/sources/files/demo-meeting.md", content: "investor demo meeting" }],
        },
        batches: { batch_count: 0, needs_update: false },
        compounding_health: {
          concept_page_count: 35,
          average_sources_per_concept_page: 11.17,
          thin_page_count: 0,
          target_sources_per_page: "8-15",
        },
        actions: [],
      },
    });

    render(<InsightsPage />);

    expect(screen.getAllByText(/investor demo meeting/i)).toHaveLength(2);
    expect(screen.getByText(/demo-meeting\.md/i)).toBeInTheDocument();
    expect(screen.getByText(/1 hits/i)).toBeInTheDocument();
  });
});
