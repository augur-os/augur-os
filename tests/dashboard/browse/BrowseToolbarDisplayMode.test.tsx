/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import { BrowseToolbar } from "@/app/(views)/browse/BrowseToolbar";
import type { BrowseCategory } from "@/lib/browse/types";

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

function renderToolbar(overrides: Partial<React.ComponentProps<typeof BrowseToolbar>> = {}) {
  const onDisplayModeChange = jest.fn();
  render(
    <BrowseToolbar
      activeCategory={category}
      effectiveViewMode="skills"
      search=""
      onSearchChange={jest.fn()}
      onSemanticSearch={jest.fn()}
      semanticLoading={false}
      semanticResults={[]}
      semanticSearched={false}
      semanticError={null}
      tagFilter={null}
      onTagFilterChange={jest.fn()}
      tagItems={[]}
      hubFilter={null}
      onHubFilterChange={jest.fn()}
      hubItems={[]}
      sourceFilter={null}
      onSourceFilterChange={jest.fn()}
      kindFilter="all"
      onKindFilterChange={jest.fn()}
      archivedFilter={null}
      onArchivedFilterChange={jest.fn()}
      archivedItems={[]}
      masterFilter={null}
      onMasterFilterChange={jest.fn()}
      masterClients={[]}
      pluginFilter={null}
      onPluginFilterChange={jest.fn()}
      pluginNames={[]}
      typeFilter={null}
      onTypeFilterChange={jest.fn()}
      typeItems={[]}
      skillTagFilter={null}
      onSkillTagFilterChange={jest.fn()}
      skillTagItems={[]}
      sortBy="default"
      onSortChange={jest.fn()}
      displayMode="card"
      onDisplayModeChange={onDisplayModeChange}
      {...overrides}
    />,
  );
  return { onDisplayModeChange };
}

describe("BrowseToolbar display mode control", () => {
  it("renders card and list controls with the current mode pressed", () => {
    renderToolbar({ displayMode: "card" });

    expect(screen.getByRole("group", { name: "Display mode" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Card mode" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "List mode" })).toHaveAttribute("aria-pressed", "false");
  });

  it("changes only the requested display mode", () => {
    const { onDisplayModeChange } = renderToolbar({ displayMode: "card" });

    fireEvent.click(screen.getByRole("button", { name: "List mode" }));

    expect(onDisplayModeChange).toHaveBeenCalledWith("list");
  });
});
