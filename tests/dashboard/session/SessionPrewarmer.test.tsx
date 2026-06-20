import { render, waitFor } from "@testing-library/react";

import SessionPrewarmer from "@/components/session/SessionPrewarmer";
import { createQueryWrapper } from "../helpers/component-test-utils";

// SessionPrewarmer now dispatches the prewarm via React Query's useMutation, so
// every render needs a QueryClientProvider in scope.
function renderPrewarmer() {
  const { Wrapper } = createQueryWrapper();
  return render(<SessionPrewarmer />, { wrapper: Wrapper });
}

const mockAirplaneState = {
  airplaneMode: true,
  airplaneModeReady: true,
  airplaneBackendReady: true,
  airplaneLocalModel: "qwen3.5:9b" as string | null,
  airplaneModeError: null as string | null,
  setAirplaneMode: jest.fn(),
  toggleAirplaneMode: jest.fn(),
};

jest.mock("next/navigation", () => ({
  usePathname: () => "/browse/test-skill",
}));

jest.mock("@/lib/stores/airplaneModeStore", () => ({
  useAirplaneModeStore: () => mockAirplaneState,
}));

describe("SessionPrewarmer", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
    Object.assign(mockAirplaneState, {
      airplaneMode: true,
      airplaneModeReady: true,
      airplaneBackendReady: true,
      airplaneLocalModel: "qwen3.5:9b",
      airplaneModeError: null,
      setAirplaneMode: jest.fn(),
      toggleAirplaneMode: jest.fn(),
    });
    document.documentElement.setAttribute("data-mode", "light");
    global.fetch = jest.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("skips prewarm while canonical airplane status is loading", async () => {
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: false,
      airplaneBackendReady: false,
    });

    renderPrewarmer();

    await waitFor(() => expect(global.fetch).not.toHaveBeenCalled());
  });

  it("skips prewarm when airplane mode is on and local backend or configured model is not ready", async () => {
    Object.assign(mockAirplaneState, {
      airplaneMode: true,
      airplaneModeReady: true,
      airplaneBackendReady: false,
    });

    renderPrewarmer();

    await waitFor(() => expect(global.fetch).not.toHaveBeenCalled());
  });

  it("prewarms when airplane mode is off even if local backend is not ready", async () => {
    Object.assign(mockAirplaneState, {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: false,
    });

    renderPrewarmer();

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/session/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          airplaneMode: false,
          airplaneLocalModel: null,
          currentPage: "/browse/test-skill",
          themeMode: "light",
        }),
      }),
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("prewarms when airplane mode is on and local backend is ready", async () => {
    renderPrewarmer();

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/session/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          airplaneMode: true,
          airplaneLocalModel: "qwen3.5:9b",
          currentPage: "/browse/test-skill",
          themeMode: "light",
        }),
      }),
    );
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("prewarms after airplane mode backend transitions from not ready to ready", async () => {
    Object.assign(mockAirplaneState, {
      airplaneMode: true,
      airplaneModeReady: true,
      airplaneBackendReady: false,
    });
    const { rerender } = renderPrewarmer();

    await waitFor(() => expect(global.fetch).not.toHaveBeenCalled());

    Object.assign(mockAirplaneState, {
      airplaneBackendReady: true,
    });
    rerender(<SessionPrewarmer />);

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(global.fetch).toHaveBeenLastCalledWith("/api/session/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        airplaneMode: true,
        airplaneLocalModel: "qwen3.5:9b",
        currentPage: "/browse/test-skill",
        themeMode: "light",
      }),
    });
  });

  it("prewarms again when airplane mode stays on but the configured local model changes", async () => {
    const { rerender } = renderPrewarmer();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    Object.assign(mockAirplaneState, {
      airplaneLocalModel: "llama3.2:3b",
    });
    rerender(<SessionPrewarmer />);

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(global.fetch).toHaveBeenLastCalledWith("/api/session/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        airplaneMode: true,
        airplaneLocalModel: "llama3.2:3b",
        currentPage: "/browse/test-skill",
        themeMode: "light",
      }),
    });
  });

  it("does not surface prewarm failures", async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error("offline"));

    renderPrewarmer();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  });
});
