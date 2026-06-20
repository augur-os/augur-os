/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import type React from "react";

const mockRefetch = jest.fn();
const mockPush = jest.fn();
const mockMcpCall = jest.fn();
const mockRunCliExecPrompt = jest.fn();

const sweepFilteredItems = [
  {
    id: "note-alpha",
    title: "Alpha Note",
    description: "Sweepable note",
    hub: "workspace",
    type: "vault",
    path: "/Users/me/Au-vault/notes/alpha.md",
    primaryAction: { label: "Open", type: "open-file", target: "/Users/me/Au-vault/notes/alpha.md" },
    metadata: {
      journey_category: "notes",
      vault_scope: "private",
      format: "md",
      skill: "brain",
    },
  },
  {
    id: "note-missing-path",
    title: "Missing Path",
    description: "Unsupported note",
    hub: "workspace",
    type: "vault",
    primaryAction: { label: "Open", type: "open-file", target: "" },
    metadata: {
      journey_category: "notes",
      vault_scope: "private",
      format: "md",
      skill: "brain",
    },
  },
];

const documentSweepFilteredItems = [
  {
    id: "doc-invoice",
    title: "Invoice",
    description: "Download invoice",
    hub: "downloads",
    type: "document",
    path: "/Users/me/Downloads/invoice.pdf",
    primaryAction: { label: "Open", type: "open-file", target: "/Users/me/Downloads/invoice.pdf" },
    metadata: {
      source_root: "downloads",
      fileType: "pdf",
    },
  },
];

const mockBrowseState = {
  activeCategory: { id: "notes", label: "Notes", singularLabel: "Note" },
  archivedFilter: null,
  archivedItems: [],
  capabilityClientFilter: null,
  capabilityClientItems: [],
  categoryFreshness: {},
  changeView: jest.fn(),
  closeDetail: jest.fn(),
  containerRef: { current: null },
  detailLoading: false,
  driftFilter: null,
  driftItems: [],
  effectiveViewMode: "notes",
  activeFolderContext: { scope: "all", label: "All Brains" },
  folderContextOptions: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
  folderContextLoading: false,
  setActiveFolderContext: jest.fn(),
  scanFolderForContext: jest.fn(),
  error: null,
  exposureFilter: null,
  exposureItems: [],
  filtered: sweepFilteredItems,
  handleDragStart: jest.fn(),
  handleKeyboardResize: jest.fn(),
  handleRunMcp: jest.fn(),
  handleSemanticSearch: jest.fn(),
  hubFilter: "brain",
  hubItems: [],
  kindFilter: "all",
  lastIndexed: null,
  loading: false,
  managementFilter: null,
  managementItems: [],
  masterClients: [],
  masterFilter: null,
  notIndexed: false,
  ownerFilter: null,
  ownerItems: [],
  pageSize: 30,
  pinnedItems: [],
  pluginFilter: null,
  pluginNames: [],
  policyScopeFilter: null,
  policyScopeItems: [],
  refetch: mockRefetch,
  scheduledExecutionDetail: null,
  scheduledExecutionDetailLoading: false,
  scopeFilter: "private",
  scopeItems: [],
  search: "alpha",
  selectScheduledExecution: jest.fn(),
  selectSkill: jest.fn(),
  selectedSchedule: null,
  selectedSkill: null,
  semanticError: null,
  semanticLoading: false,
  semanticResultsActive: false,
  semanticResults: [],
  semanticDisplayResults: [],
  semanticSearched: false,
  setArchivedFilter: jest.fn(),
  setCapabilityClientFilter: jest.fn(),
  setDriftFilter: jest.fn(),
  setExposureFilter: jest.fn(),
  setHubFilter: jest.fn(),
  setKindFilter: jest.fn(),
  setManagementFilter: jest.fn(),
  setMasterFilter: jest.fn(),
  setOwnerFilter: jest.fn(),
  setPluginFilter: jest.fn(),
  setPolicyScopeFilter: jest.fn(),
  setScopeFilter: jest.fn(),
  setSearch: jest.fn(),
  setSemanticMode: jest.fn(),
  setSemanticResults: jest.fn(),
  setSemanticSearched: jest.fn(),
  setSkillTagFilter: jest.fn(),
  setSortBy: jest.fn(),
  setSourceFilter: jest.fn(),
  setSurfaceFilter: jest.fn(),
  setTagFilter: jest.fn(),
  setTypeFilter: jest.fn(),
  setVisibleCount: jest.fn(),
  skillDetail: null,
  skillTagFilter: null,
  skillTagItems: [],
  sortBy: "name-asc",
  sorted: sweepFilteredItems,
  sourceFilter: null,
  splitPercent: 60,
  surfaceFilter: null,
  surfaceItems: [],
  sweepFilteredItems,
  sweepFilterSummary: {
    search: "alpha",
    scope: "private",
    hub: "workspace",
    tag: "md",
    kind: "all",
    source: "all",
    viewMode: "notes",
  },
  tagFilter: "md",
  tagItems: [],
  totalCount: null,
  truncated: false,
  typeFilter: null,
  typeItems: [],
  visibleCategories: [{ id: "notes", label: "Notes", group: "content" }],
  visibleCount: 30,
};

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => new URLSearchParams(),
}));

// No manual @tanstack/react-query mock: the global render wrapper
// (tests/dashboard/__mocks__/testing-library-react.tsx) supplies a real
// QueryClientProvider, so useQueryClient resolves to a real client.

jest.mock("sonner", () => ({
  toast: {
    loading: jest.fn(() => "toast-1"),
    success: jest.fn(),
    error: jest.fn(),
  },
}));

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

jest.mock("@/components/shared/BrowseCategoryActions", () => ({
  ApiRoutesStats: () => <div>API stats</div>,
  BrowseCategoryActions: ({ onSweepVisible, sweeping }: { onSweepVisible?: () => void; sweeping?: boolean }) => (
    <button type="button" disabled={sweeping} onClick={onSweepVisible}>
      Sweep visible
    </button>
  ),
  // Surface the sweep affordance as a clickable control so this test can drive
  // the same dispatch the real overflow menu item triggers.
  useBrowseCategoryActions: ({ onSweepVisible, sweeping }: { onSweepVisible?: () => void; sweeping?: boolean }) => ({
    items: onSweepVisible
      ? [{ id: "sweep", label: "Sweep visible", onSelect: onSweepVisible, disabled: sweeping }]
      : [],
    modal: onSweepVisible ? (
      <button type="button" disabled={sweeping} onClick={onSweepVisible}>
        Sweep visible
      </button>
    ) : null,
  }),
}));

jest.mock("@/components/shared/BrowseCategoryNav", () => ({
  BrowseCategoryNav: () => <div>Categories</div>,
}));

jest.mock("@/app/(views)/browse/BrowseToolbar", () => ({
  BrowseToolbar: () => <div>Toolbar</div>,
}));

jest.mock("@/app/(views)/browse/BrowseContentGrid", () => ({
  BrowseContentGrid: () => <div>Content grid</div>,
}));

jest.mock("@/components/shared/BrowseDetailPanel", () => ({
  BrowseDetailPanel: () => <div>Detail panel</div>,
}));

jest.mock("@/components/shared/BackgroundRoutineDetailPanel", () => ({
  BackgroundRoutineDetailPanel: () => <div>Routine detail</div>,
}));

jest.mock("@/features/browse/NoteDropZone", () => ({
  NoteDropZone: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/browse/NoteFAB", () => ({
  NoteFAB: () => <button type="button">Note FAB</button>,
}));

jest.mock("@/features/browse/NoteModal", () => ({
  NoteModal: () => <div>Note Modal</div>,
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: jest.fn() }),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("@/lib/browse/cliExecClient", () => ({
  runCliExecPrompt: (...args: unknown[]) => mockRunCliExecPrompt(...args),
}));

describe("Browse page Sweep visible action", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(mockBrowseState, {
      activeCategory: { id: "notes", label: "Notes", singularLabel: "Note" },
      effectiveViewMode: "notes",
      filtered: sweepFilteredItems,
      sorted: sweepFilteredItems,
      sweepFilteredItems,
      sweepFilterSummary: {
        search: "alpha",
        scope: "private",
        hub: "workspace",
        tag: "md",
        kind: "all",
        source: "all",
        viewMode: "notes",
      },
      tagFilter: "md",
      visibleCategories: [{ id: "notes", label: "Notes", group: "content" }],
    });
    mockMcpCall.mockResolvedValue(
      JSON.stringify({
        success: true,
        selection_id: "browse-sweep-20260513-120000-abcdef12",
        refusal_count: 1,
      }),
    );
    mockRunCliExecPrompt.mockResolvedValue({ answer: "ok" });
  });

  it("creates an MCP selection, dispatches the native prompt, and opens Archive", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Sweep visible" }));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith("hygiene-create-selection", {
        source_tab: "notes",
        filter_summary: mockBrowseState.sweepFilterSummary,
        targets: [
          expect.objectContaining({
            kind: "vault-notes",
            source_path: "/Users/me/Au-vault/notes/alpha.md",
            source_id: "note-alpha",
          }),
        ],
      });
    });

    await waitFor(() => {
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("Selection id: browse-sweep-20260513-120000-abcdef12"),
      );
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("Target count: 1"),
      );
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("Refusal count: 2"),
      );
      expect(mockRefetch).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith("/browse?view=archive");
    });
  });

  it("creates document sweep selections and dispatches document-source instructions", async () => {
    Object.assign(mockBrowseState, {
      activeCategory: { id: "documents", label: "Documents", singularLabel: "Document" },
      effectiveViewMode: "documents",
      filtered: documentSweepFilteredItems,
      sorted: documentSweepFilteredItems,
      sweepFilteredItems: documentSweepFilteredItems,
      sweepFilterSummary: {
        search: "invoice",
        scope: "downloads",
        hub: "downloads",
        tag: "pdf",
        kind: "all",
        source: "downloads",
        viewMode: "documents",
      },
      tagFilter: "pdf",
      visibleCategories: [{ id: "documents", label: "Documents", group: "content" }],
    });

    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Sweep visible" }));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith("hygiene-create-selection", {
        source_tab: "documents",
        filter_summary: mockBrowseState.sweepFilterSummary,
        targets: [
          expect.objectContaining({
            kind: "docs",
            archive_mode: "docs-archive",
            source_path: "/Users/me/Downloads/invoice.pdf",
            source_id: "doc-invoice",
          }),
        ],
      });
    });

    await waitFor(() => {
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("document-source files"),
      );
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("move high-confidence files into the correct Au-docs folder"),
      );
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        expect.stringContaining("destination, filename, privacy, or version grouping is ambiguous"),
      );
    });
  });
});
