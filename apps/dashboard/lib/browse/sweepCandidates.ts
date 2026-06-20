import type { BrowseItem, ViewMode } from "./types";

export type SweepTargetKind = "docs" | "source-cards" | "vault-notes" | "pages-artifacts" | "pages-live";
export type ArchiveMode = "docs-archive" | "git-aware";
export type SweepSourceTab = "sources" | "notes" | "documents" | "pages";
type SweepCandidateMode = ViewMode | "sources";

export type SweepUnsupportedReason =
  | "unsupported_view_mode"
  | "missing_source_path"
  | "missing_note_path"
  | "missing_page_source_path"
  | "relative_page_source_path"
  | "unsupported_page_kind";

export interface SweepTargetPayload {
  kind: SweepTargetKind;
  source_path: string;
  source_id: string;
  archive_mode: ArchiveMode;
  title: string;
  metadata: Record<string, string>;
}

export interface SweepCandidateResult {
  source_tab: SweepSourceTab;
  targets: SweepTargetPayload[];
  unsupported: Array<{ id: string; title: string; reason: SweepUnsupportedReason }>;
}

function firstMetadataPath(item: BrowseItem, keys: string[]): string {
  for (const key of keys) {
    const value = item.metadata?.[key];
    const text = typeof value === "string" ? value.trim() : "";
    if (text) return text;
  }
  return "";
}

function firstItemPath(item: BrowseItem, keys: string[]): string {
  return firstMetadataPath(item, keys) || item.path?.trim() || "";
}

function stringMetadata(item: BrowseItem): Record<string, string> {
  const metadata = item.metadata || {};
  const entries = Object.entries(metadata)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => [key, String(value)]);
  return Object.fromEntries(entries);
}

function isAbsoluteSourcePath(value: string): boolean {
  return value.startsWith("/")
    || /^[A-Za-z]:[\\/]/.test(value)
    || value.startsWith("\\\\");
}

function metadataText(item: BrowseItem, key: string): string {
  const value = item.metadata?.[key];
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function pathLooksLikeSharedSourceCard(sourcePath: string): boolean {
  const normalized = sourcePath.replace(/\\/g, "/");
  return normalized.startsWith("project-brain/knowledge/sources/")
    || normalized.includes("/project-brain/knowledge/sources/");
}

function pathHasSourcesSegment(sourcePath: string): boolean {
  const normalized = sourcePath.replace(/\\/g, "/");
  return normalized.startsWith("sources/") || normalized.includes("/sources/");
}

function isSourceCardItem(item: BrowseItem, sourcePath: string): boolean {
  const journeyCategory = metadataText(item, "journey_category") || metadataText(item, "journeyCategory");
  const rootHints = [
    metadataText(item, "source_root"),
    metadataText(item, "sourceRoot"),
    metadataText(item, "vault_root"),
    metadataText(item, "vaultRoot"),
    metadataText(item, "vault_scope"),
    metadataText(item, "vaultScope"),
    metadataText(item, "promotion_state"),
    metadataText(item, "promotionState"),
  ];
  const hasVaultRootHint = rootHints.some((value) =>
    value === "shared"
    || value === "private"
    || value === "packet"
    || value.includes("vault"),
  );
  if (journeyCategory === "sources" && (hasVaultRootHint || pathHasSourcesSegment(sourcePath))) {
    return true;
  }
  return pathLooksLikeSharedSourceCard(sourcePath);
}

function unsupported(
  item: BrowseItem,
  reason: SweepUnsupportedReason,
): SweepCandidateResult["unsupported"][number] {
  return { id: item.id, title: item.title, reason };
}

function target(
  item: BrowseItem,
  kind: SweepTargetKind,
  sourcePath: string,
  archiveMode: ArchiveMode,
): SweepTargetPayload {
  return {
    kind,
    source_path: sourcePath,
    source_id: item.id,
    archive_mode: archiveMode,
    title: item.title,
    metadata: stringMetadata(item),
  };
}

export function buildSweepCandidates(mode: SweepCandidateMode, items: BrowseItem[]): SweepCandidateResult {
  const sourceTab: SweepSourceTab =
    mode === "sources" || mode === "notes" || mode === "documents" || mode === "pages" ? mode : "sources";
  const targets: SweepTargetPayload[] = [];
  const unsupportedItems: SweepCandidateResult["unsupported"] = [];

  for (const item of items) {
    if (mode === "sources") {
      const sourcePath = firstItemPath(item, ["source_path", "filePath", "path", "sourcePath"]);
      if (!sourcePath) {
        unsupportedItems.push(unsupported(item, "missing_source_path"));
        continue;
      }
      if (isSourceCardItem(item, sourcePath)) {
        targets.push(target(item, "source-cards", sourcePath, "git-aware"));
        continue;
      }
      targets.push(target(item, "docs", sourcePath, "docs-archive"));
      continue;
    }

    if (mode === "documents") {
      const sourcePath = firstItemPath(item, ["source_path", "filePath", "path", "sourcePath"]);
      if (!sourcePath) {
        unsupportedItems.push(unsupported(item, "missing_source_path"));
        continue;
      }
      targets.push(target(item, "docs", sourcePath, "docs-archive"));
      continue;
    }

    if (mode === "notes") {
      const sourcePath = firstItemPath(item, ["source_path", "filePath", "path", "sourcePath"]);
      if (!sourcePath) {
        unsupportedItems.push(unsupported(item, "missing_note_path"));
        continue;
      }
      targets.push(target(item, "vault-notes", sourcePath, "git-aware"));
      continue;
    }

    if (mode === "pages") {
      const kind = item.metadata?.kind || "";
      if (kind === "live") {
        const sourcePath = firstMetadataPath(item, ["sourcePath", "source_path", "filePath", "path"]);
        if (!sourcePath) {
          unsupportedItems.push(unsupported(item, "missing_page_source_path"));
          continue;
        }
        if (!isAbsoluteSourcePath(sourcePath)) {
          unsupportedItems.push(unsupported(item, "relative_page_source_path"));
          continue;
        }
        targets.push(target(item, "pages-live", sourcePath, "git-aware"));
        continue;
      }

      if (kind === "generated" || kind === "saved") {
        const sourcePath = firstItemPath(item, ["filePath", "source_path", "path", "sourcePath"]);
        if (!sourcePath) {
          unsupportedItems.push(unsupported(item, "missing_page_source_path"));
          continue;
        }
        targets.push(target(item, "pages-artifacts", sourcePath, "docs-archive"));
        continue;
      }

      unsupportedItems.push(unsupported(item, "unsupported_page_kind"));
      continue;
    }

    unsupportedItems.push(unsupported(item, "unsupported_view_mode"));
  }

  return { source_tab: sourceTab, targets, unsupported: unsupportedItems };
}
