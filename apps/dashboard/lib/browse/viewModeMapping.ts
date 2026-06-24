import { BROWSE_CATEGORIES, RETIRED_VIEW_MODES, type ViewMode } from "./types";

const LEGACY_VIEW_MODE_MAP: Record<string, ViewMode> = {
  "dashboard-surfaces": "pages",
  "scheduled-executions": "loops",
  "background-routines": "loops",
  vault: "notes",
  agents: "agent-profiles",
};

const VAULT_JOURNEY_MODES = new Set<ViewMode>([
  "notes",
  "archive",
]);

const VAULT_JOURNEY_PATH_ROOTS: Partial<Record<ViewMode, string>> = {
  notes: "notes",
  archive: "archive",
};

const LEGACY_NOTES_ROOTS = new Set(["notes", "inbox", "sources", "prompts"]);

function vaultRelativeRoot(path: string): string | null {
  const segments = path.split(/[\\/]+/).filter(Boolean);
  if (segments.length === 0) return null;

  // `~`-prefixed paths are home-relative absolute paths (they appear in index
  // data alongside fully-expanded ones); treat them as absolute so the Au-vault
  // anchor lookup runs instead of returning the literal "~" segment.
  const isAbsolute =
    path.startsWith("/") || path.startsWith("~") || /^[A-Za-z]:[\\/]/.test(path);
  if (!isAbsolute) return segments[0] ?? null;

  const vaultIndex = segments.indexOf("Au-vault");
  return vaultIndex >= 0 ? segments[vaultIndex + 1] ?? null : null;
}

export function normalizeRequestedViewMode(value: string | null | undefined): ViewMode | null {
  if (!value) return null;
  const mapped = LEGACY_VIEW_MODE_MAP[value] ?? RETIRED_VIEW_MODES[value]?.view ?? value;
  const category = BROWSE_CATEGORIES.find((item) => item.id === mapped);
  return category ? category.id : null;
}

export function indexCategoryForViewMode(mode: ViewMode): string {
  if (mode === "pages") return "pages";
  if (VAULT_JOURNEY_MODES.has(mode)) return "vault";
  return mode;
}

export function journeyCategoryForViewMode(mode: ViewMode): string | null {
  return VAULT_JOURNEY_MODES.has(mode) ? mode : null;
}

export function itemMatchesViewMode(
  item: { metadata?: Record<string, string>; path?: string },
  mode: ViewMode,
): boolean {
  if (!VAULT_JOURNEY_MODES.has(mode)) return true;
  const journeyCategory = item.metadata?.journey_category;
  if (mode === "notes") {
    if (journeyCategory) return LEGACY_NOTES_ROOTS.has(journeyCategory);
    if (!item.path) return false;
    const root = vaultRelativeRoot(item.path);
    return root ? LEGACY_NOTES_ROOTS.has(root) : false;
  }
  if (journeyCategory) return journeyCategory === mode;

  const root = VAULT_JOURNEY_PATH_ROOTS[mode];
  if (!root || !item.path) return false;
  return vaultRelativeRoot(item.path) === root;
}
