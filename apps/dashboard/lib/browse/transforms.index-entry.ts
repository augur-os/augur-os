import type { BrowseItem, CLIToolStatus } from "./types";
import { buildPromoteBrowseAction } from "./overlay";
import { withDemoRunActions } from "./demoRunActions";
import {
  LOG_CATEGORY_ICONS,
  browseIndexItemId,
  displayWikiTags,
  firstString,
  normalizeStringList,
} from "./transforms.shared";
import {
  resolveIndexActions,
  resolveIndexPrimaryAction,
} from "./transforms.index-entry.actions";
import {
  buildIndexEnrichedMeta,
  resolveIndexDescription,
  resolveIndexTypeBadge,
} from "./transforms.index-entry.meta";

/**
 * Transform a RAG index entry into a BrowseItem.
 * Used by the unified browse API route.
 */
export function transformIndexEntry(
  entry: Record<string, any>,
  category: string,
): BrowseItem {
  const type = entry.type || category;
  const entryId = entry.id || entry.name || "";
  const itemId = browseIndexItemId(entry, category, entryId);
  const title = entry.title || entry.description || entry.name || "";

  // Determine primary action based on category
  const primaryAction = resolveIndexPrimaryAction(entry, category, entryId, type, itemId);

  // Build per-card secondary actions for relevant categories
  const actions = resolveIndexActions(entry, category, entryId, type, itemId);

  // Populate cliTools for integrations category
  let cliTools: CLIToolStatus[] | undefined;
  if (category === "integrations" && Array.isArray(entry.cli_tools)) {
    cliTools = (entry.cli_tools as CLIToolStatus[]).map((ct) => ({
      name: ct.name,
      installed: ct.installed,
      version: ct.version,
      configured: ct.configured,
      install_hint: ct.install_hint,
      homepage: ct.homepage,
    }));
  }

  // Build a useful typeBadge per category
  const typeBadge = resolveIndexTypeBadge(entry, category, type, itemId);

  // ── Description per category ──────────────────────────────────
  // Each category has different available fields in the API response.
  // This switch uses ONLY fields confirmed to exist for each category.
  const _skill = entry.metadata?.skill || "";
  const description = resolveIndexDescription(entry, category, typeBadge, itemId, _skill);

  // Build enriched metadata from entry.metadata + category-specific derived fields
  const enrichedMeta = buildIndexEnrichedMeta(entry, category, type, itemId);

  const promoteAction = buildPromoteBrowseAction({
    id: itemId,
    title,
    description,
    category,
    sourcePath: firstString(entry.source_path, entry.metadata?.source_path),
    metadata: enrichedMeta,
  });
  const allActions = promoteAction ? [...(actions || []), promoteAction] : actions;

  return withDemoRunActions({
    id: itemId,
    title,
    description,
    icon: category === "logs"
      ? LOG_CATEGORY_ICONS[entry.metadata?.category || entryId] || "ScrollText"
      : category === "mcp-servers"
        ? "Server"
        : undefined,
    typeBadge,
    path: entry.source_path,
    tags: category === "wiki" ? displayWikiTags(entry, itemId) : normalizeStringList(entry.tags),
    primaryAction,
    actions: allActions,
    cliTools,
    metadata: Object.keys(enrichedMeta).length > 0 ? enrichedMeta : undefined,
  }, category);
}
