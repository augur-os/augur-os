import type { BrowseItem } from "@/lib/browse/types";
import {
  buildCoverageIndex,
  coverageTagFor,
  enrichItemsWithCoverage,
  normalizeToolId,
  parseReport,
  slugifySkillId,
  type ResolvableReport,
} from "@/lib/browse/skillCoverage";
import { getSkillStateTags } from "@/lib/browse/skill-card-ux";

const REPORT: ResolvableReport = {
  generated_at: "2026-05-14T03:00:00Z",
  auditor_version: "1.0",
  summary: {
    skills_scanned: 3,
    surfaces_scanned: 10,
    findings: {
      unrouted_intents: 2,
      routing_collisions: 1,
      orphaned_skills: 1,
      stale_capability_entries: 1,
    },
  },
  findings: {
    unrouted_intents: [
      { skill_id: "career", intent_phrase: "growth tracking", remediation: "wire a surface" },
      { skill_id: "career", intent_phrase: "salary review", remediation: "wire a surface" },
    ],
    routing_collisions: [
      { phrase: "search", skill_ids: ["knowledge", "scraper"], remediation: "declare ownership" },
    ],
    orphaned_skills: [
      { skill_id: "experimental-x", remediation: "wire a surface or stage it" },
    ],
    stale_capability_entries: [
      { tool_id: "mcp-tool:gone-tool", remediation: "remove from capability_exposure.yaml" },
    ],
  },
};

function skillItem(id: string, skillName?: string): BrowseItem {
  return {
    id,
    title: id,
    description: "",
    hub: "dev",
    icon: "Puzzle",
    primaryAction: { label: "View", type: "navigate", target: `/browse/${id}` },
    actions: [],
    metadata: skillName ? { skillName } : undefined,
  };
}

describe("parseReport", () => {
  it("parses a JSON string payload", () => {
    expect(parseReport(JSON.stringify(REPORT))?.summary.skills_scanned).toBe(3);
  });
  it("accepts an already-parsed object", () => {
    expect(parseReport(REPORT)?.auditor_version).toBe("1.0");
  });
  it("returns null for garbage / incomplete payloads", () => {
    expect(parseReport("not json")).toBeNull();
    expect(parseReport(null)).toBeNull();
    expect(parseReport({ summary: {} })).toBeNull();
  });
});

describe("normalizeToolId / slugifySkillId", () => {
  it("strips the capability prefix from tool ids", () => {
    expect(normalizeToolId("mcp-tool:gone-tool")).toBe("gone-tool");
    expect(normalizeToolId("gone-tool")).toBe("gone-tool");
  });
  it("slugifies skill ids the same way transforms.ts does", () => {
    expect(slugifySkillId("Auto Skill Quality")).toBe("auto-skill-quality");
    expect(slugifySkillId("evals")).toBe("evals");
  });
});

describe("buildCoverageIndex", () => {
  const index = buildCoverageIndex(REPORT);

  it("aggregates per-skill findings with a correct issue count", () => {
    const career = index.bySkill.get("career");
    expect(career?.unrouted).toHaveLength(2);
    expect(career?.orphaned).toBeNull();
    expect(career?.issueCount).toBe(2);
  });

  it("attaches a routing collision to every participating skill", () => {
    expect(index.bySkill.get("knowledge")?.collisions).toHaveLength(1);
    expect(index.bySkill.get("scraper")?.collisions).toHaveLength(1);
  });

  it("flags orphaned skills", () => {
    const orphan = index.bySkill.get("experimental-x");
    expect(orphan?.orphaned?.remediation).toContain("stage it");
    expect(orphan?.issueCount).toBe(1);
  });

  it("indexes stale capability entries by normalized tool id", () => {
    expect(index.byTool.get("gone-tool")?.remediation).toContain("capability_exposure");
  });

  it("returns an empty index for a null report", () => {
    const empty = buildCoverageIndex(null);
    expect(empty.bySkill.size).toBe(0);
    expect(empty.byTool.size).toBe(0);
  });
});

describe("coverageTagFor", () => {
  it("uses danger tone for orphaned skills", () => {
    const index = buildCoverageIndex(REPORT);
    const tag = coverageTagFor(index.bySkill.get("experimental-x")!);
    expect(tag.tone).toBe("danger");
    expect(tag.title).toContain("orphaned skill");
  });
  it("uses warning tone for unrouted-only skills", () => {
    const index = buildCoverageIndex(REPORT);
    const tag = coverageTagFor(index.bySkill.get("career")!);
    expect(tag.tone).toBe("warning");
    expect(tag.label).toBe("2 coverage issues");
  });
});

describe("enrichItemsWithCoverage", () => {
  const index = buildCoverageIndex(REPORT);

  it("writes coverage metadata onto matching skill items (skills view)", () => {
    const items = [skillItem("career", "career"), skillItem("evals", "evals")];
    const enriched = enrichItemsWithCoverage(items, index, "skills");
    expect(enriched[0].metadata?.coverageIssueCount).toBe("2");
    expect(enriched[0].metadata?.coverageTone).toBe("warning");
    // Untouched skill is returned unchanged (no coverage keys).
    expect(enriched[1].metadata?.coverageIssueCount).toBeUndefined();
  });

  it("writes a stale marker onto matching mcp-tool items (mcp-tools view)", () => {
    const items: BrowseItem[] = [
      { ...skillItem("gone-tool"), metadata: { toolId: "mcp-tool:gone-tool" } },
      skillItem("live-tool"),
    ];
    const enriched = enrichItemsWithCoverage(items, index, "mcp-tools");
    expect(enriched[0].metadata?.coverageStale).toContain("capability_exposure");
    expect(enriched[1].metadata?.coverageStale).toBeUndefined();
  });

  it("does not enrich unrelated view modes", () => {
    const items = [skillItem("career", "career")];
    expect(enrichItemsWithCoverage(items, index, "wiki")).toBe(items);
  });

  it("does not mutate the input items", () => {
    const items = [skillItem("career", "career")];
    enrichItemsWithCoverage(items, index, "skills");
    expect(items[0].metadata?.coverageIssueCount).toBeUndefined();
  });
});

describe("getSkillStateTags — coverage tag", () => {
  const index = buildCoverageIndex(REPORT);

  it("renders a coverage state tag for an enriched skill item", () => {
    const [enriched] = enrichItemsWithCoverage([skillItem("career", "career")], index, "skills");
    const tags = getSkillStateTags(enriched);
    const coverage = tags.find((t) => t.key === "coverage");
    expect(coverage).toBeDefined();
    expect(coverage?.tone).toBe("warning");
    expect(coverage?.label).toBe("2 coverage issues");
  });

  it("renders a danger coverage tag for an orphaned skill", () => {
    const [enriched] = enrichItemsWithCoverage(
      [skillItem("experimental-x", "experimental-x")],
      index,
      "skills",
    );
    const coverage = getSkillStateTags(enriched).find((t) => t.key === "coverage");
    expect(coverage?.tone).toBe("danger");
  });

  it("emits no coverage tag for a clean skill", () => {
    const tags = getSkillStateTags(skillItem("evals", "evals"));
    expect(tags.find((t) => t.key === "coverage")).toBeUndefined();
  });
});
