/**
 * @jest-environment node
 */
import { describe, it, expect } from "@jest/globals";
import {
  BROWSE_CATEGORIES,
  JOURNEY_GROUP_ORDER,
  JOURNEY_GROUP_LABELS,
} from "@/lib/browse/types";

const DEV_GROUPS = ["capabilities", "diagnostics", "reference"];

describe("developer-tier category grouping", () => {
  it("places every devOnly category in exactly one of the 3 dev groups", () => {
    for (const category of BROWSE_CATEGORIES.filter((c) => c.devOnly)) {
      expect(DEV_GROUPS).toContain(category.journey_group);
    }
  });

  it("matches the ratified group membership", () => {
    const byGroup: Record<string, string[]> = {};
    for (const category of BROWSE_CATEGORIES.filter((c) => c.devOnly)) {
      (byGroup[category.journey_group] ??= []).push(category.id);
    }
    // commands/agent-profiles/background-routines promoted out of the dev
    // tier by the three-concept regroup (spec 2026-06-09 §3 amended 2026-06-11).
    expect(new Set(byGroup.capabilities)).toEqual(
      new Set(["mcp-tools", "scripts", "api-routes", "tests"]),
    );
    expect(new Set(byGroup.diagnostics)).toEqual(
      new Set(["mcp-servers", "logs", "system-metadata"]),
    );
    expect(new Set(byGroup.reference)).toEqual(new Set(["adrs"]));
  });

  it("retires the legacy dev journey groups and labels the new ones", () => {
    for (const legacy of [
      "intent", "wiring", "orchestration",
      "incoming", "knowledge", "reuse", "system", "state",
    ]) {
      expect(JOURNEY_GROUP_ORDER).not.toContain(legacy);
    }
    for (const group of DEV_GROUPS) {
      expect(JOURNEY_GROUP_ORDER).toContain(group);
      expect((JOURNEY_GROUP_LABELS as Record<string, string>)[group]).toBeTruthy();
    }
  });
});
