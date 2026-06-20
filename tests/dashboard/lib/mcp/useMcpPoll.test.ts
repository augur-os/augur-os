/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock mcpCall at the module level
const mockMcpCall = jest.fn();
jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

import { useMcpPoll } from "@/lib/mcp/useMcpPoll";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return { queryClient, Wrapper };

  function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  }
}

describe("useMcpPoll", () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("polls mcpCall with tool name and args", async () => {
    mockMcpCall.mockResolvedValue({ temperature: 22 });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpPoll("temp-sensor", "get-temperature", 5000, {
          args: { sensorId: "living-room" },
          preset: "device",
        }),
      { wrapper: Wrapper },
    );

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockMcpCall).toHaveBeenCalledWith(
      "get-temperature",
      { sensorId: "living-room" },
    );
    expect(result.current.data).toEqual({ temperature: 22 });
    expect(result.current.error).toBeNull();

    queryClient.clear();
  });

  it("applies select transform to response", async () => {
    mockMcpCall.mockResolvedValue({ data: { items: ["a", "b", "c"] } });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpPoll<string[]>("items-poll", "list-items", 10000, {
          select: (raw) => (raw as { data: { items: string[] } }).data.items,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(["a", "b", "c"]);
    expect(result.current.error).toBeNull();

    queryClient.clear();
  });

  it("surfaces error message on mcpCall failure", async () => {
    mockMcpCall.mockRejectedValue(new Error("Sensor offline"));

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpPoll("broken-sensor", "get-status", 5000),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Sensor offline");
    expect(result.current.data).toBeNull();

    queryClient.clear();
  });

  it("does not fetch when enabled is false", async () => {
    mockMcpCall.mockResolvedValue({ ok: true });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpPoll("disabled-poll", "some-tool", 5000, {
          enabled: false,
        }),
      { wrapper: Wrapper },
    );

    // Give it a tick to ensure nothing fires
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockMcpCall).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();

    queryClient.clear();
  });

  it("supports manual refetch", async () => {
    mockMcpCall
      .mockResolvedValueOnce({ value: 1 })
      .mockResolvedValueOnce({ value: 2 });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpPoll("manual-refresh", "get-manual-refresh", 60_000),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.data).toEqual({ value: 1 });

    await act(async () => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data).toEqual({ value: 2 });
    });
    expect(mockMcpCall).toHaveBeenCalledTimes(2);

    queryClient.clear();
  });
});
