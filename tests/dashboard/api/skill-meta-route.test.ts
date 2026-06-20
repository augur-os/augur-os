// TODO_CLEANUP: This file is 904 lines — consider splitting into smaller modules
/**
 * @jest-environment node
 */

const callMCPTool = jest.fn();

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: (...args: unknown[]) => callMCPTool(...args),
  MCPBridge: {
    extractText: jest.fn((result: { content?: Array<{ text?: string }> }) => {
      return result.content?.[0]?.text ?? "";
    }),
    parseJSON: jest.fn((result: { content?: Array<{ text?: string }> }) => {
      const text = result.content?.[0]?.text ?? "{}";
      return JSON.parse(text);
    }),
  },
}));

function textResult(payload: unknown) {
  return {
    isError: false,
    content: [{ type: "text", text: JSON.stringify(payload) }],
  };
}

describe("GET /api/skill-meta/[skillId]", () => {
  beforeEach(() => {
    jest.resetModules();
    callMCPTool.mockReset();
  });

  it("hydrates external ownership metadata from skill-status and reads external skills via auto repo", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "external-skill",
            ownership: "external",
            source: "claude-global",
            location: "/Users/test/.claude/skills/external-skill",
            upstream: {},
            description: "External skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: external-skill",
                "title: External Skill",
                "description: External skill",
                "---",
                "",
                "Skill body",
              ].join("\n"),
            }],
          };
        case "file-read":
          return textResult({ content: "" });
        case "file-list":
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({
            status: "healthy",
            lastCheck: "2026-04-08T12:00:00.000Z",
            errors24h: 0,
          });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/external-skill"), {
      params: Promise.resolve({ skillId: "external-skill" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skill.ownership).toBe("external");
    expect(body.skill.source).toBe("claude-global");
    expect(body.skill.title).toBe("External Skill");
    expect(callMCPTool).toHaveBeenCalledWith("skill-status", { name: "external-skill" });
    expect(callMCPTool).toHaveBeenCalledWith("get-skill", { skill_name: "external-skill" });
    expect(callMCPTool).toHaveBeenCalledWith("file-read", {
      path: "/Users/test/.claude/skills/external-skill/SKILL.md",
      repo: "auto",
    });
  });

  it("propagates adopted upstream update state from skill-status", async () => {
    callMCPTool.mockImplementation(async (tool: string) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "adopted-skill",
            ownership: "adopted",
            source: "augur",
            location: "/repo/project-brain/capabilities/skills/adopted-skill",
            upstream: {
              repo: "https://github.com/user/adopted-skill",
              ref: "oldcommit456",
            },
            update_available: true,
            latest_upstream_commit: "newcommit123",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: adopted-skill",
                "title: Adopted Skill",
                "description: Adopted skill",
                "ownership: adopted",
                "---",
                "",
                "Skill body",
              ].join("\n"),
            }],
          };
        case "file-read":
          return textResult({
            content: [
              "---",
              "name: adopted-skill",
              "title: Adopted Skill",
              "description: Adopted skill",
              "ownership: adopted",
              "---",
            ].join("\n"),
          });
        case "file-list":
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/adopted-skill"), {
      params: Promise.resolve({ skillId: "adopted-skill" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skill.ownership).toBe("adopted");
    expect(body.skill.updateAvailable).toBe(true);
  });

  it("propagates new-to-dashboard state from skill-status", async () => {
    callMCPTool.mockImplementation(async (tool: string) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "ingest",
            ownership: "augur",
            source: "augur",
            location: "/repo/project-brain/capabilities/skills/ingest",
            description: "Ingest skill",
            is_new_to_dashboard: true,
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: ingest",
                "title: Ingest",
                "description: Ingest skill",
                "---",
                "",
                "Skill body",
              ].join("\n"),
            }],
          };
        case "file-read":
          return textResult({
            content: [
              "---",
              "name: ingest",
              "title: Ingest",
              "description: Ingest skill",
              "---",
            ].join("\n"),
          });
        case "file-list":
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/ingest"), {
      params: Promise.resolve({ skillId: "ingest" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skill.isNewToDashboard).toBe(true);
  });

  it("returns file-based prompts and commands from structured skill directories", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "writer",
            ownership: "augur",
            source: "augur",
            location: "project-brain/capabilities/skills/writer",
            description: "Writer skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: writer",
                "title: Writer",
                'description: "Writer --- skill"',
                "---",
                "",
                "Skill body",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/writer/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: writer",
                "title: Writer",
                'description: "Writer --- skill"',
                "---",
                "",
                "Skill body",
              ].join("\n"),
            });
          }
          if (args.path === "project-brain/capabilities/skills/writer/prompts/draft.md") {
            return textResult({
              content: [
                "---",
                "id: draft-reply",
                "label: Draft Reply",
                'description: "Draft --- a concise reply"',
                "icon: Mail",
                "---",
                "Write a concise reply using thread context.",
                "",
              ].join("\n"),
            });
          }
          if (args.path === "project-brain/capabilities/skills/writer/commands/plan-day.md") {
            return textResult({
              content: [
                "---",
                "description: Plan the day",
                "---",
                "Use calendar and task context to plan the day.",
                "",
              ].join("\n"),
            });
          }
          return textResult({ content: "" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills/writer/prompts") {
            return textResult({
              entries: [{ type: "file", name: "draft.md" }],
            });
          }
          if (args.path === "project-brain/capabilities/skills/writer/commands") {
            return textResult({
              entries: [{ type: "file", name: "plan-day.md" }],
            });
          }
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/writer"), {
      params: Promise.resolve({ skillId: "writer" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skill.title).toBe("Writer");
    expect(body.prompts).toEqual([
      {
        id: "draft-reply",
        label: "Draft Reply",
        description: "Draft --- a concise reply",
        icon: "Mail",
        prompt: "Write a concise reply using thread context.\n",
      },
    ]);
    expect(body.commands).toEqual([
      {
        id: "plan-day",
        label: "Plan Day",
        description: "Plan the day",
        icon: undefined,
        command: "/plan-day",
      },
    ]);
    expect(callMCPTool).toHaveBeenCalledWith("file-list", expect.objectContaining({
      path: "project-brain/capabilities/skills/writer/prompts",
      repo: "code",
      pattern: "*.md",
    }));
    expect(callMCPTool).toHaveBeenCalledWith("file-list", expect.objectContaining({
      path: "project-brain/capabilities/skills/writer/commands",
      repo: "code",
      pattern: "*.md",
    }));
  });

  it("does not fall back to pre-move repo-root skill files when project-brain has no skill path", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "root-only",
            ownership: "augur",
            source: "augur",
            description: "Root-only skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: root-only",
                "title: Root Only",
                "description: Root-only skill",
                "---",
                "",
                "Runtime markdown without path JSON.",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/root-only/SKILL.md") {
            return textResult({ status: "error", error: "missing" });
          }
          if (args.path === "skills/root-only/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: root-only",
                "title: Root Only",
                "description: Root-only skill",
                "x-augur-hub: dev",
                "---",
                "",
                "Root body",
              ].join("\n"),
            });
          }
          if (args.path === "skills/root-only/prompts/root-prompt.md") {
            return textResult({
              content: [
                "---",
                "label: Root Prompt",
                "---",
                "Use root skill prompt content during transition.",
                "",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills") {
            return textResult({ entries: [] });
          }
          if (args.path === "skills") {
            return textResult({
              entries: [{ type: "directory", name: "root-only" }],
            });
          }
          if (args.path === "skills/root-only/prompts") {
            return textResult({
              entries: [{ type: "file", name: "root-prompt.md" }],
            });
          }
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/root-only"), {
      params: Promise.resolve({ skillId: "root-only" }),
    });
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.error).toContain("Skill 'root-only' not found");
    expect(callMCPTool).toHaveBeenCalledWith("file-read", {
      path: "project-brain/capabilities/skills/root-only/SKILL.md",
      repo: "code",
    });
    expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
      path: "skills/root-only/SKILL.md",
      repo: "code",
    });
    expect(callMCPTool).not.toHaveBeenCalledWith("file-list", expect.objectContaining({
      path: "skills/root-only/prompts",
      repo: "code",
      pattern: "*.md",
    }));
    expect(callMCPTool).not.toHaveBeenCalledWith("file-list", expect.objectContaining({
      path: "dev/root-only",
      repo: "data",
      pattern: "*.md",
    }));
    expect(callMCPTool).not.toHaveBeenCalledWith("file-list", expect.objectContaining({
      path: "project-brain/root-only",
      repo: "data",
    }));
  });

  it("does not fall back to repo-root skills once project-brain has dashboard skills", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "root-only",
            ownership: "augur",
            source: "augur",
            description: "Root-only skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: root-only",
                "title: Runtime Root Only",
                "---",
                "",
                "Runtime markdown without path JSON.",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/root-only/SKILL.md") {
            return textResult({ status: "error", error: "missing" });
          }
          if (args.path === "project-brain/capabilities/skills/shared-existing/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: shared-existing",
                "x-augur-hub: workspace",
                "---",
                "",
              ].join("\n"),
            });
          }
          if (args.path === "skills/root-only/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: root-only",
                "title: Root Only",
                "x-augur-hub: dev",
                "---",
                "",
                "Root body",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills") {
            return textResult({
              entries: [{ type: "directory", name: "shared-existing" }],
            });
          }
          if (args.path === "skills") {
            return textResult({
              entries: [{ type: "directory", name: "root-only" }],
            });
          }
          return textResult({ entries: [] });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/root-only"), {
      params: Promise.resolve({ skillId: "root-only" }),
    });

    expect(res.status).toBe(404);
    expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
      path: "skills/root-only/SKILL.md",
      repo: "code",
    });
  });

  it("rejects pre-move repo-root paths returned by get-skill once project-brain has dashboard skills", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "root-only",
            ownership: "augur",
            source: "augur",
            description: "Root-only skill",
          });
        case "get-skill":
          return textResult({
            skill_dir: "skills/root-only",
          });
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/root-only/SKILL.md") {
            return textResult({ status: "error", error: "missing" });
          }
          if (args.path === "project-brain/capabilities/skills/shared-existing/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: shared-existing",
                "x-augur-hub: workspace",
                "---",
                "",
              ].join("\n"),
            });
          }
          if (args.path === "skills/root-only/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: root-only",
                "title: Root Only",
                "x-augur-hub: dev",
                "---",
                "",
                "Root body",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills") {
            return textResult({
              entries: [{ type: "directory", name: "shared-existing" }],
            });
          }
          if (args.path === "skills") {
            return textResult({
              entries: [{ type: "directory", name: "root-only" }],
            });
          }
          return textResult({ entries: [] });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/root-only"), {
      params: Promise.resolve({ skillId: "root-only" }),
    });

    expect(res.status).toBe(404);
    expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
      path: "skills/root-only/SKILL.md",
      repo: "code",
    });
  });

  it("rejects pre-move repo-root paths returned by skill-status once project-brain has dashboard skills", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "root-only",
            ownership: "augur",
            source: "augur",
            location: "skills/root-only",
            description: "Root-only skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: root-only",
                "title: Runtime Root Only",
                "---",
                "",
                "Runtime markdown without path JSON.",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/root-only/SKILL.md") {
            return textResult({ status: "error", error: "missing" });
          }
          if (args.path === "project-brain/capabilities/skills/shared-existing/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: shared-existing",
                "x-augur-hub: workspace",
                "---",
                "",
              ].join("\n"),
            });
          }
          if (args.path === "skills/root-only/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: root-only",
                "title: Root Only",
                "x-augur-hub: dev",
                "---",
                "",
                "Root body",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills") {
            return textResult({
              entries: [{ type: "directory", name: "shared-existing" }],
            });
          }
          if (args.path === "skills") {
            return textResult({
              entries: [{ type: "directory", name: "root-only" }],
            });
          }
          return textResult({ entries: [] });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/root-only"), {
      params: Promise.resolve({ skillId: "root-only" }),
    });

    expect(res.status).toBe(404);
    expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
      path: "skills/root-only/SKILL.md",
      repo: "code",
    });
  });

  it("accepts private-vault skill-status paths while rejecting stale repo-root paths after project-brain is populated", async () => {
    let locationMode: "private-vault" | "repo-root" = "private-vault";
    const originalAugurRoot = process.env.AUGUR_ROOT;
    process.env.AUGUR_ROOT = "/Users/test/Projects/Augur";

    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "apple",
            ownership: "augur",
            source: locationMode === "private-vault" ? "private-vault" : "augur",
            location: locationMode === "private-vault"
              ? "/Users/test/Projects/Au-vault/skills/apple"
              : "/Users/test/Projects/Augur/skills/apple",
            description: "Apple skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: apple",
                "title: Runtime Apple",
                "---",
                "",
                "Runtime markdown without path JSON.",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/apple/SKILL.md") {
            return textResult({ status: "error", error: "missing" });
          }
          if (args.path === "project-brain/capabilities/skills/shared-existing/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: shared-existing",
                "x-augur-hub: workspace",
                "---",
                "",
              ].join("\n"),
            });
          }
          if (args.path === "/Users/test/Projects/Au-vault/skills/apple/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: apple",
                "title: Apple",
                "x-augur-hub: life",
                "---",
                "",
                "Private vault body",
              ].join("\n"),
            });
          }
          if (args.path === "/Users/test/Projects/Augur/skills/apple/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: apple",
                "title: Stale Apple",
                "x-augur-hub: dev",
                "---",
                "",
                "Stale repo-root body",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          if (args.path === "project-brain/capabilities/skills") {
            return textResult({
              entries: [{ type: "directory", name: "shared-existing" }],
            });
          }
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    try {
      const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
      let res = await GET(new Request("http://localhost/api/skill-meta/apple"), {
        params: Promise.resolve({ skillId: "apple" }),
      });
      let body = await res.json();

      expect(res.status).toBe(200);
      expect(body.skill.title).toBe("Apple");
      expect(body.skill.source).toBe("private-vault");
      expect(body.skillDoc.skillDoc).toContain("Private vault body");
      expect(callMCPTool).toHaveBeenCalledWith("file-read", {
        path: "/Users/test/Projects/Au-vault/skills/apple/SKILL.md",
        repo: "auto",
      });

      locationMode = "repo-root";
      callMCPTool.mockClear();

      res = await GET(new Request("http://localhost/api/skill-meta/apple"), {
        params: Promise.resolve({ skillId: "apple" }),
      });
      body = await res.json();

      expect(res.status).toBe(404);
      expect(body.error).toContain("Skill 'apple' not found");
      expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
        path: "/Users/test/Projects/Augur/skills/apple/SKILL.md",
        repo: "auto",
      });
    } finally {
      if (originalAugurRoot === undefined) {
        delete process.env.AUGUR_ROOT;
      } else {
        process.env.AUGUR_ROOT = originalAugurRoot;
      }
    }
  });

  it("keeps project-brain fallback ahead of pre-move repo-root skills", async () => {
    callMCPTool.mockImplementation(async (tool: string, args: Record<string, unknown>) => {
      switch (tool) {
        case "skill-status":
          return textResult({
            name: "dual-skill",
            ownership: "augur",
            source: "augur",
            description: "Dual skill",
          });
        case "get-skill":
          return {
            isError: false,
            content: [{
              type: "text",
              text: [
                "---",
                "name: dual-skill",
                "title: Runtime Dual",
                "---",
                "",
                "Runtime markdown without path JSON.",
              ].join("\n"),
            }],
          };
        case "file-read":
          if (args.path === "project-brain/capabilities/skills/dual-skill/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: dual-skill",
                "title: Shared Dual",
                "description: Shared skill",
                "---",
                "",
                "Shared body",
              ].join("\n"),
            });
          }
          if (args.path === "skills/dual-skill/SKILL.md") {
            return textResult({
              content: [
                "---",
                "name: dual-skill",
                "title: Root Dual",
                "---",
                "",
                "Root body",
              ].join("\n"),
            });
          }
          return textResult({ status: "error", error: "missing" });
        case "file-list":
          return textResult({ entries: [] });
        case "get-skill-health":
          return textResult({ status: "healthy" });
        default:
          return textResult({});
      }
    });

    const { GET } = await import("@/app/api/skill-meta/[skillId]/route");
    const res = await GET(new Request("http://localhost/api/skill-meta/dual-skill"), {
      params: Promise.resolve({ skillId: "dual-skill" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.skill.title).toBe("Shared Dual");
    expect(body.skillDoc.skillDoc).toContain("Shared body");
    expect(callMCPTool).not.toHaveBeenCalledWith("file-read", {
      path: "skills/dual-skill/SKILL.md",
      repo: "code",
    });
  });
});
