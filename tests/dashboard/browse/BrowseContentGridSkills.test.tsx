import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { BrowseItem, BrowseCategory, ViewMode } from "@/lib/browse/types";
import { BrowseContentGrid } from "@/app/(views)/browse/BrowseContentGrid";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn().mockResolvedValue({}),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
}));

const skillItem: BrowseItem = {
  id: "skill-one",
  title: "Skill One",
  description: "Discover and enrich skill inventory",
  hub: "workspace",
  icon: "Puzzle",
  primaryAction: {
    label: "Open",
    type: "navigate",
    target: "/workspace/skill-one",
  },
  metadata: {
    ownership: "augur",
    hasDashboardPage: "true",
  },
};

const externalSkill: BrowseItem = {
  id: "skill-two",
  title: "Skill Two",
  description: "Search external repos",
  hub: "career",
  icon: "Search",
  primaryAction: {
    label: "Review",
    type: "navigate",
    target: "/career/skill-two",
  },
  metadata: {
    ownership: "external",
  },
};

const adoptedNeedsSetup: BrowseItem = {
  id: "skill-three",
  title: "Skill Three",
  description: "Adopted internal skill",
  hub: "life",
  icon: "Globe",
  primaryAction: {
    label: "Open",
    type: "navigate",
    target: "/life/skill-three",
  },
  metadata: {
    ownership: "adopted",
    needsSetup: "true",
  },
};

const sourceItem: BrowseItem = {
  id: "source-one",
  title: "README",
  description: "Project README",
  hub: "career",
  icon: "FileText",
  primaryAction: {
    label: "Open",
    type: "navigate",
    target: "/career/readme",
  },
};

const skillsCategory: BrowseCategory = {
  id: "skills",
  label: "Skills",
  singularLabel: "Skill",
  icon: "Puzzle",
  devOnly: false,
  group: "content",
};

const sourcesCategory: BrowseCategory = {
  id: "sources",
  label: "Sources",
  singularLabel: "Source",
  icon: "FileSearch",
  devOnly: false,
  group: "content",
};

function makeProps(
  overrides: Partial<{
    effectiveViewMode: ViewMode;
    activeCategory: BrowseCategory;
    sorted: BrowseItem[];
    pinnedItems: BrowseItem[];
    semanticResultsActive: boolean;
    semanticResults: BrowseItem[];
    semanticLoading: boolean;
    loading: boolean;
    error: string | null;
    notIndexed: boolean;
    visibleCount: number;
    selectedSkill: string | null;
    isPinned: (item: BrowseItem) => boolean;
    onTogglePin: (item: BrowseItem) => void;
    onRunMcp: jest.Mock;
  }> = {},
) {
  const effectiveViewMode = overrides.effectiveViewMode ?? "skills";
  const activeCategory =
    overrides.activeCategory ??
    (effectiveViewMode === "skills" ? skillsCategory : sourcesCategory);

  return {
    effectiveViewMode,
    activeCategory,
    displayMode: "card" as const,
    sorted: overrides.sorted ?? [skillItem, externalSkill, adoptedNeedsSetup],
    pinnedItems: overrides.pinnedItems ?? [],
    semanticResultsActive: overrides.semanticResultsActive ?? false,
    semanticResults: overrides.semanticResults ?? [],
    semanticLoading: overrides.semanticLoading ?? false,
    loading: overrides.loading ?? false,
    error: overrides.error ?? null,
    refetch: jest.fn(),
    notIndexed: overrides.notIndexed ?? false,
    visibleCount: overrides.visibleCount ?? 20,
    onLoadMore: jest.fn(),
    pageSize: 20,
    selectedSkill: overrides.selectedSkill ?? null,
    selectedSchedule: null,
    isPinned: overrides.isPinned ?? jest.fn(() => false),
    onTogglePin: overrides.onTogglePin ?? jest.fn(),
    hubFilter: null,
    search: "",
    onRunMcp: overrides.onRunMcp ?? jest.fn(),
    onSelectSkill: jest.fn(),
    onSelectItem: jest.fn(),
    onSelectCapability: jest.fn(),
    onSelectScheduledExecution: jest.fn(),
    onTriggerPrompt: jest.fn(),
  };
}

describe("BrowseContentGrid skills tab", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mcpCall as jest.Mock).mockResolvedValue({});
  });

  it("renders skill insight strip for skills with inventory counts", () => {
    const onSelectSkill = jest.fn();
    render(
      <BrowseContentGrid
        {...makeProps()}
        onSelectSkill={onSelectSkill}
      />,
    );

    const strip = screen.getByTestId("skills-insight-strip");

    expect(strip).toHaveTextContent("Total: 3");
    expect(strip).toHaveTextContent("Augur: 1");
    expect(strip).toHaveTextContent("External: 1");
    expect(strip).toHaveTextContent("Adopted: 1");
    expect(strip).toHaveTextContent("Needs setup: 1");
  });

  it("uses the shared card shell for skill cards and calls onSelectSkill on click", () => {
    const onSelectSkill = jest.fn();
    render(
      <BrowseContentGrid
        {...makeProps()}
        onSelectSkill={onSelectSkill}
      />,
    );

    const skillCards = screen.getAllByTestId("browse-card-shell");
    expect(skillCards).toHaveLength(3);
    expect(screen.queryByTestId("skill-browse-card")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Skill One" }));
    expect(onSelectSkill).toHaveBeenCalledWith("skill-one");
    expect(onSelectSkill).toHaveBeenCalledTimes(1);
  });

  it("keeps selected ring behavior for skills cards", () => {
    render(
      <BrowseContentGrid
        {...makeProps({
          selectedSkill: "skill-three",
          sorted: [skillItem, externalSkill, adoptedNeedsSetup],
        })}
      />,
    );

    const cards = screen.getAllByTestId("browse-card-shell");
    const selectedCard = cards[2];

    expect(selectedCard).toHaveClass("ring-2");
    expect(selectedCard).toHaveClass("ring-[var(--accent-primary)]/25");
  });

  it("does not render retired client selector controls for run-action skill primary actions", () => {
    const lowQualitySkill: BrowseItem = {
      ...skillItem,
      id: "skill-improve",
      title: "Skill Improve",
      metadata: {
        ownership: "augur",
        qualityTier: "D",
        qualityScore: "24",
      },
    };

    render(
      <BrowseContentGrid
        {...makeProps({
          sorted: [lowQualitySkill],
        })}
      />,
    );

    expect(screen.queryByTestId("client-selector")).not.toBeInTheDocument();
  });

  it("shows private skill promote overflow action from shared browse actions", () => {
    const privateSkill: BrowseItem = {
      ...skillItem,
      id: "private-skill",
      title: "Private Skill",
      description: "Drafted in the private vault",
      path: "/Users/example/Au-vault/private/skills/private-skill/SKILL.md",
      metadata: {
        vault_scope: "private",
        promotion_state: "private",
        source_root: "private-vault",
      },
    };

    render(
      <BrowseContentGrid
        {...makeProps({
          sorted: [privateSkill],
        })}
      />,
    );

    fireEvent.click(screen.getByTestId("browse-card-overflow"));

    expect(screen.getByRole("menuitem", { name: "Promote" })).toBeInTheDocument();
  });

  it("passes pin state to skill cards", () => {
    render(
      <BrowseContentGrid
        {...makeProps({ sorted: [skillItem] })}
        isPinned={(item) => item.id === "skill-one"}
        onTogglePin={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Unpin Skill One" })).toHaveAttribute("aria-pressed", "true");
  });

  it("contains keyboard activation on skill pin buttons", () => {
    const onSelectSkill = jest.fn();
    const onTogglePin = jest.fn();
    render(
      <BrowseContentGrid
        {...makeProps({ sorted: [skillItem] })}
        isPinned={(item) => item.id === "skill-one"}
        onTogglePin={onTogglePin}
        onSelectSkill={onSelectSkill}
      />,
    );

    const pinButton = screen.getByRole("button", { name: "Unpin Skill One" });
    fireEvent.keyDown(pinButton, { key: "Enter" });
    fireEvent.click(pinButton);

    expect(onTogglePin).toHaveBeenCalledWith(skillItem);
    expect(onTogglePin).toHaveBeenCalledTimes(1);
    expect(onSelectSkill).not.toHaveBeenCalled();
  });
});

describe("BrowseContentGrid non-skill categories", () => {
  it("passes pin state and toggle handler to pinned page strip cards", () => {
    const pinnedPage: BrowseItem = {
      id: "pinned-page",
      title: "Pinned Page",
      description: "Pinned dashboard page",
      hub: "workspace",
      icon: "PanelsTopLeft",
      primaryAction: {
        label: "Open",
        type: "navigate",
        target: "/workspace/pinned-page",
      },
    };
    const onTogglePin = jest.fn();

    render(
      <BrowseContentGrid
        {...makeProps({
          effectiveViewMode: "pages",
          activeCategory: {
            id: "pages",
            label: "Pages",
            singularLabel: "Page",
            icon: "PanelsTopLeft",
            devOnly: false,
            group: "content",
          },
          sorted: [sourceItem],
          pinnedItems: [pinnedPage],
        })}
        isPinned={(item) => item.id === "pinned-page"}
        onTogglePin={onTogglePin}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Unpin Pinned Page" }));

    expect(onTogglePin).toHaveBeenCalledWith(pinnedPage);
    expect(onTogglePin).toHaveBeenCalledTimes(1);
  });

  it("does not render skills insight strip for sources", () => {
    render(
      <BrowseContentGrid
        {...makeProps({
          effectiveViewMode: "sources",
          activeCategory: sourcesCategory,
          sorted: [sourceItem],
        })}
      />,
    );

    expect(screen.queryByTestId("skills-insight-strip")).not.toBeInTheDocument();
    expect(screen.getByTestId("browse-card-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("skill-browse-card")).not.toBeInTheDocument();
  });

  it("reindexes the mapped category for not-indexed display modes", async () => {
    const refetch = jest.fn();
    render(
      <BrowseContentGrid
        {...makeProps({
          effectiveViewMode: "pages",
          activeCategory: {
            id: "pages",
            label: "Pages",
            singularLabel: "Page",
            icon: "PanelsTopLeft",
            devOnly: false,
            group: "content",
          },
          sorted: [],
          notIndexed: true,
        })}
        refetch={refetch}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /index this category/i }));

    await waitFor(() => {
      expect(mcpCall).toHaveBeenCalledWith("reindex-browse-category", { category: "pages" });
      expect(refetch).toHaveBeenCalled();
    });
  });
});
