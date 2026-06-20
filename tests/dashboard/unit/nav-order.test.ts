import { persistHubNavOrder, persistTabNavOrder } from "@/features/components/layout-config/nav-order";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

const mockedMcpCall = mcpCall as jest.MockedFunction<typeof mcpCall>;

describe("nav-order persistence", () => {
  beforeEach(() => {
    mockedMcpCall.mockReset();
    mockedMcpCall.mockResolvedValue({ success: true });
  });

  it("persists hub order through set-config nav-order-update", async () => {
    await persistHubNavOrder([
      { hubId: "brain", navOrder: 10 },
      { hubId: "command", navOrder: 20 },
    ]);

    expect(mockedMcpCall).toHaveBeenCalledWith("set-config", {
      scope: "nav-order-update",
      type: "hub",
      items: [
        { hubId: "brain", navOrder: 10 },
        { hubId: "command", navOrder: 20 },
      ],
    });
  });

  it("persists tab order through set-config nav-order-update", async () => {
    await persistTabNavOrder("command", [
      { pageId: "system-cleanup", skillId: "cleanup", order: 4 },
      { pageId: "sessions", order: 6, title: "Sessions", visible: true },
    ]);

    expect(mockedMcpCall).toHaveBeenCalledWith("set-config", {
      scope: "nav-order-update",
      type: "tab",
      hubId: "command",
      items: [
        { pageId: "system-cleanup", skillId: "cleanup", order: 4 },
        { pageId: "sessions", order: 6, title: "Sessions", visible: true },
      ],
    });
  });
});
