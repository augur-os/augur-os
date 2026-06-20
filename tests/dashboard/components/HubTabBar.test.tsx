/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { useState } from "react";
import { HubTabBar } from "@/components/HubTabBar";

const mockReplace = jest.fn();
let mockMode = "operation";
let mockSearchParams = new URLSearchParams();
let mockPathname = "/workspace";

jest.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => mockSearchParams,
}));

jest.mock("@/components/plugin/CustomizePanel", () => ({
  CustomizePanel: ({
    open,
  }: {
    open: boolean;
  }) => (open ? <div data-testid="page-customize-panel">Customize Page</div> : null),
}));

jest.mock("@/components/tabs/GroupDropdown", () => ({
  GroupDropdown: () => null,
}));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: (selector: (state: { mode: string }) => unknown) =>
    selector({ mode: mockMode }),
}));

function TabCustomizeHarness() {
  const [open, setOpen] = useState(false);

  return (
    <HubTabBar
      tabs={[{ id: "overview", label: "Overview", href: "/workspace" }]}
      blocks={[
        {
          id: "memory",
          label: "Memory",
          skill: "workspace",
          icon: "LayoutDashboard",
        },
      ]}
      hubId="workspace"
      tabCustomizeLabel="Customize Workspace tabs"
      tabCustomizeOpen={open}
      onOpenTabCustomize={() => setOpen(true)}
      onCloseTabCustomize={() => setOpen(false)}
      tabCustomizePanel={
        <div data-testid="tab-customize-panel">Customize Tabs</div>
      }
    />
  );
}

describe("HubTabBar", () => {
  beforeEach(() => {
    mockMode = "operation";
    mockSearchParams = new URLSearchParams();
    mockPathname = "/workspace";
    mockReplace.mockReset();
  });

  it("uses a single More button for overflow and customization actions", () => {
    mockMode = "development";
    render(<TabCustomizeHarness />);

    expect(screen.getByRole("button", { name: "More" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Customize page" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "More" }));

    expect(
      screen.getByRole("menuitem", { name: "Customize Workspace tabs" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Customize page" }),
    ).toBeInTheDocument();
  });

  it("hides page customization outside builder mode", () => {
    render(<TabCustomizeHarness />);

    fireEvent.click(screen.getByRole("button", { name: "More" }));

    expect(
      screen.getByRole("menuitem", { name: "Customize Workspace tabs" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: "Customize page" }),
    ).not.toBeInTheDocument();
  });

  it("anchors the tab customization panel to the More menu container", () => {
    mockMode = "development";
    render(<TabCustomizeHarness />);

    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Customize Workspace tabs" }));

    expect(screen.getByTestId("tab-customize-panel")).toBeInTheDocument();
    expect(screen.getByTestId("hub-tab-more-panel-anchor")).toHaveClass(
      "absolute",
      "top-full",
      "right-0",
    );
  });

  it("anchors page customization to the same More menu container", () => {
    mockMode = "development";
    render(<TabCustomizeHarness />);

    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Customize page" }));

    expect(screen.getByTestId("page-customize-panel")).toBeInTheDocument();
    expect(screen.getByTestId("hub-tab-more-panel-anchor")).toHaveClass(
      "absolute",
      "top-full",
      "right-0",
    );
  });

  it("opens page customization from the customize query param in builder mode", async () => {
    mockMode = "development";
    mockSearchParams = new URLSearchParams("customize=1&view=compact");

    render(
      <HubTabBar
        tabs={[{ id: "overview", label: "Overview", href: "/workspace" }]}
        blocks={[
          {
            id: "memory",
            label: "Memory",
            skill: "workspace",
            icon: "LayoutDashboard",
          },
        ]}
        hubId="workspace"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("page-customize-panel")).toBeInTheDocument();
    });
    expect(mockReplace).toHaveBeenCalledWith("/workspace?view=compact", {
      scroll: false,
    });
  });

  it("includes config pages in overflow navigation", async () => {
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get: () => 260,
    });
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
      configurable: true,
      get: () => 120,
    });

    render(
      <HubTabBar
        tabs={[
          { id: "overview", label: "Overview", href: "/workspace" },
          { id: "memory", label: "Memory", href: "/workspace/memory" },
        ]}
        configPages={[
          {
            id: "vault",
            label: "Augur Vault",
            href: "/workspace/vault",
            icon: "BookMarked",
          },
        ]}
        hubId="workspace"
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "More" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "More" }));

    expect(
      screen.getByRole("menuitem", { name: /Augur Vault/i }),
    ).toBeInTheDocument();
  });

  it("labels the More button with the active collapsed page", async () => {
    mockPathname = "/workspace/daily-logs";
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get: () => 260,
    });
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
      configurable: true,
      get: () => 120,
    });

    render(
      <HubTabBar
        tabs={[
          { id: "overview", label: "Overview", href: "/workspace" },
          { id: "memory", label: "Memory", href: "/workspace/memory" },
          { id: "daily-logs", label: "Daily Logs", href: "/workspace/daily-logs" },
        ]}
        hubId="workspace"
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Daily Logs" })).toBeInTheDocument();
    });
  });
});
