import {
  getSkillIdentityTags,
  getSkillPrimaryAction,
  getSkillSecondaryActions,
  getSkillStateTags,
  summarizeSkillInventory,
} from "@/lib/browse/skill-card-ux";
import type { BrowseItem } from "@/lib/browse/types";

function skill(overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id: "knowledge",
    title: "Knowledge",
    description: "Search and organize memory",
    icon: "Puzzle",
    primaryAction: { label: "View", type: "navigate", target: "/browse/knowledge" },
    metadata: {
      ownership: "augur",
      skillClients: "codex,gemini",
      skillType: "domain",
    },
    ...overrides,
  };
}

describe("skill-card-ux", () => {
  it("separates identity tags from operational state tags", () => {
    const item = skill({
      metadata: {
        ownership: "adopted",
        skillClients: "codex,gemini",
        skillType: "domain",
        enabled: "true",
        qualityTier: "A",
        qualityScore: "82",
        mcpToolCount: "5",
        actionCount: "3",
      },
    });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual([
      "Adopted",
      "Codex",
      "Gemini",
      "domain",
    ]);
    expect(getSkillStateTags(item).map((tag) => tag.label)).toEqual([
      "enabled",
      "Quality A 82",
      "5 tools",
      "3 actions",
    ]);
  });

  it("includes updateAvailable and page-count in state tags", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        updateAvailable: "true",
        pageCount: "2",
      },
    });

    expect(getSkillStateTags(item).map((tag) => tag.label)).toEqual([
      "update available",
      "2 pages",
    ]);
  });

  it("shows disabled state tag", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        enabled: "false",
      },
    });

    expect(getSkillStateTags(item).map((tag) => tag.label)).toEqual(["disabled"]);
  });

  it("includes zero quality scores in quality tags", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        qualityTier: "B",
        qualityScore: "0",
      },
    });

    expect(getSkillStateTags(item).map((tag) => tag.label)).toEqual(["Quality B 0"]);
    expect(getSkillPrimaryAction(item)).toMatchObject({ label: "Improve" });
  });

  it("uses masterClient and caps identity clients at 3", () => {
    const explicit = skill({
      metadata: {
        ownership: "augur",
        masterClient: "codex",
        skillType: "domain",
      },
    });

    const capped = skill({
      metadata: {
        ownership: "augur",
        skillClients: "codex,gemini,cursor,copilot,opencode",
        skillType: "domain",
      },
    });

    expect(getSkillIdentityTags(explicit).map((tag) => tag.label)).toEqual(["Managed", "Codex", "domain"]);
    expect(getSkillIdentityTags(capped).map((tag) => tag.label)).toEqual([
      "Managed",
      "Codex",
      "Gemini",
      "Cursor",
      "domain",
    ]);
  });

  it("coalesces client aliases that render as the same display client", () => {
    const item = skill({
      metadata: {
        ownership: "external",
        skillClients: "claude-plugin,claude,codex",
        skillType: "workflow",
      },
    });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual([
      "External",
      "Claude",
      "Codex",
      "workflow",
    ]);
    expect(getSkillIdentityTags(item).map((tag) => tag.key)).toEqual([
      "ownership",
      "client-claude-plugin",
      "client-codex",
      "skill-type",
    ]);
  });

  it("omits unknown ownership placeholders from identity tags", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        skillClients: "unknown",
        masterClient: "unknown",
        skillType: "unknown",
      },
    });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual(["Managed"]);
  });

  it("labels private user skills separately from managed and external skills", () => {
    const item = skill({
      metadata: {
        ownership: "user",
        skillClients: "augur",
      },
    });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual([
      "User",
      "Augur",
    ]);
    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Open docs",
      type: "navigate",
      target: "/browse/knowledge",
    });
    expect(getSkillSecondaryActions(item).map((action) => action.label)).not.toContain("Adopt");
  });


  it("falls back to masterClient when skillClients only contains placeholders", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        skillClients: "unknown",
        masterClient: "codex",
        skillType: "domain",
      },
    });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual(["Managed", "Codex", "domain"]);
  });

  it("omits unknown tags instead of rendering placeholders", () => {
    const item = skill({ metadata: {} });

    expect(getSkillIdentityTags(item).map((tag) => tag.label)).toEqual([]);
    expect(getSkillStateTags(item)).toEqual([]);
  });

  it("prioritizes Enable for disabled skills", () => {
    const item = skill({ metadata: { ownership: "augur", enabled: "false", hasDashboardPage: "true" } });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Enable",
      type: "run-mcp",
      target: "enable-skill:knowledge",
    });
  });

  it("prioritizes Configure before external review and open actions", () => {
    const item = skill({ metadata: { ownership: "augur", needsSetup: "true", hasDashboardPage: "true" } });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Configure",
      type: "navigate",
      target: "/browse/knowledge",
    });
  });

  it("uses Review for external skills that are not adoption-ready", () => {
    const item = skill({ metadata: { ownership: "external", adoptionReady: "false" } });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Review",
      type: "navigate",
      target: "/browse/knowledge",
    });
  });

  it("uses Adopt for external adoption-ready skills", () => {
    const item = skill({ metadata: { ownership: "external", adoptionReady: "true" } });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Adopt",
      type: "run-mcp",
      target: "skill-adopt:knowledge",
    });
  });

  it("prioritizes Improve before Open for low-quality managed skills", () => {
    const item = skill({
      metadata: {
        ownership: "augur",
        qualityTier: "D",
        qualityScore: "22",
        hasDashboardPage: "true",
      },
    });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Improve",
      type: "run-action",
      target: "/harden knowledge",
    });
  });

  it("uses Open for managed skills with a dashboard page", () => {
    const item = skill({
      primaryAction: {
        label: "View",
        type: "navigate",
        target: "/browse/knowledge",
      },
      metadata: {
        ownership: "augur",
        hasDashboardPage: "true",
        dashboardPath: "/workspace/memory",
      },
    });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Open",
      type: "navigate",
      target: "/workspace/memory",
    });
  });

  it("does not advertise dashboard page actions without an explicit dashboard path", () => {
    const item = skill({
      path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      metadata: {
        ownership: "augur",
        hasDashboardPage: "true",
      },
    });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Open docs",
      target: "/browse/knowledge",
    });
    expect(getSkillSecondaryActions(item).map((action) => action.label)).not.toContain("Open dashboard page");
  });

  it("uses explicit dashboard paths for secondary dashboard page actions", () => {
    const item = skill({
      path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      metadata: {
        ownership: "augur",
        hasDashboardPage: "true",
        dashboardPath: "/workspace/memory",
      },
    });

    expect(getSkillSecondaryActions(item).find((action) => action.label === "Open dashboard page")).toMatchObject({
      type: "navigate",
      target: "/workspace/memory",
    });
  });

  it("uses Open docs for managed skills without a dashboard page", () => {
    const item = skill({ metadata: { ownership: "augur", hasDocs: "true" } });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Open docs",
      type: "navigate",
      target: "/browse/knowledge",
    });
  });

  it("builds secondary actions with managed order and flags", () => {
    const item = skill({
      path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      metadata: {
        ownership: "augur",
        hasDashboardPage: "true",
        dashboardPath: "/workspace/memory",
      },
    });

    expect(getSkillSecondaryActions(item).map((action) => action.label)).toEqual([
      "Open docs",
      "Open dashboard page",
      "Configure",
      "Improve",
      "Sync/export",
      "Reveal source file",
      "Disable",
      "Remove",
    ]);

    expect(getSkillSecondaryActions(item).find((action) => action.label === "Remove")).toMatchObject({
      variant: "danger",
    });
  });

  it("adds external Adopt as a secondary action", () => {
    const item = skill({ metadata: { ownership: "external" } });

    expect(getSkillSecondaryActions(item).map((action) => action.label)).toContain("Adopt");
  });

  it("builds a clean URL for prefixed skill:<source>:<name> ids", () => {
    // Without this, the browse card click navigated to
    // /browse/skill:external-client:geo-technical, which Next.js percent-encoded
    // into /browse/skill%3aexternal-client%3ageo-technical and rendered
    // "Skill%3aexternal Client%3ageo Technical" as the page title.
    const item = skill({
      id: "skill:external-client:geo-technical",
      metadata: {
        ownership: "external",
        adoptionReady: "false",
        skillName: "geo-technical",
        source_root: "external-client",
      },
    });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Review",
      type: "navigate",
      target: "/browse/geo-technical?source=external-client",
    });
    expect(getSkillSecondaryActions(item).find((a) => a.label === "Open docs")).toMatchObject({
      target: "/browse/geo-technical?source=external-client",
    });
  });

  it("falls back to the last colon segment when skillName metadata is absent", () => {
    const item = skill({
      id: "skill:project-brain:knowledge",
      metadata: { ownership: "augur", hasDocs: "true" },
    });

    expect(getSkillPrimaryAction(item)).toMatchObject({
      label: "Open docs",
      type: "navigate",
      target: "/browse/knowledge",
    });
  });

  it("summarizes skill inventory for the insight strip", () => {
    const items = [
      skill({ id: "a", metadata: { ownership: "augur" } }),
      skill({ id: "b", metadata: { ownership: "external" } }),
      skill({ id: "c", metadata: { ownership: "adopted", needsSetup: "true" } }),
      skill({ id: "d", metadata: { ownership: "user" } }),
    ];

    expect(summarizeSkillInventory(items)).toEqual({
      total: 4,
      augur: 1,
      external: 1,
      adopted: 1,
      user: 1,
      needsSetup: 1,
    });
  });
});
