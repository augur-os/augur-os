/**
 * @jest-environment jsdom
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseAirplaneModeStore = jest.fn();
const mockUseMcpQuery = jest.fn();
const mockSetAirplaneMode = jest.fn();
const mockToggleAirplaneMode = jest.fn();

jest.mock("@/lib/stores/airplaneModeStore", () => ({
  useAirplaneModeStore: () => mockUseAirplaneModeStore(),
}));

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

import { ChatRouteControl } from "@/features/components/chat/ChatRouteControl";
import { FloatingChatHeader } from "@/features/components/chat/ChatHeader";
import { createQueryWrapper } from "../helpers/component-test-utils";

function renderRouteControl(ui: React.ReactElement) {
  const { Wrapper } = createQueryWrapper();
  return render(ui, { wrapper: Wrapper });
}

function renderHeader(ui: React.ReactElement) {
  const { Wrapper } = createQueryWrapper();
  return render(ui, { wrapper: Wrapper });
}

function mockSession(status: Record<string, unknown> = { status: "exited" }) {
  global.fetch = jest.fn(async () => ({
    ok: true,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => status,
    text: async () => JSON.stringify(status),
  })) as unknown as typeof fetch;
}

function mockAirplaneState(overrides: Record<string, unknown> = {}) {
  mockUseAirplaneModeStore.mockReturnValue({
    airplaneMode: false,
    airplaneModeReady: true,
    airplaneBackendReady: true,
    airplaneLocalModel: "qwen3.5:9b",
    airplaneModeError: null,
    setAirplaneMode: mockSetAirplaneMode,
    toggleAirplaneMode: jest.fn(),
    ...overrides,
  });
}

function mockMcpQueries(overrides: { integrations?: string[]; integrationError?: string | null } = {}) {
  mockUseMcpQuery.mockImplementation((key: string) => {
    if (key === "ollama-integrations") {
      return {
        data: overrides.integrationError
          ? null
          : { integrations: overrides.integrations ?? ["claude", "codex"] },
        loading: false,
        error: overrides.integrationError ?? null,
        refetch: jest.fn(),
      };
    }
    return { data: null, loading: false, error: null, refetch: jest.fn() };
  });
}

describe("ChatRouteControl", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSetAirplaneMode.mockReset();
    mockSetAirplaneMode.mockResolvedValue(undefined);
    mockSession();
    mockAirplaneState();
    mockMcpQueries();
  });

  it("renders Use offline while cloud routing is active and does not toggle on open", () => {
    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={false}
        startCli={jest.fn()}
        stopCli={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/new chats will use the configured local model/i)).toBeInTheDocument();
    expect(screen.getByText(/preference: cloud/i)).toBeInTheDocument();
    expect(screen.getByText(/this chat: no running session/i)).toBeInTheDocument();
    expect(screen.getByText("Use offline")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open settings/i })).toHaveAttribute(
      "href",
      "/settings/ai",
    );
    expect(mockSetAirplaneMode).not.toHaveBeenCalled();
  });

  it("switches the preference for new chats without restarting", async () => {
    const startCli = jest.fn();
    const stopCli = jest.fn();
    mockSetAirplaneMode.mockResolvedValue(undefined);

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={false}
        startCli={startCli}
        stopCli={stopCli}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));
    fireEvent.click(screen.getByRole("button", { name: /switch for new chats/i }));

    await waitFor(() => expect(mockSetAirplaneMode).toHaveBeenCalledWith(true));
    expect(stopCli).not.toHaveBeenCalled();
    expect(startCli).not.toHaveBeenCalled();
  });

  it("restarts a running chat with an explicit target route override", async () => {
    const startCli = jest.fn().mockResolvedValue(undefined);
    const stopCli = jest.fn().mockResolvedValue(undefined);
    const onClear = jest.fn();
    mockSetAirplaneMode.mockResolvedValue(undefined);
    mockSession({
      status: "running",
      sessionAirplaneMode: false,
      sessionLocalModel: null,
    });

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={true}
        startCli={startCli}
        stopCli={stopCli}
        onClear={onClear}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));
    expect(screen.getByText(/preference: cloud/i)).toBeInTheDocument();
    expect(await screen.findByText(/this chat: cloud/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /switch \+ restart/i }));

    await waitFor(() => expect(mockSetAirplaneMode).toHaveBeenCalledWith(true));
    expect(stopCli).toHaveBeenCalledWith("claude");
    expect(onClear).toHaveBeenCalledTimes(1);
    expect(startCli).toHaveBeenCalledWith("claude", { airplaneMode: true });
  });

  it("renders Use cloud while offline routing is active and shows the offline preference", async () => {
    mockAirplaneState({ airplaneMode: true });
    mockSession({
      status: "running",
      sessionAirplaneMode: false,
      sessionLocalModel: null,
    });

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={true}
        startCli={jest.fn()}
        stopCli={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use cloud for chat routing/i }));

    expect(screen.getByText("Use cloud")).toBeInTheDocument();
    expect(screen.getByText(/preference: offline/i)).toBeInTheDocument();
    expect(await screen.findByText(/this chat: cloud/i)).toBeInTheDocument();
    expect(screen.getByText(/differs until restart/i)).toBeInTheDocument();
  });

  it("keeps switch actions locked across close and reopen while a preference update is in flight", async () => {
    let resolvePreference!: () => void;
    mockSetAirplaneMode.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePreference = resolve;
        }),
    );

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={false}
        startCli={jest.fn()}
        stopCli={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));
    fireEvent.click(screen.getByRole("button", { name: /switch for new chats/i }));

    await waitFor(() => expect(mockSetAirplaneMode).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: /switch for new chats/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /close dialog/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));
    const reopenedSwitchButton = screen.getByRole("button", {
      name: /switch for new chats/i,
    });
    expect(reopenedSwitchButton).toBeDisabled();

    fireEvent.click(reopenedSwitchButton);
    expect(mockSetAirplaneMode).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolvePreference();
    });
  });

  it("sends unavailable offline users to Settings without a misleading switch action", () => {
    mockAirplaneState({ airplaneBackendReady: false, airplaneLocalModel: null });

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={false}
        startCli={jest.fn()}
        stopCli={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));

    expect(screen.getByText(/local backend setup is required/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /switch for new chats/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open settings/i })).toHaveAttribute(
      "href",
      "/settings/ai",
    );
  });

  it("keeps the sheet open and displays preference update errors", async () => {
    mockSetAirplaneMode.mockRejectedValue(new Error("preferences.yaml is unwritable"));

    renderRouteControl(
      <ChatRouteControl
        cliId="claude"
        isRunning={false}
        startCli={jest.fn()}
        stopCli={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /use offline for chat routing/i }));
    fireEvent.click(screen.getByRole("button", { name: /switch for new chats/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("preferences.yaml is unwritable");
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("FloatingChatHeader session conflict actions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn(async () => ({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "exited" }),
      text: async () => JSON.stringify({ status: "exited" }),
    })) as unknown as typeof fetch;
    mockUseAirplaneModeStore.mockReturnValue({
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: true,
      airplaneModeError: null,
      toggleAirplaneMode: mockToggleAirplaneMode,
    });
    mockUseMcpQuery.mockReturnValue({
      data: { integrations: ["claude"] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
  });

  it("renders switch and take-over actions for a conflicting native-terminal owner", () => {
    const onSwitchSessionOwner = jest.fn();
    const onTakeOverSessionOwner = jest.fn();

    renderHeader(
      <FloatingChatHeader
        state={{
          isOperationMode: false,
          showCliSelector: false,
          isRunning: false,
          isEnlarged: false,
          isTerminalHandoffOpening: false,
        }}
        selectorRef={{ current: null }}
        setShowCliSelector={jest.fn()}
        statusColor="bg-slate-400"
        statusLabel="Idle"
        selectedCli="claude"
        configs={[]}
        getCliLabel={() => "Claude"}
        getCliAvatarColor={() => "bg-blue-500"}
        handleCliSelect={jest.fn()}
        cliProcess={null}
        chatView="chat"
        setChatView={jest.fn()}
        toggleEnlarged={jest.fn()}
        startCli={jest.fn()}
        stopCli={jest.fn()}
        onMinimize={jest.fn()}
        onClose={jest.fn()}
        sessionConflict={{
          sessionId: "session-123",
          owner: {
            surface: "native-terminal",
            pid: 9999,
            host: "other-host",
            cli_id: "claude",
          },
        }}
        onSwitchSessionOwner={onSwitchSessionOwner}
        onTakeOverSessionOwner={onTakeOverSessionOwner}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Switch to owning surface" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /take over here/i }));

    expect(onSwitchSessionOwner).toHaveBeenCalledTimes(1);
    expect(onTakeOverSessionOwner).toHaveBeenCalledTimes(1);
  });
});
