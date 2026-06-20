// ADR-802: the per-item `hub` field was removed with the hub-concept teardown.
import type { BrowseItem } from "./types";
import type { SkillOwnership, SkillRecord } from "./transforms.types";

export const LOG_CATEGORY_ICONS: Record<string, string> = {
  mcp: "Server",
  llm: "Cpu",
  plugins: "Puzzle",
  daemon: "Activity",
  "self-heal": "Shield",
  system: "Database",
  claude: "Bot",
};

export function formatLogCount(value: unknown): string {
  const count = Number(value);
  if (!Number.isFinite(count) || count <= 0) return "";
  return `${count} ${count === 1 ? "file" : "files"}`;
}

export function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      const text = value.trim();
      if (text) return text;
      continue;
    }
    if (typeof value === "number") {
      return Number.isFinite(value) ? String(value) : undefined;
    }
    if (typeof value === "boolean") return String(value);
  }
  return undefined;
}

export function copyMeta(
  metadata: Record<string, string>,
  key: string,
  value: unknown,
): void {
  if (Object.prototype.hasOwnProperty.call(metadata, key)) return;
  const text = firstString(value);
  if (text !== undefined) {
    metadata[key] = text;
  }
}

const NOTE_JOURNEY_CATEGORIES = new Set(["notes", "sources", "prompts"]);

export function hasVaultNoteSignal(metadata: Record<string, string>, path: string): boolean {
  const classificationSignal = firstString(
    metadata["x-augur-domain"],
    metadata.noteDomain,
    metadata["x-augur-source"],
    metadata.noteSource,
    metadata["x-augur-status"],
    metadata.noteStatus,
    metadata["x-augur-classification-confidence"],
    metadata.classificationConfidence,
  );
  if (classificationSignal) return true;

  const inactiveScope = firstString(metadata.inactive_scope)?.toLowerCase();
  if (
    metadata.journey_category === "archive" ||
    firstString(metadata.archive_source) ||
    firstString(metadata.archive_mode) ||
    inactiveScope === "true" ||
    inactiveScope === "1" ||
    inactiveScope === "yes"
  ) {
    return false;
  }

  const explicitNoteType = firstString(
    metadata["x-augur-note-type"],
    metadata.noteType,
    metadata.note_type,
    metadata.note_type_filter,
  );
  if (explicitNoteType) return true;

  if (metadata.journey_category === "inbox") return false;

  const urlSignal = firstString(
    metadata.canonical_url,
    metadata.canonicalUrl,
    metadata.url,
    metadata.source_url,
    metadata.sourceUrl,
    metadata.source_domain,
  );
  if (urlSignal) return true;

  const normalizedPath = path.replace(/\\/g, "/");
  if (
    normalizedPath.includes("/sources/urls/") ||
    normalizedPath.includes("/sources/files/") ||
    normalizedPath.includes("/prompts/")
  ) {
    return true;
  }

  return NOTE_JOURNEY_CATEGORIES.has(metadata.journey_category);
}

export function normalizeSkillOwnership(value: unknown, fallback: SkillOwnership = "augur"): SkillOwnership {
  const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (normalized === "augur" || normalized === "external" || normalized === "adopted" || normalized === "user") return normalized;
  if (normalized === "private-vault") return "user";
  if (normalized === "local" || normalized === "global" || normalized === "plugin" || normalized === "plugin-cache") return "external";
  if (normalized.endsWith("-plugin-cache")) return "external";
  if (normalized.endsWith("-local") || normalized.endsWith("-global")) return "external";
  return fallback;
}

export function normalizeStringList(value: unknown): string[] {
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

export function normalizeTagKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

const SOURCE_SCOPE_LABELS: Record<string, string> = {
  "project-brain": "Project Brain",
  "private-vault": "Personal Vault",
  "plugin-cache": "Plugin Cache",
  "external-client": "Client Projection",
  external: "External",
  global: "Global",
  system: "System",
  unknown: "Unknown",
};

const SOURCE_SCOPE_PRIORITY: Record<string, number> = {
  "project-brain": 50,
  "private-vault": 40,
  "plugin-cache": 30,
  "external-client": 20,
  global: 15,
  external: 10,
  system: 5,
  unknown: 0,
};

export function normalizeSourceScope(...values: unknown[]): string {
  const raw = firstString(...values);
  const key = raw ? normalizeTagKey(raw) : "";
  if (!key) return "unknown";
  if (key === "project" || key === "project-brain" || key === "shared-vault") return "project-brain";
  if (key === "private" || key === "vault" || key === "private-vault" || key === "personal-vault") return "private-vault";
  if (key === "plugin" || key === "plugin-cache" || key.endsWith("-plugin-cache")) return "plugin-cache";
  if (key === "client" || key === "client-projection" || key === "external-client") return "external-client";
  if (key.endsWith("-local") || key.endsWith("-global")) return "external-client";
  return key;
}

export function formatSourceScopeLabel(scope: string | undefined): string | undefined {
  if (!scope) return undefined;
  return SOURCE_SCOPE_LABELS[scope] || scope.split("-").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

export function sourceScopePriority(scope: string): number {
  return SOURCE_SCOPE_PRIORITY[scope] ?? SOURCE_SCOPE_PRIORITY.external;
}

export function uniqueStringList(...values: unknown[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    for (const item of normalizeStringList(value)) {
      const key = item.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(item);
    }
  }
  return result;
}

export function selectCanonicalSkillRecord(records: SkillRecord[]): SkillRecord {
  return [...records].sort((a, b) => {
    const priorityDelta =
      sourceScopePriority(normalizeSourceScope(b.sourceRoot, b.source_root, b.source, b.hub)) -
      sourceScopePriority(normalizeSourceScope(a.sourceRoot, a.source_root, a.source, a.hub));
    if (priorityDelta !== 0) return priorityDelta;
    if (firstString(b.description) && !firstString(a.description)) return 1;
    if (firstString(a.description) && !firstString(b.description)) return -1;
    return 0;
  })[0] || {};
}

export function sourceScopeFromSkillPath(path: string | undefined): string | undefined {
  if (!path) return undefined;
  const normalized = path.replace(/\\/g, "/");
  if (
    normalized.includes("/.claude/skills/") ||
    normalized.includes("/.codex/skills/") ||
    normalized.includes("/.gemini/skills/")
  ) {
    return "external-client";
  }
  if (normalized.includes("/project-brain/capabilities/skills/")) return "project-brain";
  if (normalized.includes("/Au-vault/") && normalized.includes("/capabilities/skills/")) return "private-vault";
  return undefined;
}

export function skillNameFromPath(path: string | undefined): string | undefined {
  if (!path) return undefined;
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  const fileName = parts[parts.length - 1]?.toLowerCase();
  if (fileName === "skill.md" && parts.length >= 2) return parts[parts.length - 2];
  const skillIndex = parts.lastIndexOf("skills");
  if (skillIndex >= 0 && skillIndex + 1 < parts.length) return parts[skillIndex + 1];
  return undefined;
}

export function skillSourceScopeForItem(item: BrowseItem): string {
  const metadata = item.metadata;
  return normalizeSourceScope(
    metadata?.sourceRoot,
    metadata?.source_root,
    sourceScopeFromSkillPath(item.path),
    metadata?.source,
  );
}

export function canonicalSkillItemName(item: BrowseItem): string {
  const name = firstString(
    item.metadata?.skillName,
    skillNameFromPath(item.path),
    item.title,
    item.id.includes(":") ? item.id.split(":").pop() : item.id,
  );
  return normalizeTagKey(name || item.id) || item.id;
}

export function wikiPageKind(entry: Record<string, any>, entryId: string): string {
  const explicit = firstString(
    entry.page_type,
    entry.pageType,
    entry.metadata?.page_type,
    entry.metadata?.pageType,
  );
  if (explicit) return explicit;
  if (entryId.startsWith("concepts/")) return "concept";
  if (entryId.startsWith("queries/")) return "query";
  return "wiki";
}

export function formatWikiPageKind(entry: Record<string, any>, entryId: string): string {
  const kind = normalizeTagKey(wikiPageKind(entry, entryId));
  if (kind === "concept") return "Concept";
  if (kind === "query") return "Query";
  if (kind === "overview") return "Overview";
  if (kind === "index") return "Index";
  return "Wiki Page";
}

export function displayWikiTags(entry: Record<string, any>, itemId: string): string[] {
  const rawTags = [
    ...normalizeStringList(entry.tags),
    ...normalizeStringList(entry.metadata?.tags),
    ...normalizeStringList(entry.metadata?.pageTags),
  ];
  const blocked = new Set([
    "wiki",
    "concept",
    "concepts",
    "query",
    "queries",
    "page",
    "brain",
    normalizeTagKey(itemId),
    normalizeTagKey(itemId.split("/").pop() || ""),
  ]);
  for (const value of [entry.id, entry.name, entry.title, entry.metadata?.title]) {
    const key = normalizeTagKey(firstString(value) || "");
    if (key) blocked.add(key);
  }
  const result: string[] = [];
  const seen = new Set<string>();
  for (const tag of rawTags) {
    const key = normalizeTagKey(tag);
    if (!key || blocked.has(key) || seen.has(key)) continue;
    seen.add(key);
    result.push(tag);
  }
  return result;
}

export function wikiMarkdownLink(entry: Record<string, any>, itemId: string): string {
  const wikiPath = String(entry.source_path || itemId)
    .replace(/\\/g, "/")
    .replace(/^.*?\/wiki\//, "")
    .replace(/\.md$/i, "");
  const target = wikiPath || itemId.replace(/\.md$/i, "");
  const title = firstString(entry.title, entry.name, entry.id);
  return title ? `[[${target}|${title}]]` : `[[${target}]]`;
}

const SOURCE_BACKED_ID_CATEGORIES = new Set(["documents", "vault", "scripts", "tests"]);

export function hasOverlayIdentity(entry: Record<string, any>): boolean {
  return firstString(
    entry.vault_scope,
    entry.metadata?.vault_scope,
    entry.promotion_state,
    entry.metadata?.promotion_state,
    entry.source_root,
    entry.metadata?.source_root,
  ) !== undefined;
}

export function browseIndexItemId(entry: Record<string, any>, category: string, fallback: string): string {
  const explicitId = firstString(entry.id);
  if (category === "wiki") {
    if (explicitId) return explicitId;
    const sourcePath = typeof entry.source_path === "string" ? entry.source_path.trim() : "";
    if (sourcePath) return sourcePath;
  }
  if (SOURCE_BACKED_ID_CATEGORIES.has(category)) {
    const sourcePath = typeof entry.source_path === "string" ? entry.source_path.trim() : "";
    if (explicitId && hasOverlayIdentity(entry) && explicitId.includes(":")) return explicitId;
    if (sourcePath) return sourcePath;
  }
  if (explicitId) return explicitId;
  return fallback || entry.source_path || entry.title || entry.name || category;
}
