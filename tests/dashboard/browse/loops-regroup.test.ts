import { BROWSE_CATEGORIES, JOURNEY_GROUP_LABELS } from "@/lib/browse/types";
import { normalizeRequestedViewMode } from "@/lib/browse/viewModeMapping";

function byGroup(group: string) {
  return BROWSE_CATEGORIES.filter((c) => c.journey_group === group)
    .sort((a, b) => a.journey_order - b.journey_order)
    .map((c) => c.id);
}

test("background-routines is renamed to loops with Loops label", () => {
  const loops = BROWSE_CATEGORIES.find((c) => c.id === "loops");
  expect(loops).toBeDefined();
  expect(loops!.label).toBe("Loops");
  expect(loops!.singularLabel).toBe("Loop");
  expect(BROWSE_CATEGORIES.find((c) => c.id === "background-routines")).toBeUndefined();
});

test("loop journey group bundles the full loop anatomy in order", () => {
  expect(byGroup("loop")).toEqual([
    "loops",
    "agent-profiles",
    "skills",
    "integrations",
    "mcp-tools",
    "mcp-servers",
  ]);
});

test("skills/mcp-tools/mcp-servers left their old groups", () => {
  expect(byGroup("prompt")).toEqual(["prompts", "commands"]);
  expect(byGroup("capabilities")).toEqual(["scripts", "api-routes", "tests"]);
  expect(byGroup("diagnostics")).toEqual(["logs", "system-metadata"]);
});

test("legacy background-routines + scheduled-executions URLs resolve to loops", () => {
  expect(normalizeRequestedViewMode("background-routines")).toBe("loops");
  expect(normalizeRequestedViewMode("scheduled-executions")).toBe("loops");
  expect(JOURNEY_GROUP_LABELS.loop).toBe("LOOP ENGINEERING");
});
