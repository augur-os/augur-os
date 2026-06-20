import {
  buildBrainFilterOptions,
  itemMatchesBrainFilter,
  type BrainDiscoveryLite,
} from "@/lib/browse/brainFilters";

const discovery: BrainDiscoveryLite = {
  active: { brain_id: "personal" },
  current_project: { registered_brain_id: "project-augur" },
  brains: [
    { id: "personal", type: "personal", description: "Personal brain", root: "/vault" },
    { id: "project-augur", type: "project", description: "Augur project brain", root: "/repo/augur/project-brain" },
    { id: "project-client", type: "project", description: "Client project brain", root: "/repo/client/project-brain" },
    { id: "team-core", type: "team", description: "Team core", root: "/team" },
  ],
};

const items = [
  { id: "g", title: "Global", description: "", hub: "system", metadata: {}, primaryAction: { label: "Open", type: "open-file" as const, target: "" } },
  { id: "p", title: "Personal", description: "", hub: "workspace", metadata: { brain_id: "personal" }, primaryAction: { label: "Open", type: "open-file" as const, target: "" } },
  { id: "a", title: "Augur", description: "", hub: "system", metadata: { brain_id: "project-augur" }, primaryAction: { label: "Open", type: "open-file" as const, target: "" } },
  { id: "c", title: "Client", description: "", hub: "system", metadata: { brain_id: "project-client" }, primaryAction: { label: "Open", type: "open-file" as const, target: "" } },
  { id: "t", title: "Team", description: "", hub: "system", metadata: { brain_id: "team-core" }, primaryAction: { label: "Open", type: "open-file" as const, target: "" } },
];

describe("Browse brain filters", () => {
  it("builds all/global/current/all-projects/named project options", () => {
    const options = buildBrainFilterOptions(items, discovery);

    expect(options.map((option) => option.id)).toEqual([
      "all",
      "global",
      "personal",
      "current-project",
      "all-projects",
      "team",
      "project:project-augur",
      "project:project-client",
    ]);
    expect(options.find((option) => option.id === "global")?.label).toBe("Global (1)");
    expect(options.find((option) => option.id === "all-projects")?.label).toBe("All projects (2)");
    expect(options.find((option) => option.id === "project:project-client")?.label).toBe("Client (1)");
  });

  it("matches current project, all projects, and named project filters", () => {
    expect(itemMatchesBrainFilter(items[0], "global", discovery)).toBe(true);
    expect(itemMatchesBrainFilter(items[1], "global", discovery)).toBe(false);
    expect(itemMatchesBrainFilter(items[2], "all-projects", discovery)).toBe(true);
    expect(itemMatchesBrainFilter(items[2], "current-project", discovery)).toBe(true);
    expect(itemMatchesBrainFilter(items[3], "current-project", discovery)).toBe(false);
    expect(itemMatchesBrainFilter(items[3], "all-projects", discovery)).toBe(true);
    expect(itemMatchesBrainFilter(items[3], "project:project-client", discovery)).toBe(true);
    expect(itemMatchesBrainFilter(items[2], "project:project-client", discovery)).toBe(false);
  });
});
