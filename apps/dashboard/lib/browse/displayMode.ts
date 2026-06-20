import { BROWSE_CATEGORIES, type BrowseCategory, type ViewMode } from "./types";

export type { BrowseDisplayMode } from "./displayModeTypes";
import type { BrowseDisplayMode } from "./displayModeTypes";

export const BROWSE_DISPLAY_MODE_STORAGE_KEY = "augur:browse:display-mode:v1";

export type BrowseDisplayModeOverrides = Partial<Record<ViewMode, BrowseDisplayMode>>;

const VALID_VIEW_MODES = new Set<ViewMode>(BROWSE_CATEGORIES.map((category) => category.id));

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

function isBrowseDisplayMode(value: unknown): value is BrowseDisplayMode {
  return value === "card" || value === "list";
}

export function readDisplayModeOverrides(): BrowseDisplayModeOverrides {
  const localStorage = storage();
  if (!localStorage) return {};

  let raw: string | null;
  try {
    raw = localStorage.getItem(BROWSE_DISPLAY_MODE_STORAGE_KEY);
  } catch {
    return {};
  }
  if (!raw) return {};

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};

  const overrides: BrowseDisplayModeOverrides = {};
  Object.entries(parsed).forEach(([key, value]) => {
    if (!VALID_VIEW_MODES.has(key as ViewMode)) return;
    if (!isBrowseDisplayMode(value)) return;
    overrides[key as ViewMode] = value;
  });
  return overrides;
}

export function writeDisplayModeOverride(
  viewMode: ViewMode,
  displayMode: BrowseDisplayMode,
): BrowseDisplayModeOverrides {
  const overrides = {
    ...readDisplayModeOverrides(),
    [viewMode]: displayMode,
  };
  try {
    storage()?.setItem(BROWSE_DISPLAY_MODE_STORAGE_KEY, JSON.stringify(overrides));
  } catch {
    return overrides;
  }
  return overrides;
}

export function displayModeForCategory(
  category: BrowseCategory,
  overrides: BrowseDisplayModeOverrides,
): BrowseDisplayMode {
  return overrides[category.id] ?? category.defaultDisplayMode ?? "card";
}
