import type { BrowseItem, BrowseCardAction } from "./types";
import type { SkillRecord } from "./transforms.types";
import {
  copyMeta,
  firstString,
  formatSourceScopeLabel,
  normalizeSkillOwnership,
  normalizeSourceScope,
  normalizeTagKey,
  selectCanonicalSkillRecord,
  skillSourceScopeForItem,
  sourceScopePriority,
  uniqueStringList,
  canonicalSkillItemName,
} from "./transforms.shared";

// Skills
export function transformSkills(
  skills: SkillRecord[],
): BrowseItem[] {
  const grouped = new Map<string, SkillRecord[]>();
  for (const skill of skills) {
    const name = firstString(skill.name, skill.display_name) || "Unnamed";
    const slug = normalizeTagKey(firstString(skill.name, name) || name) || "unnamed";
    const records = grouped.get(slug) || [];
    records.push(skill);
    grouped.set(slug, records);
  }

  return Array.from(grouped.entries()).map(([slug, records]) => {
    const s = selectCanonicalSkillRecord(records);
    const name = s.display_name || s.name || "Unnamed";
    const id = slug;
    const sourceScope = normalizeSourceScope(s.sourceRoot, s.source_root, s.source, s.hub);
    const fallbackOwnership = sourceScope === "private-vault" || s.source === "private-vault"
      ? "user"
      : !s.plugin && s.source !== "global" && s.hub !== "system"
      ? "augur"
      : "external";
    const ownership = normalizeSkillOwnership(s.ownership ?? s.source, fallbackOwnership);
    const isManaged = ownership === "augur" || ownership === "adopted";
    const skillActions: BrowseCardAction[] = isManaged
      ? [
          { id: `improve-${id}`, label: "Improve", icon: "Sparkles", type: "run-action", target: `/harden ${id}` },
          { id: `remove-${id}`, label: "Remove", icon: "Trash", type: "run-mcp", target: `remove-skill:${id}`, variant: "danger" },
        ]
      : [
          { id: `install-${id}`, label: "Install in IDE", icon: "CheckCircle2", type: "run-mcp", target: `install-skill:${id}` },
          { id: `catalog-${id}`, label: "Add to Catalog", icon: "BookmarkPlus", type: "run-mcp", target: `add-to-catalog:${id}` },
        ];
    const item: BrowseItem = {
      id,
      title: name,
      description: s.description || "",
      icon: "Puzzle",
      primaryAction: {
        label: "View",
        type: "navigate",
        target: `/browse/${slug}`,
      },
      actions: skillActions,
    };
    const meta: Record<string, string> = {};
    copyMeta(meta, "masterClient", s.master);
    copyMeta(meta, "ownership", ownership);
    copyMeta(meta, "source", s.source);
    copyMeta(meta, "sourceRoot", sourceScope);
    copyMeta(meta, "sourceScope", sourceScope);
    copyMeta(meta, "sourceScopeLabel", formatSourceScopeLabel(sourceScope));
    if (s.upstream?.source && typeof s.upstream.source === "string") meta.upstreamSource = s.upstream.source;
    if (s.upstream?.path && typeof s.upstream.path === "string") meta.upstreamPath = s.upstream.path;
    copyMeta(meta, "category", s.category);
    copyMeta(meta, "group", s.group);
    copyMeta(meta, "release", s.release);
    copyMeta(meta, "plugin", s.plugin);
    copyMeta(meta, "skillType", s.skill_type);
    if (s.tags?.length) copyMeta(meta, "skillTags", s.tags.join(","));
    copyMeta(meta, "hasDocs", firstString(s.hasDocs, s.has_docs));
    const skillClients = uniqueStringList(...records.map((record) => record.skillClients ?? record.skill_clients));
    copyMeta(meta, "skillClients", skillClients.join(","));
    const clientSources = uniqueStringList(...records.map((record) => record.clientSources ?? record.client_sources));
    copyMeta(meta, "clientSources", clientSources.join(","));
    const sourceRoots = uniqueStringList(records.map((record) => normalizeSourceScope(record.sourceRoot, record.source_root, record.source, record.hub)));
    copyMeta(meta, "sourceRoots", sourceRoots.join(","));
    if (Object.keys(meta).length > 0) {
      item.metadata = meta;
    }
    return item;
  });
}

export function dedupeSkillBrowseItems(items: BrowseItem[]): BrowseItem[] {
  const groups = new Map<string, BrowseItem[]>();
  for (const item of items) {
    const key = canonicalSkillItemName(item);
    const group = groups.get(key) || [];
    group.push(item);
    groups.set(key, group);
  }

  return Array.from(groups.values()).map((group) => {
    const primary = [...group].sort((a, b) => {
      const priorityDelta =
        sourceScopePriority(skillSourceScopeForItem(b)) -
        sourceScopePriority(skillSourceScopeForItem(a));
      if (priorityDelta !== 0) return priorityDelta;
      return (b.description ? 1 : 0) - (a.description ? 1 : 0);
    })[0];
    if (!primary) return group[0];

    const sourceScope = skillSourceScopeForItem(primary);
    const sourceRoots = uniqueStringList(group.map((item) => skillSourceScopeForItem(item)));
    const skillClients = uniqueStringList(...group.map((item) => item.metadata?.skillClients ?? item.metadata?.skill_clients));
    const clientSources = uniqueStringList(
      ...group.map((item) => item.metadata?.clientSources ?? item.metadata?.client_sources ?? item.metadata?.source),
    );
    const metadata: Record<string, string> = { ...(primary.metadata ?? {}) };
    copyMeta(metadata, "sourceRoot", sourceScope);
    copyMeta(metadata, "sourceScope", sourceScope);
    copyMeta(metadata, "sourceScopeLabel", formatSourceScopeLabel(sourceScope));
    copyMeta(metadata, "sourceRoots", sourceRoots.join(","));
    copyMeta(metadata, "skillClients", skillClients.join(","));
    copyMeta(metadata, "clientSources", clientSources.join(","));

    return {
      ...primary,
      metadata,
    };
  });
}
