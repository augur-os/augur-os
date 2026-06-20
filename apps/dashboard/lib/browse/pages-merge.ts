import type { BrowseItem, BrowsePageKind } from "./types";

export interface LiveTabEntry {
  label: string;
  href: string;
  hub: string;
  icon: string;
  pageType?: string;
  skillId?: string;
}

export interface ArtifactEntry {
  slug: string;
  title: string;
  kind: Exclude<BrowsePageKind, "live">;
  hub: string;
  url: string;
  path: string;
  tags: string[];
  promoted_at: string;
  created_at: string;
  /**
   * Owning skill that generated this artifact, when known. Drives the
   * constrained HTML→AI bridge: `augur.runAction(id)` only dispatches actions
   * DECLARED by this skill. Undefined → runAction disabled for the artifact.
   */
  skill?: string;
}

export interface IndexedPageEntry {
  id?: unknown;
  title?: unknown;
  hub?: unknown;
  tags?: unknown;
  route?: unknown;
  source_path?: unknown;
  metadata?: Record<string, unknown>;
}

function liveDescription(tab: LiveTabEntry): string {
  const hrefParts = tab.href.split("/").filter(Boolean);
  const skill = tab.skillId || (hrefParts.length >= 2 ? hrefParts[1] : "");
  return skill
    ? `${skill.replace(/[-_]/g, " ")} · workspace page`
    : "dashboard page";
}

function liveTypeBadge(pageType: string | undefined): string {
  if (pageType === "yaml") return "YAML";
  if (pageType === "auto") return "Auto";
  return "Live";
}

function normalizeRoute(route: string): string {
  const trimmed = route.trim();
  if (!trimmed) return "";
  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeadingSlash.length > 1 ? withLeadingSlash.replace(/\/+$/, "") : withLeadingSlash;
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (text) return text;
  }
  return "";
}

function isAbsoluteSourcePath(value: string): boolean {
  return value.startsWith("/")
    || /^[A-Za-z]:[\\/]/.test(value)
    || value.startsWith("\\\\");
}

function sourcePathByRoute(indexedPages: IndexedPageEntry[] = []): Map<string, string> {
  const map = new Map<string, string>();
  for (const entry of indexedPages) {
    const route = normalizeRoute(firstString(entry.route, entry.metadata?.route));
    const sourcePath = firstString(
      entry.source_path,
      entry.metadata?.source_path,
      entry.metadata?.sourcePath,
      entry.metadata?.filePath,
      entry.metadata?.path,
    );
    if (!route || !sourcePath) continue;
    const existing = map.get(route);
    if (!existing || (!isAbsoluteSourcePath(existing) && isAbsoluteSourcePath(sourcePath))) {
      map.set(route, sourcePath);
    }
  }
  return map;
}

const ARTIFACT_KINDS = new Set<string>(["generated", "saved"]);

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((v): v is string => typeof v === "string");
  }
  return [];
}

/**
 * Artifact entries ride the pages browse index (kind: generated|saved in
 * metadata) instead of a separate artifacts-list MCP call. Extract them
 * back into ArtifactEntry shape for the card merge.
 */
export function extractIndexedArtifacts(
  indexedPages: IndexedPageEntry[] = [],
): ArtifactEntry[] {
  const artifacts: ArtifactEntry[] = [];
  for (const entry of indexedPages) {
    const meta = entry.metadata ?? {};
    const kind = firstString(meta.kind);
    if (!ARTIFACT_KINDS.has(kind)) continue;
    const slug = firstString(meta.slug, entry.id);
    if (!slug) continue;
    const skill = firstString(meta.skill);
    artifacts.push({
      slug,
      title: firstString(entry.title, meta.title) || slug,
      kind: kind as ArtifactEntry["kind"],
      hub: firstString(entry.hub, meta.hub) || "uncategorized",
      url: firstString(meta.url) || `/artifact/${slug}`,
      path: firstString(meta.path, entry.source_path),
      tags: stringList(entry.tags),
      promoted_at: firstString(meta.promoted_at),
      created_at: firstString(meta.created_at),
      ...(skill ? { skill } : {}),
    });
  }
  return artifacts;
}

export function mergePagesSources(
  live: LiveTabEntry[],
  artifacts: ArtifactEntry[],
  indexedPages: IndexedPageEntry[] = [],
): BrowseItem[] {
  const indexedSourceByRoute = sourcePathByRoute(indexedPages);

  const liveItems: BrowseItem[] = live.map((tab) => {
    const hrefParts = tab.href.split("/").filter(Boolean);
    const skill = tab.skillId || (hrefParts.length >= 2 ? hrefParts[1] : "");
    const sourcePath = indexedSourceByRoute.get(normalizeRoute(tab.href));
    return {
      id: `live:${tab.href}`,
      title: tab.label,
      description: liveDescription(tab),
      icon: tab.icon,
      path: tab.href,
      typeBadge: liveTypeBadge(tab.pageType),
      primaryAction: {
        label: "Open Page",
        type: "navigate",
        target: tab.href,
      },
      actions: [
        {
          id: `open-${tab.href}`,
          label: "Open",
          icon: "ExternalLink",
          type: "navigate",
          target: tab.href,
        },
      ],
      metadata: {
        kind: "live",
        pageType: tab.pageType || "tsx",
        ...(skill ? { skill } : {}),
        ...(sourcePath ? { sourcePath } : {}),
      },
    };
  });

  const artifactItems: BrowseItem[] = artifacts.map((artifact) => ({
    id: `artifact:${artifact.slug}`,
    title: artifact.title,
    description: `${artifact.kind} HTML artifact`,
    icon: "FileCode",
    path: artifact.path,
    tags: artifact.tags,
    typeBadge: artifact.kind === "generated" ? "Generated" : "Saved",
    primaryAction: {
      label: "Open Artifact",
      type: "navigate",
      target: artifact.url,
    },
    actions: [
      {
        id: `open-${artifact.slug}`,
        label: "Open",
        icon: "ExternalLink",
        type: "navigate",
        target: artifact.url,
      },
      {
        id: `reveal-${artifact.slug}`,
        label: "Reveal",
        icon: "FolderOpen",
        type: "reveal-file",
        target: artifact.path,
      },
    ],
    metadata: {
      kind: artifact.kind,
      url: artifact.url,
      filePath: artifact.path,
      promoted_at: artifact.promoted_at,
      created_at: artifact.created_at,
      tags: artifact.tags.join(","),
      ...(artifact.skill ? { skill: artifact.skill } : {}),
    },
  }));

  return [...liveItems, ...artifactItems];
}
