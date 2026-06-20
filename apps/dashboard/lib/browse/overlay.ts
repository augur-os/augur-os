import type { BrowseCardAction, BrowseItem, ViewMode } from "./types";

export type OverlayScopeFilter = "shared" | "private" | "packet";

export type OverlayViewMode = Extract<ViewMode, "notes" | "wiki" | "skills">;

const OVERLAY_VIEW_MODES: readonly OverlayViewMode[] = [
  "notes",
  "wiki",
  "skills",
];

type OverlayMetadata = Record<string, unknown> | undefined;
type OverlayScopeSource = BrowseItem | OverlayMetadata;

export function isOverlayViewMode(value: string): value is OverlayViewMode {
  return (OVERLAY_VIEW_MODES as readonly string[]).includes(value);
}

/**
 * Stable, collision-free identity for a browse card.
 *
 * In overlay view modes the same `item.id` is intentionally surfaced more than
 * once — e.g. a note or skill that exists in both the shared and private vault
 * scopes is a distinct card per scope. Those variants are only distinguished by
 * scope/source/path, so the React key (and the dedup key in useBrowseState)
 * must fold those fields in; keying by `item.id` alone collapses or duplicates
 * cards (React "two children with the same key"). Non-overlay views dedup by id
 * alone, so the bare id is already unique there.
 */
export function browseItemKey(item: BrowseItem, viewMode: string): string {
  if (!isOverlayViewMode(viewMode)) return item.id;
  return [
    item.id,
    item.metadata?.vault_scope ?? "",
    item.metadata?.source_root ?? "",
    item.path ?? "",
  ].join("::");
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (text) return text;
  }
  return undefined;
}

function normalizeScope(value: unknown): OverlayScopeFilter | undefined {
  const text = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (text === "shared" || text === "private" || text === "packet") return text;
  return undefined;
}

export function overlayScope(metadata: OverlayMetadata): OverlayScopeFilter | null {
  if (!metadata) return null;
  if (normalizeScope(metadata.promotion_state) === "packet") return "packet";
  return normalizeScope(metadata.vault_scope)
    ?? normalizeScope(metadata.overlay_scope)
    ?? normalizeScope(metadata.scope)
    ?? normalizeScope(metadata.promotion_state)
    ?? null;
}

export function overlayScopeLabel(scope: OverlayScopeFilter | null | undefined): string {
  if (scope === "shared") return "Shared";
  if (scope === "private") return "Private";
  if (scope === "packet") return "Packet";
  return "All";
}

function overlayMetadata(source: OverlayScopeSource): OverlayMetadata {
  if (!source) return undefined;
  if ("id" in source && "metadata" in source) {
    return source.metadata as OverlayMetadata;
  }
  return source as Record<string, unknown>;
}

export function matchesOverlayScope(source: OverlayScopeSource, filter: OverlayScopeFilter | null): boolean {
  if (!filter) return true;
  return overlayScope(overlayMetadata(source)) === filter;
}

function promotableBrowseCategory(
  browseCategory: string,
  metadata: OverlayMetadata,
): "wiki" | "skills" | "notes" | null {
  if (browseCategory === "wiki" || browseCategory === "skills") return browseCategory;
  if (browseCategory !== "vault") return null;

  const journeyCategory = firstString(metadata?.journey_category, metadata?.journeyCategory)?.toLowerCase();
  if (journeyCategory === "notes" || journeyCategory === "sources") return "notes";
  return null;
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => {
      const trimmed = String(item).trim();
      return trimmed ? [trimmed] : [];
    });
  }
  if (typeof value === "string") {
    return value.split(",").flatMap((item) => {
      const trimmed = item.trim();
      return trimmed ? [trimmed] : [];
    });
  }
  return [];
}

export function buildPromoteBrowseAction(params: {
  id: string;
  title: string;
  description: string;
  category: string;
  sourcePath?: string;
  metadata?: Record<string, unknown>;
}): BrowseCardAction | null {
  const category = promotableBrowseCategory(params.category, params.metadata);
  const sourcePath = firstString(params.sourcePath, params.metadata?.source_path, params.metadata?.sourcePath);

  if (overlayScope(params.metadata) !== "private" || !sourcePath || !category) {
    return null;
  }

  return {
    id: `promote-${params.id}`,
    label: "Promote",
    icon: "UploadCloud",
    type: "mcp-tool",
    target: "promote-browse-item",
    args: {
      category,
      title: params.title,
      source_path: sourcePath,
      description: params.description,
      roles: stringList(params.metadata?.roles),
      domains: stringList(params.metadata?.domains),
    },
  };
}
