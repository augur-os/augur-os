import { fetchFromSource } from "@/lib/plugin-schema/data-fetcher";
import { fetchMCPData } from "@/lib/plugin-schema/actions";

jest.mock("@/lib/plugin-schema/actions", () => ({
  fetchMCPData: jest.fn(),
}));

const mockedFetchMCPData = jest.mocked(fetchMCPData);

describe("fetchFromSource", () => {
  beforeEach(() => {
    mockedFetchMCPData.mockReset();
  });

  it("treats bare source strings as MCP tool names", async () => {
    mockedFetchMCPData.mockResolvedValue({ success: true, data: { netWorth: 42 } });

    const result = await fetchFromSource("finance-summary", { period: "month" });

    expect(mockedFetchMCPData).toHaveBeenCalledWith("finance-summary", { period: "month" });
    expect(result).toEqual({ success: true, data: { netWorth: 42 } });
  });

  it("keeps explicit mcp sources working", async () => {
    mockedFetchMCPData.mockResolvedValue('{"success":true,"data":[1,2,3]}');

    const result = await fetchFromSource("mcp://finance-summary");

    expect(mockedFetchMCPData).toHaveBeenCalledWith("finance-summary", {});
    expect(result).toEqual({ success: true, data: [1, 2, 3] });
  });

  it("parses MCP text envelopes returned by the bridge", async () => {
    mockedFetchMCPData.mockResolvedValue({
      content: [
        {
          type: "text",
          text: '{"success":true,"data":{"netWorth":62200,"savingsRate":73.3}}',
        },
      ],
    });

    const result = await fetchFromSource("finance-summary");

    expect(result).toEqual({
      success: true,
      data: { netWorth: 62200, savingsRate: 73.3 },
    });
  });
});
