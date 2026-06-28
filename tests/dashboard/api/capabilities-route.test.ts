/**
 * @jest-environment node
 */
import { describe, it, expect, jest, beforeEach } from "@jest/globals";

const mockCall = jest.fn();

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: (...a: unknown[]) => mockCall(...a),
  MCPBridge: class {
    static parseJSON(result: { content?: Array<{ text: string }> }) {
      const text = result.content?.[0]?.text ?? "{}";
      return JSON.parse(text);
    }
  },
}));

// Mock server-side dependencies so no filesystem access is needed
jest.mock("@/lib/server/skillsState", () => ({
  readDisabledSkills: jest.fn().mockResolvedValue(new Set()),
}));

jest.mock("@/lib/server/skillsScanning", () => ({
  buildSkillPathMap: jest.fn().mockResolvedValue(new Map([["wiki", "/fake/skills/wiki"]])),
  collectSkillSubdir: jest.fn().mockResolvedValue([]),
}));

jest.mock("@/lib/server/repo", () => ({
  getRepoRoot: jest.fn().mockReturnValue("/fake/repo"),
}));

jest.mock("@/lib/server/skillSlug", () => ({
  normalizeSkillSlug: jest.fn((s: string) => s.toLowerCase()),
  promptSlugFromTrigger: jest.fn((t: string) => t.toLowerCase().replace(/\s+/g, "-")),
}));

describe("GET /api/mcp/capabilities sources skills via MCP, not CLI", () => {
  beforeEach(() => mockCall.mockReset());

  it("maps list-skills MCP output into the capabilities response", async () => {
    mockCall.mockResolvedValue({
      isError: false,
      content: [
        {
          type: "text",
          text: JSON.stringify({
            skills: [{ name: "wiki", display_name: "Wiki", description: "d", triggers: ["t"] }],
          }),
        },
      ],
    });
    const { GET } = await import("@/app/api/mcp/capabilities/route");
    const res = await GET();
    const body = await res.json();
    // the MCP tool was called (no CLI spawn path)
    expect(mockCall).toHaveBeenCalledWith("list-skills", expect.anything());
    // the skill surfaced in the response
    expect(JSON.stringify(body)).toContain("wiki");
  });
});
