/**
 * @jest-environment jsdom
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { renderWithQuery as render } from "../helpers/component-test-utils";

const mockPush = jest.fn();

function createMockBrowseState(overrides: Record<string, unknown> = {}) {
  return {
    ...baseBrowseState,
    ...overrides,
  };
}

const baseBrowseState = {
  containerRef: { current: null },
  selectedSkill: null,
  selectedSchedule: null,
  splitPercent: 60,
  lastIndexed: null,
  activeCategory: { id: "skills", label: "Skills" },
  effectiveViewMode: "skills",
  activeFolderContext: { scope: "all", label: "All Brains" },
  folderContextOptions: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
  folderContextLoading: false,
  setActiveFolderContext: jest.fn(),
  scanFolderForContext: jest.fn(),
  truncated: false,
  totalCount: 0,
  sorted: [],
  visibleCategories: [{ id: "skills", label: "Skills", group: "core" }],
  categoryFreshness: {},
  changeView: jest.fn(),
  displayMode: "card",
  setDisplayMode: jest.fn(),
  refetch: jest.fn(),
  search: "",
  setSearch: jest.fn(),
  semanticResultsActive: false,
  semanticDisplayResults: [],
  setSemanticResults: jest.fn(),
  setSemanticMode: jest.fn(),
  setSemanticSearched: jest.fn(),
  handleSemanticSearch: jest.fn(),
  semanticLoading: false,
  semanticResults: [],
  semanticSearched: false,
  semanticError: null,
  tagFilter: null,
  setTagFilter: jest.fn(),
  tagItems: [],
  hubFilter: null,
  setHubFilter: jest.fn(),
  hubItems: [],
  sourceFilter: null,
  setSourceFilter: jest.fn(),
  kindFilter: "all",
  setKindFilter: jest.fn(),
  masterFilter: null,
  setMasterFilter: jest.fn(),
  masterClients: [],
  pluginFilter: null,
  setPluginFilter: jest.fn(),
  pluginNames: [],
  typeFilter: null,
  setTypeFilter: jest.fn(),
  typeItems: [],
  skillTagFilter: null,
  setSkillTagFilter: jest.fn(),
  skillTagItems: [],
  sortBy: "default",
  setSortBy: jest.fn(),
  filtered: [],
  sweepFilteredItems: [],
  sweepFilterSummary: {
    search: "",
    scope: "all",
    hub: "all",
    tag: "all",
    kind: "all",
    source: "all",
    viewMode: "skills",
  },
  pinnedItems: [],
  loading: false,
  error: null,
  notIndexed: false,
  visibleCount: 20,
  setVisibleCount: jest.fn(),
  pageSize: 20,
  handleRunMcp: jest.fn(),
  selectSkill: jest.fn(),
  detailLoading: false,
  skillDetail: null,
  scheduledExecutionDetail: null,
  scheduledExecutionDetailLoading: false,
  closeDetail: jest.fn(),
  handleDragStart: jest.fn(),
  handleKeyboardResize: jest.fn(),
  selectScheduledExecution: jest.fn(),
};

let mockBrowseState = createMockBrowseState();
const mockRunAction = jest.fn();

jest.mock("@/app/(views)/browse/useBrowseState", () => ({
  useBrowseState: () => mockBrowseState,
}));

jest.mock("@/lib/browse/useSkillCoverage", () => ({
  useSkillCoverage: () => ({
    index: { generatedAt: null, bySkill: new Map(), byTool: new Map() },
    loading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock("@/components/shared/BrowseCategoryNav", () => ({
  BrowseCategoryNav: ({ categories, onSelect, renderTrailing }: { categories: Array<{ id: string; label: string }>; onSelect?: (id: string) => void; renderTrailing?: (category: { id: string; label: string }) => React.ReactNode }) => (
    <div>{categories.map((category) => (
      <button key={category.id} type="button" onClick={() => onSelect?.(category.id)}>
        {category.label}
        {renderTrailing?.(category)}
      </button>
    ))}</div>
  ),
}));

jest.mock("@/components/shared/BrowseCategoryActions", () => ({
  ApiRoutesStats: () => <div>API stats</div>,
  BrowseCategoryActions: ({ onReindex }: { onReindex?: () => void }) => (
    <button type="button" onClick={onReindex}>
      Actions
    </button>
  ),
  useBrowseCategoryActions: ({ onReindex }: { onReindex?: () => void }) => ({
    items: onReindex
      ? [{ id: "reindex", label: "Reindex", onSelect: onReindex }]
      : [],
    // Surface the reindex affordance as a clickable control so layout tests can
    // drive the same dispatch the real overflow menu item triggers.
    modal: onReindex ? (
      <button type="button" onClick={onReindex}>
        Actions
      </button>
    ) : null,
  }),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
  }),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/components/shared/BrowseDetailPanel", () => ({
  BrowseDetailPanel: () => <div>Detail panel</div>,
}));

jest.mock("@/app/(views)/browse/BrowseToolbar", () => ({
  BrowseToolbar: ({
    displayMode,
    onDisplayModeChange,
    onDeepSearch,
    deepSearchDisabled,
    semanticError,
  }: {
    displayMode: string;
    onDisplayModeChange: (mode: "card" | "list") => void;
    onDeepSearch?: () => void;
    deepSearchDisabled?: boolean;
    semanticError?: string | null;
  }) => (
    <div>
      Toolbar
      <button
        type="button"
        aria-label="List mode"
        aria-pressed={displayMode === "list"}
        onClick={() => onDisplayModeChange("list")}
      >
        List mode
      </button>
      <button type="button" aria-label="Ask AI" disabled={deepSearchDisabled} onClick={onDeepSearch}>
        Ask AI
      </button>
      <div data-testid="toolbar-semantic-error">{semanticError ?? ""}</div>
    </div>
  ),
}));

jest.mock("@/app/(views)/browse/BrowseContentGrid", () => ({
  BrowseContentGrid: () => <div>Content grid</div>,
}));

jest.mock("@/features/browse/NoteDropZone", () => ({
  NoteDropZone: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="note-drop-zone">{children}</div>
  ),
}));

jest.mock("@/features/browse/NoteFAB", () => ({
  NoteFAB: () => <button type="button">Note FAB</button>,
}));

jest.mock("@/features/browse/NoteModal", () => ({
  NoteModal: () => <div data-testid="note-modal">Note Modal</div>,
}));

describe("Browse page layout", () => {
  beforeEach(() => {
    localStorage.clear();
    mockBrowseState = createMockBrowseState();
    mockRunAction.mockReset();
    mockRunAction.mockResolvedValue(true);
    mockPush.mockReset();
  });

  it("does not render any first-run welcome banner above the category grid (ADR-760)", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    // The WelcomeBanner was removed by ADR-760; Brain and Settings remain
    // 1-click reachable from the sidebar, so the banner is no longer needed.
    expect(screen.queryByText("Start Here")).not.toBeInTheDocument();
    expect(screen.queryByText("Welcome to Augur")).not.toBeInTheDocument();
    expect(screen.queryByTestId("browse-welcome-banner")).not.toBeInTheDocument();
  });

  it("does not create an extra left-pane scroll container", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    const { container } = render(<BrowsePageClient />);

    expect(screen.getByRole("heading", { name: "Browse · Skills" })).toBeInTheDocument();

    const rootSplitLayout = container.querySelector("div.mt-6.flex.min-h-0.items-start");
    expect(rootSplitLayout).toHaveClass("overflow-x-clip");
    expect(rootSplitLayout).not.toHaveClass("overflow-hidden");
    expect(rootSplitLayout?.className).not.toContain("h-[calc(");

    const leftScrollPane = container.querySelector(
      "div.overflow-y-auto.overflow-x-hidden.shrink-0",
    );
    expect(leftScrollPane).toBeNull();
  });

  it("surfaces a compact browse summary above the category rail", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    expect(screen.getByRole("heading", { name: "Browse · Skills" })).toBeInTheDocument();
    expect(screen.getByText("0 skills")).toBeInTheDocument();
    expect(screen.getByText("Explore capability packages across Augur.")).toBeInTheDocument();
  });

  it("keeps ingest affordances available for indexed Browse categories", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    expect(await screen.findByTestId("note-drop-zone")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Note FAB" })).toBeInTheDocument();
    expect(screen.getByTestId("note-modal")).toBeInTheDocument();
  });

  it("dispatches category reindex through the action runner", async () => {
    mockBrowseState = createMockBrowseState({
      effectiveViewMode: "wiki",
      activeCategory: { id: "wiki", label: "Wiki" },
      visibleCategories: [{ id: "wiki", label: "Wiki", group: "knowledge" }],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Actions" }));

    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "browse-reindex-wiki",
          label: "Reindex Wiki",
          dispatch: "ide",
          prompt: "/search reindex wiki",
        }),
      );
    });
  });

  it("dispatches mapped index categories for operation/development browse modes", async () => {
    mockBrowseState = createMockBrowseState({
      effectiveViewMode: "pages",
      activeCategory: { id: "pages", label: "Pages" },
      visibleCategories: [
        { id: "pages", label: "Pages", group: "content" },
      ],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Actions" }));

    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "browse-reindex-pages",
          label: "Reindex Pages",
          description: "Rebuild the Pages browse index.",
          prompt: "/search reindex pages",
        }),
      );
    });
  });

  it("dispatches Browse deep search through the generic action runner", async () => {
    const deckResults = [
      {
        id: "deck",
        title: "augur angel deck v20",
        description: "PPTX · venture-augur / IntelSubmit / inteliginite / augur-angel-deck-v20.pptx",
        hub: "venture-augur",
        icon: "FileText",
        typeBadge: "pptx",
        path: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
        tags: ["documents"],
        primaryAction: {
          label: "Open",
          type: "open-file",
          target: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
        },
        metadata: {
          source_path: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
        },
      },
    ];
    mockBrowseState = createMockBrowseState({
      search: "pitch slide I am working on",
      semanticResults: deckResults,
      semanticDisplayResults: deckResults,
      semanticSearched: true,
      semanticSearchActive: true,
      semanticResultsActive: true,
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(mockRunAction).toHaveBeenCalledWith(expect.objectContaining({
      id: "browse.deep-search",
      dispatch: "ide",
      tier: "deep",
      page: "browse",
    }));
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("pitch slide I am working on");
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("augur angel deck v20");
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("augur-angel-deck-v20.pptx");
  });

  it("includes no-result Browse context when Ask AI runs after an empty fast search", async () => {
    mockBrowseState = createMockBrowseState({
      search: "missing pitch artifact",
      semanticResults: [],
      semanticSearched: true,
      semanticSearchActive: true,
      semanticResultsActive: true,
      sorted: [],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(mockRunAction.mock.calls[0][0].prompt).toContain("Query: missing pitch artifact");
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("Fast local search already ran: yes");
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("No top results are available");
  });

  it("includes current retrieval errors in the Ask AI prompt", async () => {
    mockBrowseState = createMockBrowseState({
      search: "broken pitch lookup",
      semanticError: "Search backend unavailable",
      semanticResults: [],
      semanticSearched: true,
      semanticSearchActive: true,
      semanticResultsActive: false,
      sorted: [],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    const prompt = mockRunAction.mock.calls[0][0].prompt;
    expect(prompt).toContain("Query: broken pitch lookup");
    expect(prompt).toContain("Fast local search already ran: yes");
    expect(prompt).toContain("Retrieval error: Search backend unavailable");
    expect(prompt).toContain("No top results are available");
  });

  it("does not pass stale retrieval errors to the toolbar when scoped search is inactive", async () => {
    mockBrowseState = createMockBrowseState({
      search: "new filtered query",
      semanticError: "Old failed search",
      semanticSearched: true,
      semanticSearchActive: false,
      semanticResultsActive: false,
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    expect(screen.getByTestId("toolbar-semantic-error")).toBeEmptyDOMElement();
  });

  it("dispatches Ask AI while fast search is loading", async () => {
    mockBrowseState = createMockBrowseState({
      search: "pitch slide while loading",
      semanticLoading: true,
      semanticResults: [],
      semanticSearched: false,
      semanticSearchActive: false,
      semanticResultsActive: false,
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    expect(mockRunAction).toHaveBeenCalledWith(expect.objectContaining({
      id: "browse.deep-search",
      dispatch: "ide",
      tier: "deep",
      page: "browse",
    }));
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("Query: pitch slide while loading");
    expect(mockRunAction.mock.calls[0][0].prompt).toContain("Fast local search already ran: no");
  });

  it("does not include stale fast-search results when scoped search state is inactive", async () => {
    mockBrowseState = createMockBrowseState({
      search: "new filtered query",
      semanticResults: [
        {
          id: "stale-deck",
          title: "stale pitch deck",
          description: "Old result from a previous Browse scope",
          hub: "venture-augur",
          icon: "FileText",
          typeBadge: "pptx",
          path: "/tmp/stale-pitch-deck.pptx",
          tags: ["documents"],
          primaryAction: {
            label: "Open",
            type: "open-file",
            target: "/tmp/stale-pitch-deck.pptx",
          },
          metadata: {
            source_path: "/tmp/stale-pitch-deck.pptx",
          },
        },
      ],
      semanticSearched: true,
      semanticSearchActive: false,
      semanticResultsActive: false,
      sorted: [],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));

    const prompt = mockRunAction.mock.calls[0][0].prompt;
    expect(prompt).toContain("Query: new filtered query");
    expect(prompt).toContain("Fast local search already ran: no");
    expect(prompt).toContain("No top results are available");
    expect(prompt).not.toContain("stale pitch deck");
    expect(prompt).not.toContain("/tmp/stale-pitch-deck.pptx");
  });

});
