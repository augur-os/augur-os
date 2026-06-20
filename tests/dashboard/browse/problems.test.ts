import {
  buildProblemFilterOptions,
  buildProblemPrompt,
  hasInventoryProblemMetadata,
  itemMatchesProblemFilter,
  problemBadgesForItem,
  problemDetailRowsForItem,
} from "@/lib/browse/problems";
import type { BrowseItem } from "@/lib/browse/types";

function item(metadata: Record<string, string>): BrowseItem {
  return {
    id: "artifact-1",
    title: "Codex agent",
    description: "agent profile",
    hub: "system",
    typeBadge: "agent-profile",
    path: "/repo/.codex/agents/dev.md",
    primaryAction: { label: "Open", type: "open-file", target: "/repo/.codex/agents/dev.md" },
    metadata,
  };
}

describe("browse problem helpers", () => {
  it("parses tags into badges, details, filters, and chat prompt text", () => {
    const artifact = item({
      problem_tags: "unknown_source,missing_mcp_config",
      problem_count: "2",
      problem_summary: "Unknown source",
      problem_evidence:
        '[{"id":"unknown_source","severity":"warning","reason":"Scanner warning: unknown_source","source_path":"/repo/.codex/agents/dev.md"}]',
      brain_id: "project-demo",
      project_root: "/repo",
      artifact_type: "agent-profile",
      client: "codex",
      vendor: "openai",
    });

    expect(problemBadgesForItem(artifact).map((badge) => badge.label)).toEqual([
      "Unknown source",
      "Missing MCP config",
    ]);
    expect(problemBadgesForItem(artifact)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "problem-unknown_source", tone: "warning" }),
        expect.objectContaining({ id: "problem-missing_mcp_config", tone: "info" }),
      ]),
    );
    expect(problemDetailRowsForItem(artifact)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "Unknown source", value: expect.stringContaining("Scanner warning") }),
      ]),
    );
    expect(buildProblemFilterOptions([artifact])).toEqual([
      { id: "unknown_source", label: "Unknown source (1)" },
      { id: "missing_mcp_config", label: "Missing MCP config (1)" },
    ]);
    expect(itemMatchesProblemFilter(artifact, "missing_mcp_config")).toBe(true);
    expect(buildProblemPrompt(artifact)).toContain(
      "Do not modify, adopt, sync, rewrite, delete, or project files until I approve.",
    );
  });

  it("humanizes unknown future problem ids and falls back when evidence json is invalid", () => {
    const artifact = item({
      problem_tags: "future_problem",
      problem_evidence: "not json",
    });

    expect(problemBadgesForItem(artifact)).toEqual([
      expect.objectContaining({ id: "problem-future_problem", label: "Future problem" }),
    ]);
    expect(problemDetailRowsForItem(artifact)).toEqual([
      expect.objectContaining({ label: "Future problem" }),
    ]);
    expect(buildProblemFilterOptions([artifact])).toEqual([
      { id: "future_problem", label: "Future problem (1)" },
    ]);
  });

  it("falls back to a safe badge tone when evidence severity is invalid", () => {
    const artifact = item({
      problem_tags: "unknown_source",
      problem_evidence: '[{"id":"unknown_source","severity":"critical","reason":"Malformed severity"}]',
    });

    expect(problemBadgesForItem(artifact)).toEqual([
      expect.objectContaining({ id: "problem-unknown_source", tone: "warning" }),
    ]);
  });

  it("requires problem tags and inventory artifact signals for inventory problem metadata", () => {
    expect(hasInventoryProblemMetadata(item({ problem_tags: "unknown_source" }))).toBe(false);
    expect(hasInventoryProblemMetadata(item({
      problem_tags: "unknown_source",
      inventory_source: "ai-artifact-inventory",
    }))).toBe(true);
    expect(hasInventoryProblemMetadata(item({
      problem_tags: "unknown_source",
      artifact_type: "agent-profile",
      client: "codex",
      source_path: "/repo/.codex/agents/dev.md",
    }))).toBe(true);
  });

  it("includes problem tags that do not have evidence rows in the prompt", () => {
    const prompt = buildProblemPrompt(item({
      problem_tags: "unknown_source,missing_mcp_config",
      problem_evidence:
        '[{"id":"unknown_source","severity":"warning","reason":"Scanner warning: unknown_source"}]',
    }));

    expect(prompt).toContain("Unknown source");
    expect(prompt).toContain("Missing MCP config");
  });
});
