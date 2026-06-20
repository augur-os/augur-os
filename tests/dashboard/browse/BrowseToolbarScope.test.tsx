/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

describe("BrowseToolbar scope filters", () => {
  it("calls the scope filter handler when selecting private in notes mode", async () => {
    const { BrowseToolbar } = await import("@/app/(views)/browse/BrowseToolbar");
    const user = userEvent.setup();
    const onScopeFilterChange = jest.fn();

    render(
      <BrowseToolbar
        activeCategory={{ id: "notes", label: "Notes" } as any}
        effectiveViewMode="notes"
        search=""
        onSearchChange={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        scopeFilter={null}
        onScopeFilterChange={onScopeFilterChange}
        scopeItems={[
          { id: "all", label: "Scope: All" },
          { id: "shared", label: "Shared" },
          { id: "private", label: "Private" },
          { id: "packet", label: "Packet" },
        ]}
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
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /show filters/i }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Filter by Scope" }),
      "private",
    );

    expect(onScopeFilterChange).toHaveBeenCalledWith("private");
  });
});
