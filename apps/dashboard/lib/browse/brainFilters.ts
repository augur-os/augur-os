import type { BrowseItem } from "@/lib/browse/types";

export type BrainFilter =
  | "all"
  | "global"
  | "personal"
  | "current-project"
  | "all-projects"
  | "team"
  | `project:${string}`;

export type BrainDiscoveryBrain = {
  id: string;
  type: string;
  description?: string | null;
  label?: string | null;
  name?: string | null;
  root?: string | null;
};

export type BrainDiscoveryLite = {
  active?: { brain_id?: string | null } | null;
  current_project?: { registered_brain_id?: string | null } | null;
  brains?: BrainDiscoveryBrain[] | null;
};

export type BrainFilterOption = {
  id: BrainFilter;
  label: string;
};

type BrowseBrainItem = Pick<BrowseItem, "metadata">;

export function brainTypeById(discovery: BrainDiscoveryLite | null | undefined): Record<string, string> {
  const map: Record<string, string> = {};
  for (const brain of discovery?.brains ?? []) {
    if (brain?.id) map[brain.id] = brain.type;
  }
  return map;
}

export function itemMatchesBrainFilter(
  item: BrowseBrainItem,
  filter: BrainFilter,
  discovery: BrainDiscoveryLite | null | undefined,
): boolean {
  if (filter === "all") return true;

  const brainId = itemBrainId(item);
  if (filter === "global") return !brainId;
  if (!brainId) return false;

  if (filter.startsWith("project:")) {
    return brainId === filter.slice("project:".length);
  }

  const typeById = brainTypeById(discovery);
  if (filter === "current-project") {
    return brainId === currentProjectBrainId(discovery);
  }
  if (filter === "all-projects") {
    return typeById[brainId] === "project";
  }
  return typeById[brainId] === filter;
}

export function buildBrainFilterOptions(
  items: readonly BrowseBrainItem[],
  discovery: BrainDiscoveryLite | null | undefined,
): BrainFilterOption[] {
  if (items.length === 0) return [];

  const typeById = brainTypeById(discovery);
  const counts: Record<Exclude<BrainFilter, `project:${string}`>, number> = {
    all: items.length,
    global: 0,
    personal: 0,
    "current-project": 0,
    "all-projects": 0,
    team: 0,
  };
  const projectCounts = new Map<string, number>();
  const currentProjectId = currentProjectBrainId(discovery);

  for (const item of items) {
    const brainId = itemBrainId(item);
    if (!brainId) {
      counts.global += 1;
      continue;
    }

    const type = typeById[brainId];
    if (type === "personal") counts.personal += 1;
    if (type === "team") counts.team += 1;
    if (type === "project") {
      counts["all-projects"] += 1;
      projectCounts.set(brainId, (projectCounts.get(brainId) ?? 0) + 1);
    }
    if (currentProjectId && brainId === currentProjectId) {
      counts["current-project"] += 1;
    }
  }

  const options: BrainFilterOption[] = [
    { id: "all", label: labelForBuiltIn("all", counts.all) },
  ];
  const builtInOrder: Exclude<BrainFilter, "all" | `project:${string}`>[] = [
    "global",
    "personal",
    "current-project",
    "all-projects",
    "team",
  ];

  for (const filter of builtInOrder) {
    const count = counts[filter];
    if (count > 0) {
      options.push({ id: filter, label: labelForBuiltIn(filter, count) });
    }
  }

  const projectOptions = (discovery?.brains ?? [])
    .filter((brain) => brain.type === "project")
    .map((brain) => {
      const count = projectCounts.get(brain.id) ?? 0;
      if (count === 0) return null;
      const label = projectLabel(brain);
      return {
        id: `project:${brain.id}` as const,
        label: `${label} (${count})`,
        sortLabel: label,
      };
    })
    .filter((option): option is { id: `project:${string}`; label: string; sortLabel: string } => option !== null)
    .sort((a, b) => a.sortLabel.localeCompare(b.sortLabel));

  for (const option of projectOptions) {
    options.push({
      id: option.id,
      label: option.label,
    });
  }

  return options;
}

function itemBrainId(item: BrowseBrainItem): string | null {
  const value = item.metadata?.brain_id;
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function currentProjectBrainId(discovery: BrainDiscoveryLite | null | undefined): string | null {
  const value = discovery?.current_project?.registered_brain_id;
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function labelForBuiltIn(filter: Exclude<BrainFilter, `project:${string}`>, count: number): string {
  const labels: Record<Exclude<BrainFilter, `project:${string}`>, string> = {
    all: "All",
    global: "Global",
    personal: "Personal",
    "current-project": "Current project",
    "all-projects": "All projects",
    team: "Team",
  };
  return `${labels[filter]} (${count})`;
}

function projectLabel(brain: BrainDiscoveryBrain): string {
  const description = brain.description?.replace(/\s+project brain$/i, "").trim();
  if (description) return description;
  const root = brain.root?.replace(/\/project-brain$/, "").split("/").filter(Boolean).pop();
  if (root) return titleCase(root);
  return titleCase(brain.id.replace(/^project[-_]/i, ""));
}

function titleCase(value: string): string {
  return value.replace(/[-_]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
