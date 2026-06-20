/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import type { BrowseCategory, BrowseItem } from "@/lib/browse/types";
import { BrowseDisplayRenderer } from "@/app/(views)/browse/BrowseDisplayRenderer";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

const category: BrowseCategory = {
  id: "skills",
  label: "Skills",
  singularLabel: "Skill",
  icon: "Puzzle",
  devOnly: false,
  group: "content",
  journey_group: "prompt",
  journey_order: 1,
};

const notesCategory: BrowseCategory = {
  id: "notes",
  label: "Notes",
  singularLabel: "Note",
  icon: "FileText",
  devOnly: false,
  group: "content",
  journey_group: "context",
  journey_order: 2,
};

const commandCategory: BrowseCategory = {
  id: "commands",
  label: "Commands",
  singularLabel: "Command",
  icon: "Terminal",
  devOnly: true,
  group: "system",
  journey_group: "loop",
  journey_order: 3,
};

const items: BrowseItem[] = [
  {
    id: "skill-one",
    title: "Skill One",
    description: "Skill description",
    hub: "workspace",
    icon: "Puzzle",
    primaryAction: { label: "Open", type: "navigate", target: "/workspace/skill-one" },
    actions: [
      { id: "run", label: "Run", icon: "Play", type: "run-mcp", target: "skill-one:run" },
    ],
    metadata: { ownership: "augur", capabilityId: "skill:skill-one" },
  },
];

function renderRenderer(
  overrides: Partial<React.ComponentProps<typeof BrowseDisplayRenderer>> = {},
) {
  const props: React.ComponentProps<typeof BrowseDisplayRenderer> = {
    activeCategory: category,
    viewMode: "skills",
    displayMode: "card",
    items,
    selectedSkill: null,
    selectedSchedule: null,
    onRunMcp: jest.fn(),
    onSelectItem: jest.fn(),
    onSelectSkill: jest.fn(),
    onSelectCapability: jest.fn(),
    onSelectScheduledExecution: jest.fn(),
    isPinned: jest.fn(() => false),
    onTogglePin: jest.fn(),
    onTriggerPrompt: jest.fn(),
    ...overrides,
  };

  render(<BrowseDisplayRenderer {...props} />);
  return props;
}

describe("BrowseDisplayRenderer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders card mode through BrowseCardShell", () => {
    renderRenderer();

    expect(screen.getByTestId("browse-display-grid")).toBeInTheDocument();
    expect(screen.getByTestId("browse-card-shell")).toHaveTextContent("Skill One");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders command quality and KPI chips through the shared card shell", () => {
    renderRenderer({
      activeCategory: commandCategory,
      viewMode: "commands",
      items: [{
        id: "command:ask",
        title: "/ask",
        description: "Ask the project brain",
        hub: "command",
        icon: "Terminal",
        typeBadge: "command",
        path: "project-brain/capabilities/skills/ask/SKILL.md",
        primaryAction: {
          label: "Open",
          type: "open-file",
          target: "project-brain/capabilities/skills/ask/SKILL.md",
        },
        metadata: {
          qualityTier: "A",
          qualityScore: "88",
          docsScore: "80",
          wiringScore: "100",
          kpiStatus: "pass",
        },
      }],
    });

    expect(screen.getByTestId("browse-card-shell")).toHaveTextContent("Quality A 88");
    expect(screen.getByTestId("browse-card-shell")).toHaveTextContent("KPI ✓");
  });

  it("shows a badge overflow count instead of silently dropping extra tags", () => {
    renderRenderer({
      items: [
        {
          ...items[0],
          metadata: {
            ownership: "augur",
            capabilityId: "skill:skill-one",
            skillClients: "codex",
            skillType: "domain",
            skillTags: "tag-one,tag-two,tag-three,tag-four",
          },
        },
      ],
    });

    expect(screen.getByTestId("browse-card-shell")).toHaveTextContent("+");
    expect(screen.getByTitle(/tag-two/)).toBeInTheDocument();
  });

  it("renders list mode as compact row cards and not a table", () => {
    renderRenderer({ displayMode: "list" });

    expect(screen.getByTestId("browse-display-list")).toBeInTheDocument();
    expect(screen.getByTestId("browse-list-row-card")).toHaveTextContent("Skill One");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("routes skill selection from the shared shell", () => {
    const onSelectSkill = jest.fn();
    renderRenderer({ onSelectSkill });

    fireEvent.click(screen.getByRole("button", { name: "Skill One" }));

    expect(onSelectSkill).toHaveBeenCalledWith("skill-one");
  });

  it("routes policy and pin clicks without selecting the card", () => {
    const onSelectSkill = jest.fn();
    const onSelectCapability = jest.fn();
    const onTogglePin = jest.fn();
    renderRenderer({ onSelectSkill, onSelectCapability, onTogglePin });

    fireEvent.click(screen.getByRole("button", { name: "Pin Skill One" }));
    expect(onTogglePin).toHaveBeenCalledWith(items[0]);
    expect(onSelectSkill).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Review policy for Skill One" }));
    expect(onSelectCapability).toHaveBeenCalledWith(items[0]);
    expect(onSelectSkill).not.toHaveBeenCalled();
  });

  it.each([
    ["card", "browse-card-shell"],
    ["list", "browse-list-row-card"],
  ] as const)("uses item-specific policy accessible names in %s mode", (displayMode) => {
    const onSelectCapability = jest.fn();
    renderRenderer({ displayMode, onSelectCapability });

    fireEvent.click(screen.getByRole("button", { name: "Review policy for Skill One" }));

    expect(onSelectCapability).toHaveBeenCalledWith(items[0]);
  });

  it("executes derived navigate primary actions through the router", () => {
    renderRenderer();

    fireEvent.click(screen.getByRole("button", { name: "Open docs" }));

    expect(mockPush).toHaveBeenCalledWith("/browse/skill-one");
  });

  it("executes overflow actions through onRunMcp", () => {
    const onRunMcp = jest.fn();
    renderRenderer({ onRunMcp });

    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Run" }));

    expect(onRunMcp).toHaveBeenCalledWith("skill-one:run");
  });

  it("routes generated direct item actions from the overflow menu", () => {
    const onItemDirect = jest.fn();
    renderRenderer({ onItemDirect });

    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Health" }));

    expect(onItemDirect).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "skill-health",
        tool: "skill-resolvable-report",
      }),
      items[0],
    );
  });

  it("keeps article enrichment off non-article note overflow menus", () => {
    renderRenderer({
      activeCategory: notesCategory,
      viewMode: "notes",
      items: [{
        id: "note:thought:one",
        title: "Loose thought",
        description: "A thought note",
        hub: "workspace",
        icon: "MessageSquare",
        typeBadge: "thought",
        path: "notes/thought.md",
        primaryAction: { label: "Open", type: "open-file", target: "notes/thought.md" },
        metadata: { "x-augur-note-type": "thought" },
      }],
      onItemPrompt: jest.fn(),
      onItemDirect: jest.fn(),
    });

    fireEvent.click(screen.getByTestId("browse-card-overflow"));

    expect(screen.queryByRole("menuitem", { name: "Enrich" })).not.toBeInTheDocument();
  });

  it("routes article note enrichment through an AI prompt, not a direct mutation", () => {
    const onItemPrompt = jest.fn();
    const onItemDirect = jest.fn();

    renderRenderer({
      activeCategory: notesCategory,
      viewMode: "notes",
      items: [{
        id: "note:url:one",
        title: "Example article",
        description: "A saved URL",
        hub: "workspace",
        icon: "Link2",
        typeBadge: "url",
        path: "notes/example.md",
        primaryAction: { label: "Open", type: "open-file", target: "notes/example.md" },
        metadata: { "x-augur-note-type": "url" },
      }],
      onItemPrompt,
      onItemDirect,
    });

    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Enrich" }));

    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining("submit-enrich-article-result"));
    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining("notes/example.md"));
    expect(onItemDirect).not.toHaveBeenCalled();
  });

  it.each([
    ["card", "browse-card-shell"],
    ["list", "browse-list-row-card"],
  ] as const)("keeps %s article and title keyboard selection working", async (displayMode, testId) => {
    const user = userEvent.setup();
    const onSelectSkill = jest.fn();
    renderRenderer({ displayMode, onSelectSkill });

    const article = screen.getByTestId(testId);
    article.focus();
    expect(article).toHaveFocus();

    fireEvent.keyDown(article, { key: "Enter" });
    expect(onSelectSkill).toHaveBeenCalledTimes(1);
    expect(onSelectSkill).toHaveBeenLastCalledWith("skill-one");

    onSelectSkill.mockClear();
    const title = screen.getByRole("button", { name: "Skill One" });
    title.focus();
    expect(title).toHaveFocus();

    await user.keyboard("{Enter}");

    expect(onSelectSkill).toHaveBeenCalledTimes(1);
    expect(onSelectSkill).toHaveBeenLastCalledWith("skill-one");
  });

  it.each([
    ["card", "browse-card-overflow"],
    ["list", "browse-list-row-overflow"],
  ] as const)("does not select the %s item from child control keydown events", (displayMode, overflowTestId) => {
    const onSelectSkill = jest.fn();
    renderRenderer({ displayMode, onSelectSkill });

    fireEvent.keyDown(screen.getByRole("button", { name: "Open docs" }), { key: "Enter" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Review policy for Skill One" }), { key: "Enter" });
    fireEvent.keyDown(screen.getByTestId(overflowTestId), { key: "Enter" });

    expect(onSelectSkill).not.toHaveBeenCalled();
  });
});
