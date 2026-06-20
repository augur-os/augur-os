/**
 * @jest-environment jsdom
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import PageActionButtons from "@/features/components/PageActionButtons";

const mockUseModeStore = jest.fn();
const mockUseMcpHealth = jest.fn();
const mockOpenChat = jest.fn();
const mockToggleMode = jest.fn();
const mockChatStore = {
  isOpen: false,
  cliProcess: null,
  openChat: mockOpenChat,
};

jest.mock("next/navigation", () => ({
  usePathname: () => "/browse",
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: jest.fn(),
    isExecuting: false,
    result: null,
    clearResult: jest.fn(),
  }),
}));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: () => mockUseModeStore(),
}));

jest.mock("@/hooks/useMcpHealth", () => ({
  useMcpHealth: () => mockUseMcpHealth(),
}));

jest.mock("@/features/hooks/usePageActionsData", () => ({
  usePageActionsData: () => ({
    buttons: [],
    shortcuts: [],
    dataContext: { path: null, lastUpdated: null },
    loading: false,
  }),
}));

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: () => mockChatStore,
}));

jest.mock("@/features/components/action-bar", () => ({
  ActionsMenu: () => <div>Actions</div>,
  DevToolsMenu: () => <div>Dev Tools</div>,
  ExecutionFeedbackModal: () => null,
  ModeToggle: () => <div>Mode</div>,
}));

jest.mock("@/features/components/TabCustomizePanel", () => ({
  __esModule: true,
  default: () => <div>Tabs</div>,
}));

jest.mock("@/lib/tabs/generated-registry", () => ({
  pluginTabRegistry: {},
}));

jest.mock("@/components/plugin/HubTabNav", () => ({
  TAB_CONFIG_UPDATED_EVENT: "tab-config-updated",
}));

describe("PageActionButtons", () => {
  beforeEach(() => {
    mockUseModeStore.mockReturnValue({
      mode: "development",
      toggleMode: mockToggleMode,
    });
    mockUseMcpHealth.mockReturnValue({
      data: {
        staleMcpConfig: false,
        migrationInProgress: false,
      },
      hasIssues: false,
      isLoading: false,
    });
    mockOpenChat.mockReset();
    mockToggleMode.mockReset();
    mockChatStore.isOpen = false;
    mockChatStore.cliProcess = null;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("hydrates without a portal mismatch", async () => {
    const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const container = document.createElement("div");
    document.body.appendChild(container);

    let root: ReturnType<typeof hydrateRoot> | null = null;

    try {
      container.innerHTML = renderToString(<PageActionButtons />);
      expect(container.innerHTML).toBe("");

      await act(async () => {
        root = hydrateRoot(container, <PageActionButtons />);
      });

      await waitFor(() => {
        expect(document.body.querySelector(".floating-action-bar")).not.toBeNull();
      });

      const loggedHydrationFailure = consoleErrorSpy.mock.calls.some(([message]) =>
        typeof message === "string" && message.includes("Hydration failed"),
      );
      expect(loggedHydrationFailure).toBe(false);
    } finally {
      root?.unmount();
      container.remove();
    }
  });

  it("renders the floating action bar as a desktop-only round launcher", async () => {
    render(<PageActionButtons />);

    await waitFor(() => {
      const bar = document.body.querySelector(".floating-action-bar");
      expect(bar).not.toBeNull();
    });

    const bar = document.body.querySelector(".floating-action-bar");
    expect(bar?.className).toContain("hidden");
    expect(bar?.className).toContain("md:flex");
    expect(bar?.className).toContain("right-6");
    expect(bar?.className).not.toContain("left-1/2");
    expect(bar?.className).not.toContain("liquid-glass");
    expect(screen.queryByRole("button", { name: "Collapse action bar" })).not.toBeInTheDocument();

    const launcher = await screen.findByTestId("collapsed-chat-launcher");
    expect(launcher.className).toContain("rounded-full");
    expect(launcher.className).toContain("h-12");
    expect(launcher.className).toContain("w-12");
  });

  it("still renders the desktop action bar in operation mode", async () => {
    mockUseModeStore.mockReturnValue({
      mode: "operation",
      toggleMode: mockToggleMode,
    });
    render(<PageActionButtons />);

    await waitFor(() => {
      expect(document.body.querySelector(".floating-action-bar")).not.toBeNull();
    });
  });

  it("keeps a desktop chat entry inside the floating action bar", async () => {
    const user = userEvent.setup();
    render(<PageActionButtons />);

    const chatButton = await screen.findByRole("button", { name: "Open chat" });
    await user.click(chatButton);

    expect(mockOpenChat).toHaveBeenCalledWith({ mode: "ide" });
  });

  it("does not render a separate mode chip in the desktop action bar", async () => {
    render(<PageActionButtons />);

    await waitFor(() => {
      expect(document.body.querySelector(".floating-action-bar")).not.toBeNull();
    });

    const bar = document.body.querySelector(".floating-action-bar");
    expect(bar).not.toHaveTextContent("USER");
    expect(bar).not.toHaveTextContent("BUILDER");
  });

  it("hides the desktop action bar while chat is open", async () => {
    mockChatStore.isOpen = true;
    render(<PageActionButtons />);

    await waitFor(() => {
      expect(document.body.querySelector(".floating-action-bar")).toBeNull();
    });
  });

  it("keeps a single round chat launcher without extra controls", async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    try {
      render(<PageActionButtons />);

      const mergedLauncher = await screen.findByTestId("collapsed-chat-launcher");
      expect(mergedLauncher).toBeInTheDocument();
      expect(mergedLauncher.querySelector(".fab-divider")).toBeNull();
      expect(screen.queryByRole("button", { name: "Collapse action bar" })).not.toBeInTheDocument();
      expect(screen.queryByText("Actions")).not.toBeInTheDocument();
      expect(within(mergedLauncher).queryByRole("button", { name: "Expand action bar" })).not.toBeInTheDocument();

      await user.click(mergedLauncher);
      expect(mockOpenChat).toHaveBeenCalledWith({ mode: "ide" });

      await user.hover(mergedLauncher);
      act(() => {
        jest.advanceTimersByTime(200);
      });
      expect(screen.queryByText("Actions")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Expand action bar" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Collapse action bar" })).not.toBeInTheDocument();
      expect(mergedLauncher).toHaveAttribute("data-status", "healthy");
    } finally {
      jest.useRealTimers();
    }
  });
});
