/**
 * @jest-environment jsdom
 */
import { renderHook, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock mcpCall at the module level
const mockMcpCall = jest.fn();
jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

import { useMcpMutation } from "@/lib/mcp/useMcpMutation";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
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

describe("useMcpMutation", () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
  });

  it("calls mcpCall with tool name and body", async () => {
    mockMcpCall.mockResolvedValue({ ok: true });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("update-settings"),
      { wrapper: Wrapper },
    );

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();

    await act(async () => {
      await result.current.mutate({ theme: "dark" });
    });

    expect(mockMcpCall).toHaveBeenCalledWith("update-settings", { theme: "dark" });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    queryClient.clear();
  });

  it("calls mcpCall with empty args when mutate() called without body", async () => {
    mockMcpCall.mockResolvedValue({ status: "done" });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("trigger-sync"),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.mutate();
    });

    expect(mockMcpCall).toHaveBeenCalledWith("trigger-sync", {});
    queryClient.clear();
  });

  it("merges staticArgs with body", async () => {
    mockMcpCall.mockResolvedValue({ saved: true });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpMutation("save-item", {
          staticArgs: { hub: "workspace", source: "test" },
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.mutate({ title: "My Note" });
    });

    expect(mockMcpCall).toHaveBeenCalledWith("save-item", {
      hub: "workspace",
      source: "test",
      title: "My Note",
    });
    queryClient.clear();
  });

  it("body overrides staticArgs on key collision", async () => {
    mockMcpCall.mockResolvedValue({ ok: true });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpMutation("update-config", {
          staticArgs: { mode: "default" },
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.mutate({ mode: "advanced" });
    });

    expect(mockMcpCall).toHaveBeenCalledWith("update-config", {
      mode: "advanced",
    });
    queryClient.clear();
  });

  it("invalidates query cache keys after success", async () => {
    mockMcpCall.mockResolvedValue({ updated: true });

    const { queryClient, Wrapper } = createWrapper();
    const invalidateSpy = jest.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () =>
        useMcpMutation("update-settings", {
          invalidates: ["settings-list", "dashboard-config"],
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.mutate({ theme: "dark" });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["settings-list"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["dashboard-config"] });
    invalidateSpy.mockRestore();
    queryClient.clear();
  });

  it("does not invalidate cache on failure", async () => {
    mockMcpCall.mockRejectedValue(new Error("MCP tool failed"));

    const { queryClient, Wrapper } = createWrapper();
    const invalidateSpy = jest.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(
      () =>
        useMcpMutation("bad-tool", {
          invalidates: ["some-key"],
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      try {
        await result.current.mutate();
      } catch {
        // expected
      }
    });

    expect(invalidateSpy).not.toHaveBeenCalled();
    invalidateSpy.mockRestore();
    queryClient.clear();
  });

  it("applies select transform to response", async () => {
    mockMcpCall.mockResolvedValue({ data: { items: [1, 2, 3] } });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpMutation<number[], Record<string, unknown>>("list-items", {
          select: (raw) => (raw as { data: { items: number[] } }).data.items,
        }),
      { wrapper: Wrapper },
    );

    let mutResult: number[] | undefined;
    await act(async () => {
      mutResult = await result.current.mutate();
    });

    expect(mutResult).toEqual([1, 2, 3]);
    queryClient.clear();
  });

  it("calls onSuccess callback after successful mutation", async () => {
    mockMcpCall.mockResolvedValue({ id: 42, status: "created" });
    const onSuccess = jest.fn();

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () =>
        useMcpMutation("create-item", {
          onSuccess,
        }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      await result.current.mutate({ name: "test" });
    });

    expect(onSuccess).toHaveBeenCalledWith({ id: 42, status: "created" });
    queryClient.clear();
  });

  it("does not call onSuccess on failure", async () => {
    mockMcpCall.mockRejectedValue(new Error("fail"));
    const onSuccess = jest.fn();

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("bad-tool", { onSuccess }),
      { wrapper: Wrapper },
    );

    await act(async () => {
      try {
        await result.current.mutate();
      } catch {
        // expected
      }
    });

    expect(onSuccess).not.toHaveBeenCalled();
    queryClient.clear();
  });

  it("sets error state on failure and re-throws", async () => {
    mockMcpCall.mockRejectedValue(new Error("Something went wrong"));

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("fail-tool"),
      { wrapper: Wrapper },
    );

    let caughtError: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutate();
      } catch (e) {
        caughtError = e as Error;
      }
    });

    expect(caughtError?.message).toBe("Something went wrong");
    expect(result.current.error).toBe("Something went wrong");
    expect(result.current.loading).toBe(false);
    queryClient.clear();
  });

  it("clears error on next successful mutation", async () => {
    mockMcpCall.mockRejectedValueOnce(new Error("first call fails"));

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("retry-tool"),
      { wrapper: Wrapper },
    );

    // First call: fails
    await act(async () => {
      try {
        await result.current.mutate();
      } catch {
        // expected
      }
    });
    expect(result.current.error).toBe("first call fails");

    // Second call: succeeds
    mockMcpCall.mockResolvedValueOnce({ ok: true });
    await act(async () => {
      await result.current.mutate();
    });

    expect(result.current.error).toBeNull();
    queryClient.clear();
  });

  it("returns the final result from mutate()", async () => {
    mockMcpCall.mockResolvedValue({ id: 99 });

    const { queryClient, Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useMcpMutation("create-thing"),
      { wrapper: Wrapper },
    );

    let returned: unknown;
    await act(async () => {
      returned = await result.current.mutate({ name: "thing" });
    });

    expect(returned).toEqual({ id: 99 });
    queryClient.clear();
  });
});
