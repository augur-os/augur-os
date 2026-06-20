/**
 * @jest-environment node
 */

import { NextRequest } from "next/server";
import { GET } from "@/app/api/settings/layout/pulse/route";

const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe("/api/settings/layout/pulse", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
    });
  });

  it("probes the live activity summary route in quick mode", async () => {
    await GET(new NextRequest("http://localhost/api/settings/layout/pulse?mode=quick"));

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost/api/activity/summary",
      expect.objectContaining({
        cache: "no-store",
        method: "GET",
      }),
    );
  });

  it("probes the agent availability route in deep mode", async () => {
    await GET(new NextRequest("http://localhost/api/settings/layout/pulse?mode=deep"));

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost/api/agents/available?mode=api",
      expect.objectContaining({
        cache: "no-store",
        method: "GET",
      }),
    );
  });

  it("uses the same core probes for quick mode", async () => {
    await GET(
      new NextRequest("http://localhost/api/settings/layout/pulse?mode=quick"),
    );

    expect(mockFetch.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost/api/activity/summary",
      "http://localhost/api/agents/available?mode=api",
    ]);
  });
});
