import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { BrowseCategory, BrowseItem, ViewMode } from "@/lib/browse/types";
import { BrowseContentGrid } from "@/app/(views)/browse/BrowseContentGrid";

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
}));

function item(id: string): BrowseItem {
  return {
    id,
    title: `${id} item`,
    description: `${id} description`,
    hub: "dev",
    primaryAction: { label: "Open", type: "navigate", target: `/browse/${id}` },
  };
}

function category(id: ViewMode): BrowseCategory {
  return {
    id,
    label: id,
    singularLabel: "Item",
    icon: "FileText",
    devOnly: true,
    group: "dev",
    journey_group: "diagnostics",
    journey_order: 1,
    defaultDisplayMode: "list",
  };
}

function renderGrid(viewMode: ViewMode) {
  render(
    <BrowseContentGrid
      effectiveViewMode={viewMode}
      activeCategory={category(viewMode)}
      displayMode="list"
      sorted={[item(viewMode)]}
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
      isPinned={jest.fn(() => false)}
      onTogglePin={jest.fn()}
      onTriggerPrompt={jest.fn()}
    />,
  );
}

describe("BrowseContentGrid legacy display bridge", () => {
  it.each(["tests", "logs"] as const)(
    "renders %s through unified list cards",
    (viewMode) => {
      renderGrid(viewMode);

      expect(screen.getByTestId("browse-display-list")).toBeInTheDocument();
      expect(screen.getByTestId("browse-list-row-card")).toHaveTextContent(`${viewMode} item`);
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    },
  );

  it("renders api-routes through unified list cards", () => {
    renderGrid("api-routes");

    expect(screen.getByTestId("browse-display-list")).toBeInTheDocument();
    expect(screen.getByTestId("browse-list-row-card")).toHaveTextContent("api-routes item");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows base Browse loading even when unified search is idle", () => {
    render(
      <BrowseContentGrid
        effectiveViewMode="skills"
        activeCategory={category("skills")}
        displayMode="card"
        sorted={[]}
        pinnedItems={[]}
        semanticResultsActive={false}
        semanticResults={[]}
        semanticLoading={false}
        loading={true}
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
        isPinned={jest.fn(() => false)}
        onTogglePin={jest.fn()}
        onTriggerPrompt={jest.fn()}
      />,
    );

    expect(screen.getAllByTestId("browse-card-skeleton")).toHaveLength(6);
  });

  it("shows an empty state instead of fallback cards for current empty unified search results", () => {
    render(
      <BrowseContentGrid
        effectiveViewMode="skills"
        activeCategory={category("skills")}
        displayMode="card"
        sorted={[item("fallback")]}
        pinnedItems={[]}
        semanticResultsActive={true}
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
        search="missing pitch artifact"
        onRunMcp={jest.fn()}
        onSelectSkill={jest.fn()}
        onSelectItem={jest.fn()}
        onSelectCapability={jest.fn()}
        onSelectScheduledExecution={jest.fn()}
        isPinned={jest.fn(() => false)}
        onTogglePin={jest.fn()}
        onTriggerPrompt={jest.fn()}
      />,
    );

    expect(screen.getByTestId("browse-empty-state")).toHaveTextContent("No skills found");
    expect(screen.queryByText("fallback item")).not.toBeInTheDocument();
  });

  it("explains empty project document folders as missing shared sources", () => {
    render(
      <BrowseContentGrid
        effectiveViewMode="documents"
        activeCategory={category("documents")}
        displayMode="card"
        sorted={[]}
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
        onChatResult={jest.fn()}
        onSelectSkill={jest.fn()}
        onSelectItem={jest.fn()}
        onSelectCapability={jest.fn()}
        onSelectScheduledExecution={jest.fn()}
        isPinned={jest.fn(() => false)}
        onTogglePin={jest.fn()}
        onTriggerPrompt={jest.fn()}
        activeFolderContext={{ scope: "brain", brain_id: "project-augur", label: "Augur" }}
      />,
    );

    expect(screen.getByTestId("browse-empty-state")).toHaveTextContent("No documents found");
    expect(screen.getByTestId("browse-empty-state")).toHaveTextContent(
      "No shared document source is attached to Augur yet.",
    );
    expect(screen.queryByText(/Try switching categories/i)).not.toBeInTheDocument();
  });
});
