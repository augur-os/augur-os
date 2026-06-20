import { emitHealEvent } from "@/lib/self-heal-event";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(() => Promise.resolve({ ok: true })),
}));

describe("emitHealEvent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("routes client heal events through the registered set-config self-heal scope", () => {
    emitHealEvent({
      source: "window.onerror",
      category: "client-error",
      severity: "high",
      message: "Hydration failed",
      context: { url: "/browse" },
    });

    expect(mcpCall).toHaveBeenCalledWith("set-config", {
      scope: "self-heal-event",
      source: "window.onerror",
      category: "client-error",
      severity: "high",
      message: "Hydration failed",
      context: { url: "/browse" },
    });
  });
});
