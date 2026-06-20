import {
  BROWSE_CATEGORIES,
  JOURNEY_GROUP_LABELS,
  JOURNEY_GROUP_ORDER,
  compareBrowseCategoriesByJourney,
  partitionBrowseCategoriesByTier,
} from "@/lib/browse/types";

describe("Browse category journey metadata", () => {
  it("assigns every category to a labeled journey group", () => {
    for (const category of BROWSE_CATEGORIES) {
      expect(JOURNEY_GROUP_ORDER).toContain(category.journey_group);
      expect(JOURNEY_GROUP_LABELS[category.journey_group]).toBeTruthy();
      expect(category.journey_order).toBeGreaterThan(0);
      expect(category.label).not.toMatch(/^_/);
    }
  });

  it("orders user-visible categories by the concept journey", () => {
    const ordered = BROWSE_CATEGORIES
      .filter((category) => !category.devOnly)
      .slice()
      .sort(compareBrowseCategoriesByJourney)
      .map((category) => category.id);

    // Spec 2026-06-09 §3 (amended 2026-06-11): three AI-engineering concept
    // groups — context (what the AI knows), prompt (how you instruct it),
    // loop (how it runs without you). prompts/commands/background-routines/
    // agent-profiles promoted to user-facing tabs.
    expect(ordered).toEqual([
      "notes",
      "documents",
      "wiki",
      "pages",
      "archive",
      "prompts",
      "commands",
      "skills",
      "background-routines",
      "agent-profiles",
      "integrations",
    ]);
  });

  it("assigns user-visible categories to the three concept groups", () => {
    const grouped = BROWSE_CATEGORIES
      .filter((category) => !category.devOnly)
      .reduce<Record<string, string[]>>((groups, category) => {
        groups[category.journey_group] = groups[category.journey_group] ?? [];
        groups[category.journey_group].push(category.id);
        return groups;
      }, {});

    expect(grouped).toMatchObject({
      context: ["notes", "documents", "wiki", "pages", "archive"],
      prompt: ["prompts", "commands", "skills"],
      loop: ["background-routines", "agent-profiles", "integrations"],
    });
  });

  it("assigns every category to a tier", () => {
    for (const category of BROWSE_CATEGORIES) {
      expect(["primary", "more"]).toContain(category.tier);
    }
  });

  it("every devOnly category lives in the more tier", () => {
    // Invariant: dev-only categories must never appear in the always-visible
    // primary row. Which non-dev categories sit in primary vs more is an
    // editable policy choice; this test guards the dev/primary boundary.
    const devOnlyInPrimary = BROWSE_CATEGORIES
      .filter((category) => category.devOnly && category.tier === "primary")
      .map((category) => category.id);

    expect(devOnlyInPrimary).toEqual([]);
  });

  it("promotes the concept-defining categories to user-facing primary tabs", () => {
    const byId = Object.fromEntries(BROWSE_CATEGORIES.map((c) => [c.id, c]));
    expect(byId["prompts"]).toMatchObject({
      label: "Prompts", devOnly: false, journey_group: "prompt", tier: "primary",
    });
    expect(byId["commands"]).toMatchObject({
      devOnly: false, journey_group: "prompt", tier: "primary",
    });
    expect(byId["background-routines"]).toMatchObject({
      label: "Routines", devOnly: false, journey_group: "loop", tier: "primary",
    });
    expect(byId["agent-profiles"]).toMatchObject({
      label: "Agents", singularLabel: "Agent", devOnly: false, journey_group: "loop", tier: "primary",
    });
  });

  it("partitionBrowseCategoriesByTier splits and preserves input order", () => {
    const { primary, more } = partitionBrowseCategoriesByTier(BROWSE_CATEGORIES);
    expect(primary.length + more.length).toBe(BROWSE_CATEGORIES.length);
    expect(primary.every((c) => c.tier === "primary")).toBe(true);
    expect(more.every((c) => c.tier === "more")).toBe(true);
    expect(primary.map((c) => c.id)).toEqual(
      BROWSE_CATEGORIES.filter((c) => c.tier === "primary").map((c) => c.id),
    );
  });

  it("orders dev categories by the dev lifecycle journey", () => {
    const ordered = BROWSE_CATEGORIES
      .filter((category) => category.devOnly)
      .slice()
      .sort(compareBrowseCategoriesByJourney)
      .map((category) => category.id);

    // Groups: CAPABILITIES (mcp-tools, scripts, api-routes, tests),
    // DIAGNOSTICS (mcp-servers, logs, system-metadata), REFERENCE (adrs).
    // commands/agent-profiles/background-routines promoted to user tabs
    // (spec 2026-06-09 §3 amended 2026-06-11).
    expect(ordered).toEqual([
      "mcp-tools",
      "scripts",
      "api-routes",
      "tests",
      "mcp-servers",
      "logs",
      "system-metadata",
      "adrs",
    ]);
  });
});
