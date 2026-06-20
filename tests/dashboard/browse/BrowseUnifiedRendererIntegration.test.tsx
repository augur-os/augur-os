import { render, screen } from "@testing-library/react";
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

const categories: Record<string, BrowseCategory> = {
  "background-routines": {
    id: "background-routines",
    label: "Routines",
    singularLabel: "Routine",
    icon: "Activity",
    devOnly: false,
    group: "content",
    journey_group: "loop",
    journey_order: 1,
    defaultDisplayMode: "list",
  },
  "mcp-servers": {
    id: "mcp-servers",
    label: "MCP Servers",
    singularLabel: "MCP Server",
    icon: "Server",
    devOnly: true,
    group: "dev",
    journey_group: "diagnostics",
    journey_order: 1,
    defaultDisplayMode: "list",
  },
  "api-routes": {
    id: "api-routes",
    label: "API Routes",
    singularLabel: "Route",
    icon: "Route",
    devOnly: true,
    group: "dev",
    journey_group: "capabilities",
    journey_order: 4,
    defaultDisplayMode: "list",
  },
  skills: {
    id: "skills",
    label: "Skills",
    singularLabel: "Skill",
    icon: "Puzzle",
    devOnly: false,
    group: "content",
    journey_group: "prompt",
    journey_order: 1,
  },
};

function browseItem(id: string): BrowseItem {
  return {
    id,
    title: id,
    description: `${id} description`,
    hub: "dev",
    icon: "Puzzle",
    primaryAction: { label: "Open", type: "navigate", target: `/browse/${id}` },
    metadata: {
      cadence: "daily",
      status: "healthy",
      method: "GET",
      route: `/api/${id}`,
      runtimeStatus: "running",
    },
  };
}

function renderGrid(
  viewMode: ViewMode,
  displayMode: "card" | "list",
  overrides: Partial<React.ComponentProps<typeof BrowseContentGrid>> = {},
) {
  render(
    <BrowseContentGrid
      effectiveViewMode={viewMode}
      activeCategory={categories[viewMode]}
      displayMode={displayMode}
      sorted={[browseItem(`${viewMode}-one`)]}
      pinnedItems={[]}
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
      isPinned={() => false}
      onTogglePin={jest.fn()}
      onTriggerPrompt={jest.fn()}
      {...overrides}
    />,
  );
}

describe("BrowseContentGrid unified renderer", () => {
  it.each(["background-routines", "mcp-servers", "api-routes"] as ViewMode[])(
    "renders %s as list row cards without tables",
    (viewMode) => {
      renderGrid(viewMode, "list");

      expect(screen.getByTestId("browse-display-list")).toBeInTheDocument();
      expect(screen.getByTestId("browse-list-row-card")).toHaveTextContent(`${viewMode}-one`);
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    },
  );

  it("renders skills through the same shared card shell", () => {
    renderGrid("skills", "card");

    expect(screen.getByTestId("browse-display-grid")).toBeInTheDocument();
    expect(screen.getByTestId("browse-card-shell")).toHaveTextContent("skills-one");
    expect(screen.queryByTestId("skill-browse-card")).not.toBeInTheDocument();
  });
});
