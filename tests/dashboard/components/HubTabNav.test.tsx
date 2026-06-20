/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { HubTabNav } from "@/components/plugin/HubTabNav";

const mockUseModeStore = jest.fn();
const mockHubTabBar = jest.fn();

jest.mock("@/lib/tabs/generated-registry", () => ({
  pluginTabRegistry: {
    workspace: {
      title: "Workspace",
      subtitle: "Thinking surfaces",
      tabs: [{ id: "overview", label: "Overview", href: "/workspace" }],
      overflow: [],
      basePath: "/workspace",
    },
  },
}));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: () => mockUseModeStore(),
}));

jest.mock("@/components/HubTabBar", () => ({
  HubTabBar: (props: unknown) => {
    mockHubTabBar(props);
    return <div data-testid="hub-tab-bar">Hub Tabs</div>;
  },
}));

jest.mock("@/components/plugin/UserBlocksSection", () => ({
  UserBlocksSection: () => <div data-testid="user-blocks">User Blocks</div>,
}));

jest.mock("@/features/components/TabCustomizePanel", () => ({
  __esModule: true,
  default: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="tab-customize-panel">
      <button onClick={onClose}>Close Customize</button>
    </div>
  ),
}));

describe("HubTabNav", () => {
  beforeEach(() => {
    mockHubTabBar.mockClear();
    mockUseModeStore.mockReturnValue({
      mode: "operation",
    });
  });

  it("passes tab customization controls into the More menu in builder mode", () => {
    mockUseModeStore.mockReturnValue({
      mode: "development",
    });

    render(<HubTabNav hubId="workspace" />);

    expect(
      screen.queryByRole("button", { name: "Customize Workspace tabs" }),
    ).not.toBeInTheDocument();
    expect(mockHubTabBar).toHaveBeenCalledWith(
      expect.objectContaining({
        tabCustomizeLabel: "Customize Workspace tabs",
        tabCustomizeOpen: false,
      }),
    );
  });

  it("hides Customize Tabs outside builder mode", () => {
    render(<HubTabNav hubId="workspace" />);

    expect(
      screen.queryByRole("button", { name: "Customize Workspace tabs" }),
    ).not.toBeInTheDocument();
    expect(mockHubTabBar).toHaveBeenCalledWith(
      expect.objectContaining({
        tabCustomizeLabel: undefined,
        tabCustomizeOpen: false,
      }),
    );
  });
});
