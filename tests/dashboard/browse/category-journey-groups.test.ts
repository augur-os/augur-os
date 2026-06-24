/**
 * @jest-environment node
 */
import { describe, it, expect } from "@jest/globals";
import {
  BROWSE_CATEGORIES,
  JOURNEY_GROUP_ORDER,
  JOURNEY_GROUP_LABELS,
} from "@/lib/browse/types";

const DEV_GROUPS = ["loop", "capabilities", "diagnostics", "reference"];

describe("developer-tier category grouping", () => {
  it("places every devOnly category in exactly one of the 4 journey groups", () => {
    for (const category of BROWSE_CATEGORIES.filter((c) => c.devOnly)) {
      expect(DEV_GROUPS).toContain(category.journey_group);
    }
  });

  it("matches the ratified group membership", () => {
    const byGroup: Record<string, string[]> = {};
    for (const category of BROWSE_CATEGORIES.filter((c) => c.devOnly)) {
      (byGroup[category.journey_group] ??= []).push(category.id);
    }
    // mcp-tools/mcp-servers moved into the loop group as full loop anatomy
    // (task-1 regroup 2026-06-23).
    expect(new Set(byGroup.loop)).toEqual(
      new Set(["mcp-tools", "mcp-servers"]),
    );
    expect(new Set(byGroup.capabilities)).toEqual(
      new Set(["scripts", "api-routes", "tests"]),
    );
    expect(new Set(byGroup.diagnostics)).toEqual(
      new Set(["logs", "system-metadata"]),
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
