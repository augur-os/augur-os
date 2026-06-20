import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import { PluginEventNotifier } from "@/components/plugin-wizard/PluginEventNotifier";
import { BrowseToolbar } from "@/app/(views)/browse/BrowseToolbar";
import { NoteFAB } from "@/features/browse/NoteFAB";

jest.mock("@/components/plugin-wizard/SkillWizard", () => ({
  SkillWizard: () => <div data-testid="skill-wizard" />,
}));

jest.mock("@/components/plugin-wizard/RemovalWizard", () => ({
  RemovalWizard: () => <div data-testid="removal-wizard" />,
}));

const mockUseMcpPoll = jest.fn();
jest.mock("@/lib/mcp/useMcpPoll", () => ({
  useMcpPoll: (...args: unknown[]) => mockUseMcpPoll(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

function renderBrowseToolbar() {
  return render(
    <BrowseToolbar
      activeCategory={{ id: "skills", label: "Skills", group: "library" } as never}
      effectiveViewMode="skills"
      search=""
      onSearchChange={jest.fn()}
      onSemanticSearch={jest.fn()}
      semanticLoading={false}
      semanticResults={[]}
      semanticSearched={false}
      semanticError={null}
      displayMode="grid"
      onDisplayModeChange={jest.fn()}
      archivedFilter="active"
      onArchivedFilterChange={jest.fn()}
      archivedItems={0}
      tagFilter={null}
      onTagFilterChange={jest.fn()}
      tagItems={[{ id: "all", label: "All" }, { id: "B", label: "B (5)" }]}
      hubFilter={null}
      onHubFilterChange={jest.fn()}
      hubItems={[{ id: "all", label: "All" }, { id: "command", label: "Command" }]}
      sourceFilter={null}
      onSourceFilterChange={jest.fn()}
      kindFilter="all"
      onKindFilterChange={jest.fn()}
      masterFilter={null}
      onMasterFilterChange={jest.fn()}
      masterClients={["augur", "codex"]}
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
}

describe("Browse responsive UI", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders plugin event notifications in flow on mobile so they do not cover Browse content", async () => {
    mockUseMcpPoll.mockReturnValue({
      data: {
        events: [
          {
            type: "skill_added",
            bundle: "adaptive",
            skill: "loop-security",
            timestamp: "2026-04-27T06:00:00Z",
            acknowledged: false,
          },
        ],
      },
    });

    render(<PluginEventNotifier pollingIntervalMs={60000} />);

    expect(await screen.findAllByText("New skill detected: loop-security")).toHaveLength(2);
    const mobileStack = document.querySelector("[data-testid='plugin-event-toast-stack-mobile']");
    const desktopStack = document.querySelector("[data-testid='plugin-event-toast-stack']");
    expect(mobileStack).toHaveClass("relative", "mt-14", "md:hidden");
    expect(mobileStack).not.toHaveClass("fixed");
    expect(desktopStack).toHaveClass("hidden", "md:flex", "fixed");
  });

  it("uses container-aware toolbar wrapping instead of auto-margin wrapping", () => {
    renderBrowseToolbar();

    const search = screen.getByLabelText("Search skills");
    const toolbar = search.closest("div")?.parentElement?.parentElement;
    expect(toolbar).toHaveClass("flex", "flex-wrap");
    expect(screen.getByLabelText("Sort order")).not.toHaveClass("ml-auto");
    expect(screen.queryByRole("button", { name: /focus on active brain/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enter select mode/i })).not.toBeInTheDocument();
  });

  it("keeps the mobile ingest action on the right so it does not cover filters", () => {
    render(<NoteFAB queue={[]} onAddClick={jest.fn()} />);

    const addButton = screen.getByRole("button", { name: "Add note" });
    const container = addButton.parentElement;

    expect(container).toHaveClass("fixed", "bottom-6", "right-6", "items-end");
    expect(container).not.toHaveClass("left-6");
    expect(addButton).toHaveClass("cursor-pointer");
  });

  it("suppresses the mobile ingest action when the filter form is open", () => {
    render(<NoteFAB queue={[]} onAddClick={jest.fn()} suppress />);

    expect(screen.queryByRole("button", { name: "Add note" })).not.toBeInTheDocument();
  });
});
