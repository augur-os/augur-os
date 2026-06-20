import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { TabPanel } from "@/features/components/chat/TabPanel";
import { PageScopedList } from "@/features/components/chat/PageScopedList";
import { FileContextMenu } from "@/features/components/chat/FileContextMenu";

// Mock createPortal so FileContextMenu renders inline
jest.mock("react-dom", () => ({
  ...jest.requireActual("react-dom"),
  createPortal: (node: React.ReactNode) => node,
}));

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
});

// ---------------------------------------------------------------------------
// T1: TabPanel
// ---------------------------------------------------------------------------
describe("T1: TabPanel", () => {
  const tabs = [
    { id: "actions", label: "Actions" },
    { id: "files", label: "Files" },
    { id: "debug", label: "Debug", devOnly: true },
  ];

  it("renders all non-devOnly tabs", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={jest.fn()}
        isOperationMode={true}
      >
        <div>content</div>
      </TabPanel>,
    );

    expect(screen.getByText("Actions")).toBeInTheDocument();
    expect(screen.getByText("Files")).toBeInTheDocument();
    expect(screen.queryByText("Debug")).not.toBeInTheDocument();
  });

  it("in dev mode, renders devOnly tabs with a DEV badge", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={jest.fn()}
        isOperationMode={false}
      >
        <div>content</div>
      </TabPanel>,
    );

    expect(screen.getByText("Debug")).toBeInTheDocument();
    expect(screen.getByText("DEV")).toBeInTheDocument();
  });

  it("in operation mode, hides devOnly tabs", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={jest.fn()}
        isOperationMode={true}
      >
        <div>content</div>
      </TabPanel>,
    );

    expect(screen.queryByText("Debug")).not.toBeInTheDocument();
    expect(screen.queryByText("DEV")).not.toBeInTheDocument();
  });

  it("clicking a tab calls onTabChange with the tab id", () => {
    const onTabChange = jest.fn();
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={onTabChange}
        isOperationMode={false}
      >
        <div>content</div>
      </TabPanel>,
    );

    fireEvent.click(screen.getByText("Files"));
    expect(onTabChange).toHaveBeenCalledWith("files");
  });

  it("active tab has violet text styling", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="files"
        onTabChange={jest.fn()}
        isOperationMode={false}
      >
        <div>content</div>
      </TabPanel>,
    );

    const filesButton = screen.getByText("Files").closest("button");
    expect(filesButton?.className).toContain("text-violet-400");

    const actionsButton = screen.getByText("Actions").closest("button");
    expect(actionsButton?.className).not.toContain("text-violet-400");
  });

  it("search bar appears when onSearchChange is provided", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={jest.fn()}
        isOperationMode={false}
        searchPlaceholder="Filter items..."
        searchValue=""
        onSearchChange={jest.fn()}
      >
        <div>content</div>
      </TabPanel>,
    );

    expect(screen.getByPlaceholderText("Filter items...")).toBeInTheDocument();
  });

  it("search bar hidden when onSearchChange is undefined", () => {
    render(
      <TabPanel
        tabs={tabs}
        activeTab="actions"
        onTabChange={jest.fn()}
        isOperationMode={false}
        searchPlaceholder="Filter items..."
      >
        <div>content</div>
      </TabPanel>,
    );

    expect(
      screen.queryByPlaceholderText("Filter items..."),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// T2: PageScopedList
// ---------------------------------------------------------------------------
describe("T2: PageScopedList", () => {
  const ItemComponent = ({ item, index }: { item: string; index: number }) => (
    <div data-testid={`item-${index}`}>{item}</div>
  );

  it("renders primary items using ItemComponent", () => {
    render(
      <PageScopedList
        items={["Alpha", "Beta"]}
        hubItems={[]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
      />,
    );

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("shows empty message when items is empty", () => {
    render(
      <PageScopedList
        items={[]}
        hubItems={[]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
        emptyMessage="Nothing here"
      />,
    );

    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("hub section hidden when hubItems is empty", () => {
    render(
      <PageScopedList
        items={["Alpha"]}
        hubItems={[]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
      />,
    );

    expect(screen.queryByText(/More from/)).not.toBeInTheDocument();
  });

  it("hub section visible when hubItems has items, starts collapsed", () => {
    render(
      <PageScopedList
        items={["Alpha"]}
        hubItems={["Gamma", "Delta"]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
      />,
    );

    expect(screen.getByText("More from Dev")).toBeInTheDocument();
    // Hub items are NOT rendered when collapsed
    expect(screen.queryByText("Gamma")).not.toBeInTheDocument();
    expect(screen.queryByText("Delta")).not.toBeInTheDocument();
  });

  it('clicking "More from {hubName}" expands to show hub items', () => {
    render(
      <PageScopedList
        items={["Alpha"]}
        hubItems={["Gamma", "Delta"]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
      />,
    );

    fireEvent.click(screen.getByText("More from Dev"));

    expect(screen.getByText("Gamma")).toBeInTheDocument();
    expect(screen.getByText("Delta")).toBeInTheDocument();
  });

  it("hub item count badge shows correct number", () => {
    render(
      <PageScopedList
        items={["Alpha"]}
        hubItems={["Gamma", "Delta", "Epsilon"]}
        hubName="Dev"
        ItemComponent={ItemComponent}
        itemProps={{}}
      />,
    );

    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// T3: FileContextMenu
// ---------------------------------------------------------------------------
describe("T3: FileContextMenu", () => {
  const defaultProps = {
    filePath: "/src/index.ts",
    fileName: "index.ts",
    onAttach: jest.fn(),
    onPreview: jest.fn(),
    onOpenExternal: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (navigator.clipboard.writeText as jest.Mock).mockClear();
  });

  it("left click calls onAttach with filePath", () => {
    const onAttach = jest.fn();
    render(
      <FileContextMenu {...defaultProps} onAttach={onAttach}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.click(screen.getByText("my-file.ts"));
    expect(onAttach).toHaveBeenCalledWith("/src/index.ts");
  });

  it("right click opens context menu with options", () => {
    render(
      <FileContextMenu {...defaultProps}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));

    expect(screen.getByText("Attach to Chat")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("Open in Finder")).toBeInTheDocument();
    expect(screen.getByText("Copy Path")).toBeInTheDocument();
  });

  it("with all optional callbacks shows 4 options", () => {
    render(
      <FileContextMenu {...defaultProps}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));

    const buttons = screen.getAllByRole("menuitem");
    expect(buttons).toHaveLength(4);
  });

  it("without optional callbacks shows only Attach and Copy Path", () => {
    render(
      <FileContextMenu
        filePath="/src/index.ts"
        fileName="index.ts"
        onAttach={jest.fn()}
      >
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));

    expect(screen.getByText("Attach to Chat")).toBeInTheDocument();
    expect(screen.getByText("Copy Path")).toBeInTheDocument();
    expect(screen.queryByText("Preview")).not.toBeInTheDocument();
    expect(screen.queryByText("Open in Finder")).not.toBeInTheDocument();
  });

  it('clicking "Attach to Chat" calls onAttach and closes menu', () => {
    const onAttach = jest.fn();
    render(
      <FileContextMenu {...defaultProps} onAttach={onAttach}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));
    fireEvent.click(screen.getByText("Attach to Chat"));

    expect(onAttach).toHaveBeenCalledWith("/src/index.ts");
    // Menu should be closed — options no longer visible
    expect(screen.queryByText("Copy Path")).not.toBeInTheDocument();
  });

  it('clicking "Copy Path" calls navigator.clipboard.writeText and closes menu', () => {
    render(
      <FileContextMenu {...defaultProps}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));
    fireEvent.click(screen.getByText("Copy Path"));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "/src/index.ts",
    );
    expect(screen.queryByText("Attach to Chat")).not.toBeInTheDocument();
  });

  it("pressing Escape closes the menu", () => {
    render(
      <FileContextMenu {...defaultProps}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));
    expect(screen.getByText("Attach to Chat")).toBeInTheDocument();

    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });

    expect(screen.queryByText("Attach to Chat")).not.toBeInTheDocument();
  });

  it("clicking outside closes the menu", () => {
    render(
      <FileContextMenu {...defaultProps}>
        <span>my-file.ts</span>
      </FileContextMenu>,
    );

    fireEvent.contextMenu(screen.getByText("my-file.ts"));
    expect(screen.getByText("Attach to Chat")).toBeInTheDocument();

    act(() => {
      fireEvent.mouseDown(document.body);
    });

    expect(screen.queryByText("Attach to Chat")).not.toBeInTheDocument();
  });
});
