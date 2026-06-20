import {
  __resetBestEffortQueueForTests,
  enqueueBestEffortJson,
} from "@/lib/bestEffortQueue";

describe("bestEffortQueue", () => {
  const originalFetch = global.fetch;
  const originalNavigator = global.navigator;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.useFakeTimers();
    mockFetch = jest.fn().mockResolvedValue({ ok: true });
    global.fetch = mockFetch as unknown as typeof fetch;
    Object.defineProperty(global, "navigator", {
      value: { onLine: true },
      configurable: true,
    });
    __resetBestEffortQueueForTests();
  });

  afterEach(() => {
    jest.useRealTimers();
    global.fetch = originalFetch;
    Object.defineProperty(global, "navigator", {
      value: originalNavigator,
      configurable: true,
    });
  });

  it("batches background posts behind a delayed queue", async () => {
    enqueueBestEffortJson("/api/telemetry/performance", { metric: "load" }, { delayMs: 100 });
    enqueueBestEffortJson("/api/usage/track", { page: "/brain" }, { delayMs: 100 });

    expect(mockFetch).not.toHaveBeenCalled();

    await jest.advanceTimersByTimeAsync(100);
    await Promise.resolve();

    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      "/api/telemetry/performance",
      expect.objectContaining({ method: "POST", keepalive: true }),
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      "/api/usage/track",
      expect.objectContaining({ method: "POST", keepalive: true }),
    );
  });

  it("drops background posts when offline", () => {
    Object.defineProperty(global, "navigator", {
      value: { onLine: false },
      configurable: true,
    });

    enqueueBestEffortJson("/api/usage/track", { page: "/brain" });

    jest.advanceTimersByTime(5000);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
