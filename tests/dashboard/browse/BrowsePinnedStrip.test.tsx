import { render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowseContentGrid } from "@/app/(views)/browse/BrowseContentGrid";
import type { BrowseCategory, BrowseItem, ViewMode } from "@/lib/browse/types";
import type React from "react";

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

const skillsCategory: BrowseCategory = {
  id: "skills",
  label: "Skills",
  singularLabel: "Skill",
  icon: "Puzzle",
  devOnly: false,
  group: "content",
  journey_group: "prompt",
  journey_order: 1,
};

function browseItem(id: string, title: string): BrowseItem {
  return {
    id,
    title,
    description: `${title} description`,
    hub: "workspace",
    icon: "Puzzle",
    primaryAction: { label: "Open", type: "navigate", target: `/browse/${id}` },
  };
}

const pinned = browseItem("pinned-skill", "Pinned Skill");
const unpinned = browseItem("plain-skill", "Plain Skill");

function renderGrid(
  overrides: Partial<React.ComponentProps<typeof BrowseContentGrid>> = {},
) {
  render(
    <BrowseContentGrid
      effectiveViewMode={"skills" as ViewMode}
      activeCategory={skillsCategory}
      displayMode="card"
      // sortBrowseItems puts pinned first; the grid receives the full sorted list.
      sorted={[pinned, unpinned]}
      pinnedItems={[pinned]}
      semanticResultsActive={false}
      semanticResults={[]}
      semanticLoading={false}
      loading={false}
      error={null}
      refetch={jest.fn()}
      notIndexed={false}
      visibleCount={20}
      onLoadMore={jest.fn()}
      pageSize={20}
      selectedSkill={null}
      selectedSchedule={null}
      hubFilter={null}
      search=""
      onRunMcp={jest.fn()}
      onSelectSkill={jest.fn()}
      onSelectItem={jest.fn()}
      onSelectCapability={jest.fn()}
      onSelectScheduledExecution={jest.fn()}
      isPinned={(item) => item.id === pinned.id}
      onTogglePin={jest.fn()}
      onTriggerPrompt={jest.fn()}
      {...overrides}
    />,
  );
}

function cardsWithTitle(title: string): HTMLElement[] {
  return screen
    .getAllByTestId("browse-card-shell")
    .filter((card) => card.textContent?.includes(title));
}

describe("Browse pinned strip (all tabs)", () => {
  it("renders a dedicated Pinned section for non-pages view modes", () => {
    renderGrid();

    const strip = screen.getByTestId("browse-pinned-strip");
    expect(strip).toHaveTextContent(/pinned/i);
    expect(within(strip).getByTestId("browse-card-shell")).toHaveTextContent("Pinned Skill");
  });

  it("does not duplicate a pinned item between the strip and the main grid", () => {
    renderGrid();

    expect(cardsWithTitle("Pinned Skill")).toHaveLength(1);
  });

  it("keeps unpinned items in the main grid, outside the strip", () => {
    renderGrid();

    const strip = screen.getByTestId("browse-pinned-strip");
    expect(within(strip).queryByText("Plain Skill")).not.toBeInTheDocument();
    expect(cardsWithTitle("Plain Skill")).toHaveLength(1);
  });

  it("renders no strip when nothing is pinned", () => {
    renderGrid({ pinnedItems: [], isPinned: () => false });

    expect(screen.queryByTestId("browse-pinned-strip")).not.toBeInTheDocument();
    expect(cardsWithTitle("Plain Skill")).toHaveLength(1);
  });

  it("hides the strip during an active semantic search", () => {
    renderGrid({
      semanticResultsActive: true,
      semanticResults: [unpinned],
    });

    expect(screen.queryByTestId("browse-pinned-strip")).not.toBeInTheDocument();
  });
});
