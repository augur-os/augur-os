/**
 * @jest-environment node
 */

import { GET } from "@/app/api/activity/summary/route";

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    isError: false,
    content: [
      {
        type: "text",
        text: JSON.stringify({
          focus: null,
          workflows: [],
          assets: [],
          pages: [],
          dev: { branch: "main", last_commit: "fix", commit_time: "1m ago" },
        }),
      },
    ],
  }),
  extractContextFromRequest: jest.fn().mockReturnValue({ clientId: "test" }),
  MCPBridge: {
    extractText: jest.fn(
      (r: { content?: Array<{ type?: string; text?: string }> }) =>
        r.content?.[0]?.text ?? "",
    ),
  },
}));

describe("GET /api/activity/summary", () => {
  it("loads the activity summary via get-settings", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/activity/summary");

    const res = await GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "get-settings",
      { scope: "activity-summary" },
      { clientId: "test" },
    );
    expect(body.dev.branch).toBe("main");
  });
});
