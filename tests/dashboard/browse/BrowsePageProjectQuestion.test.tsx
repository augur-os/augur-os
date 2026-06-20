/**
 * @jest-environment jsdom
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { renderWithQuery as render } from "../helpers/component-test-utils";

const mockOpenChat = jest.fn();
const mockOpenChatWithPreparedActionDraft = jest.fn();
const mockPush = jest.fn();
const mockRunAction = jest.fn();

const activeFolderContext = {
  scope: "brain" as const,
  brain_id: "project-demo",
  label: "Demo Project",
  project_root: "/tmp/demo-project",
};

const baseBrowseState = {
  containerRef: { current: null },
  selectedSkill: null,
  selectedSchedule: null,
  splitPercent: 60,
  lastIndexed: null,
  activeCategory: {
    id: "documents",
    label: "Documents",
    singularLabel: "Document",
    icon: "FolderOpen",
    devOnly: false,
    group: "content",
  },
  effectiveViewMode: "documents",
  truncated: false,
  totalCount: 0,
  sorted: [],
  visibleCategories: [{ id: "documents", label: "Documents", group: "content" }],
  categoryFreshness: {},
  changeView: jest.fn(),
  displayMode: "card",
  setDisplayMode: jest.fn(),
  refetch: jest.fn(),
  search: "",
  setSearch: jest.fn(),
  semanticResultsActive: false,
  setSemanticResults: jest.fn(),
  setSemanticMode: jest.fn(),
  setSemanticSearched: jest.fn(),
  handleSemanticSearch: jest.fn(),
  semanticLoading: false,
  semanticResults: [],
  semanticSearched: false,
  semanticSearchActive: false,
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
  archivedFilter: "active",
  setArchivedFilter: jest.fn(),
  archivedItems: [],
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
  problemFilter: null,
  setProblemFilter: jest.fn(),
  problemItems: [],
  brainFilter: null,
  setBrainFilter: jest.fn(),
  brainItems: [],
  focusMode: false,
  setFocusMode: jest.fn(),
  activeBrainId: "project-demo",
  scopeFilter: null,
  setScopeFilter: jest.fn(),
  scopeItems: [],
  exposureFilter: null,
  setExposureFilter: jest.fn(),
  exposureItems: [],
  surfaceFilter: null,
  setSurfaceFilter: jest.fn(),
  surfaceItems: [],
  ownerFilter: null,
  setOwnerFilter: jest.fn(),
  ownerItems: [],
  managementFilter: null,
  setManagementFilter: jest.fn(),
  managementItems: [],
  policyScopeFilter: null,
  setPolicyScopeFilter: jest.fn(),
  policyScopeItems: [],
  driftFilter: null,
  setDriftFilter: jest.fn(),
  driftItems: [],
  capabilityClientFilter: null,
  setCapabilityClientFilter: jest.fn(),
  capabilityClientItems: [],
  sortBy: "default",
  setSortBy: jest.fn(),
  filtered: [
    { id: "doc-1", title: "Doc 1", metadata: { problem_count: "3" } },
    { id: "doc-2", title: "Doc 2", metadata: { problem_count: "3" } },
    { id: "doc-3", title: "Doc 3", metadata: { problem_count: "-2" } },
  ],
  sweepFilteredItems: [],
  sweepFilterSummary: {
    search: "",
    scope: "all",
    hub: "all",
    tag: "all",
    kind: "all",
    source: "all",
    viewMode: "documents",
  },
  pinnedItems: [],
  loading: false,
  error: null,
  notIndexed: false,
  stale: false,
  visibleCount: 20,
  setVisibleCount: jest.fn(),
  pageSize: 20,
  handleRunMcp: jest.fn(),
  handleChatResult: jest.fn(),
  selectSkill: jest.fn(),
  detailLoading: false,
  skillDetail: null,
  scheduledExecutionDetail: null,
  scheduledExecutionDetailLoading: false,
  closeDetail: jest.fn(),
  handleDragStart: jest.fn(),
  handleKeyboardResize: jest.fn(),
  selectScheduledExecution: jest.fn(),
  isPinned: jest.fn(() => false),
  togglePin: jest.fn(),
  handleTriggerPrompt: jest.fn(),
  activeFolderContext,
  folderContextOptions: [{ id: "project-demo", scope: "brain", label: "Demo Project", brain_id: "project-demo" }],
  folderContextLoading: false,
  setActiveFolderContext: jest.fn(),
  scanFolderForContext: jest.fn(),
};

jest.mock("@/app/(views)/browse/useBrowseState", () => ({
  useBrowseState: () => baseBrowseState,
}));

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: (selector: (state: {
    openChat: typeof mockOpenChat;
    openChatWithPreparedActionDraft: typeof mockOpenChatWithPreparedActionDraft;
  }) => unknown) =>
    selector({
      openChat: mockOpenChat,
      openChatWithPreparedActionDraft: mockOpenChatWithPreparedActionDraft,
    }),
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

jest.mock("sonner", () => ({
  toast: {
    loading: jest.fn(() => "toast-1"),
    success: jest.fn(),
    error: jest.fn(),
    message: jest.fn(),
  },
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/lib/browse/cliExecClient", () => ({
  runCliExecPrompt: jest.fn(),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: mockRunAction,
    isExecuting: false,
    lastActionId: null,
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
  BrowseItemDetailPanel: () => <div>Item detail panel</div>,
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
  NoteModal: () => <div data-testid="note-modal">Note Modal</div>,
}));

jest.mock("@/app/(views)/browse/BrowseAddFolderDialog", () => ({
  BrowseAddFolderDialog: () => <div data-testid="add-folder-dialog" />,
}));

jest.mock("@/app/(views)/browse/CapabilityPolicyPanel", () => ({
  CapabilityPolicyPanel: () => <div>Capability policy</div>,
}));

jest.mock("@/features/browse/AddSkillModal", () => ({
  AddSkillModal: () => null,
}));

describe("BrowsePageClient project question integration", () => {
  beforeEach(() => {
    mockOpenChat.mockReset();
    mockOpenChatWithPreparedActionDraft.mockReset();
    mockRunAction.mockReset();
    mockPush.mockReset();
  });

  it("opens a prepared project inventory chat draft from the browse context menu", async () => {
    const { BrowsePageClient } = await import("@/app/(views)/browse/BrowsePageClient");
    render(<BrowsePageClient />);

    expect(screen.queryByRole("button", { name: "Ask Augur about this project" })).not.toBeInTheDocument();

    // The standalone "Manage" menu was folded into the brain-scope selector
    // (BrowseFolderContextMenu); category actions now live in its popover.
    fireEvent.click(screen.getByTestId("browse-context-menu-trigger"));
    expect(screen.getByRole("menuitem", { name: "Ask Augur about this project" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem", { name: "Ask Augur about this project" }));

    await waitFor(() => {
      expect(mockOpenChatWithPreparedActionDraft).toHaveBeenCalledTimes(1);
    });

    const [draft, context] = mockOpenChatWithPreparedActionDraft.mock.calls[0];
    expect(draft.id).toBe("ask-project-inventory-summary");
    expect(draft.prompt).toContain("Active folder: Demo Project");
    expect(draft.prompt).toContain("Project root: /tmp/demo-project");
    expect(draft.prompt).toContain("Inventory records visible in Browse: 3");
    expect(draft.prompt).toContain("Problem badges visible in Browse: 6");
    expect(context).toEqual({
      page: "browse",
      folderContext: activeFolderContext,
    });
  });
});
