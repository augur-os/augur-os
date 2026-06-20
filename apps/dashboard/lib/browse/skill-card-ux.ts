import type { BrowseCardAction, BrowseItem, BrowsePrimaryAction } from "@/lib/browse/types";
import { buildPromoteBrowseAction, overlayScope, overlayScopeLabel } from "@/lib/browse/overlay";

export type SkillTagTone = "neutral" | "success" | "warning" | "danger" | "info";
export type SkillTagKind = "hub" | "ownership" | "client" | "type" | "state";

export interface SkillTag {
  key: string;
  label: string;
  tone: SkillTagTone;
  kind?: SkillTagKind;
  title?: string;
}

export interface SkillInventorySummary {
  total: number;
  augur: number;
  external: number;
  adopted: number;
  user: number;
  needsSetup: number;
}

const CLIENT_DISPLAY_NAMES: Record<string, string> = {
  claude: "Claude",
  "claude-code": "Claude",
  "claude-plugin": "Claude",
  codex: "Codex",
  gemini: "Gemini",
  cursor: "Cursor",
  copilot: "Copilot",
  opencode: "OpenCode",
  augur: "Augur",
};

const OWNERSHIP_TONES: Record<string, SkillTagTone> = {
  augur: "info",
  external: "warning",
  adopted: "success",
  user: "info",
};

const OVERLAY_TONES: Record<"packet" | "private" | "shared", SkillTagTone> = {
  packet: "warning",
  private: "info",
  shared: "success",
};

function getMetadata(item: BrowseItem): Record<string, string> {
  return item.metadata ?? {};
}

/**
 * Build the `/browse/<skill>` URL for a skill card.
 *
 * Browse skill ids carry the form `skill:<source>:<name>` (see
 * `src/lib/index/_scanners_knowledge.py`). Passing the raw id into the URL
 * forces the colons through URL encoding and breaks the `[skill]` route
 * handler, so the URL is built from the bare skill name with the source root
 * preserved as a query hint for downstream disambiguation.
 */
function skillBrowseHref(item: BrowseItem): string {
  const metadata = getMetadata(item);
  const namedFromMeta = metadata.skillName?.trim();
  const namedFromId = item.id.includes(":")
    ? item.id.split(":").filter((segment) => segment.length > 0).pop() || item.id
    : item.id;
  const skillName = namedFromMeta || namedFromId;
  const sourceRoot = (metadata.source_root || metadata.sourceRoot || "").trim();
  const safeName = encodeURIComponent(skillName);
  return sourceRoot
    ? `/browse/${safeName}?source=${encodeURIComponent(sourceRoot)}`
    : `/browse/${safeName}`;
}

function parseBoolean(value: string | undefined): boolean {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "true" || normalized === "1" || normalized === "yes";
}

function splitList(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((client) => client.trim())
    .filter((client) => client !== "" && client.toLowerCase() !== "unknown");
}

function clientLabel(client: string): string {
  return CLIENT_DISPLAY_NAMES[client.toLowerCase()] ?? client;
}

function dedupeClientsByDisplayName(clients: string[]): string[] {
  const seenLabels = new Set<string>();
  const deduped: string[] = [];

  for (const client of clients) {
    const labelKey = clientLabel(client).toLowerCase();
    if (seenLabels.has(labelKey)) continue;
    seenLabels.add(labelKey);
    deduped.push(client);
  }

  return deduped;
}

function skillClients(metadata: Record<string, string>): string[] {
  const explicitClients = splitList(metadata.skillClients);
  return dedupeClientsByDisplayName(
    explicitClients.length > 0 ? explicitClients : splitList(metadata.masterClient),
  );
}

function dashboardPath(metadata: Record<string, string>): string | null {
  const path = metadata.dashboardPath?.trim();
  if (!path || path.toLowerCase() === "unknown") return null;
  return path;
}

function ownershipLabel(value: string | undefined): string | null {
  if (value === "augur") return "Managed";
  if (value === "external") return "External";
  if (value === "adopted") return "Adopted";
  if (value === "user") return "User";
  return null;
}

function ownershipTone(value: string | undefined): SkillTagTone {
  return OWNERSHIP_TONES[value ?? ""] ?? "neutral";
}

function isManaged(item: BrowseItem): boolean {
  const ownership = getMetadata(item).ownership;
  return ownership === "augur" || ownership === "adopted" || ownership === "user";
}

function parseQualityScore(value: string | undefined): number | null {
  if (!value) return null;
  const score = Number(value);
  return Number.isFinite(score) ? score : null;
}

function isLowQuality(item: BrowseItem): boolean {
  const metadata = getMetadata(item);
  if (metadata.qualityTier === "D" || metadata.qualityTier === "F") return true;

  const score = parseQualityScore(metadata.qualityScore);
  return score !== null && score < 55;
}

function buildCountTag(value: string | undefined, label: string): string | null {
  const count = Number(value);
  if (!Number.isFinite(count) || count <= 0) return null;
  return `${count} ${label}`;
}

export function getSkillIdentityTags(item: BrowseItem): SkillTag[] {
  const metadata = getMetadata(item);
  const tags: SkillTag[] = [];

  const scope = overlayScope(metadata);
  if (scope) {
    tags.push({
      key: `overlay-${scope}`,
      label: overlayScopeLabel(scope),
      tone: OVERLAY_TONES[scope],
      kind: "ownership",
      title: "Scope",
    });
  }

  const owner = ownershipLabel(metadata.ownership);
  if (owner) {
    tags.push({
      key: "ownership",
      label: owner,
      tone: ownershipTone(metadata.ownership),
      kind: "ownership",
      title: "Ownership",
    });
  }

  for (const client of skillClients(metadata).slice(0, 3)) {
    tags.push({
      key: `client-${client}`,
      label: clientLabel(client),
      tone: "neutral",
      kind: "client",
      title: "Client",
    });
  }

  if (metadata.skillType) {
    if (metadata.skillType === "unknown") {
      return tags;
    }
    tags.push({
      key: "skill-type",
      label: metadata.skillType,
      tone: "neutral",
      kind: "type",
      title: "Skill type",
    });
  }

  return tags;
}

export function getSkillStateTags(item: BrowseItem): SkillTag[] {
  const metadata = getMetadata(item);
  const tags: SkillTag[] = [];

  if (metadata.enabled === "true" || metadata.enabled === "false") {
    const enabled = parseBoolean(metadata.enabled);
    tags.push({
      key: "enabled",
      label: enabled ? "enabled" : "disabled",
      tone: enabled ? "success" : "neutral",
      kind: "state",
    });
  }

  if (parseBoolean(metadata.needsSetup)) {
    tags.push({ key: "needs-setup", label: "needs setup", tone: "warning", kind: "state" });
  }

  // ADR-741 check-resolvable findings — joined onto skill items by
  // enrichItemsWithCoverage(). The audit has no browse view of its own;
  // it rides the skill card here (see lib/browse/skillCoverage.ts).
  if (metadata.coverageIssueCount && metadata.coverageIssueCount !== "0") {
    tags.push({
      key: "coverage",
      label: metadata.coverageLabel || `${metadata.coverageIssueCount} coverage issues`,
      tone: metadata.coverageTone === "danger" ? "danger" : "warning",
      kind: "state",
      title: metadata.coverageSummary || "Skill coverage (ADR-741)",
    });
  }

  if (metadata.qualityTier) {
    const tier = metadata.qualityTier;
    const score = metadata.qualityScore !== undefined && metadata.qualityScore !== ""
      ? ` ${metadata.qualityScore}`
      : "";
    tags.push({
      key: "quality",
      label: `Quality ${tier}${score}`,
      tone: isLowQuality(item) ? "danger" : "success",
      kind: "state",
      title: "Quality",
    });
  }

  if (parseBoolean(metadata.updateAvailable)) {
    tags.push({ key: "update", label: "update available", tone: "warning", kind: "state" });
  }

  const toolCount = buildCountTag(metadata.mcpToolCount, metadata.mcpToolCount === "1" ? "tool" : "tools");
  if (toolCount) {
    tags.push({ key: "tools", label: toolCount, tone: "neutral", kind: "state" });
  }

  const actionCount = buildCountTag(metadata.actionCount, metadata.actionCount === "1" ? "action" : "actions");
  if (actionCount) {
    tags.push({ key: "actions", label: actionCount, tone: "neutral", kind: "state" });
  }

  const pageCount = buildCountTag(metadata.pageCount, metadata.pageCount === "1" ? "page" : "pages");
  if (pageCount) {
    tags.push({ key: "pages", label: pageCount, tone: "neutral", kind: "state" });
  }

  return tags;
}

export function getSkillPrimaryAction(item: BrowseItem): BrowsePrimaryAction {
  const metadata = getMetadata(item);

  if (metadata.enabled === "false") {
    return {
      label: "Enable",
      type: "run-mcp",
      target: `enable-skill:${item.id}`,
    };
  }

  if (parseBoolean(metadata.needsSetup)) {
    return {
      label: "Configure",
      type: "navigate",
      target: skillBrowseHref(item),
    };
  }

  if (metadata.ownership === "external" && !parseBoolean(metadata.adoptionReady)) {
    return {
      label: "Review",
      type: "navigate",
      target: skillBrowseHref(item),
    };
  }

  if (metadata.ownership === "external" && parseBoolean(metadata.adoptionReady)) {
    return {
      label: "Adopt",
      type: "run-mcp",
      target: `skill-adopt:${item.id}`,
    };
  }

  if (isManaged(item) && isLowQuality(item)) {
    return {
      label: "Improve",
      type: "run-action",
      target: `/harden ${item.id}`,
    };
  }

  const pagePath = dashboardPath(metadata);
  if (isManaged(item) && pagePath) {
    return {
      label: "Open",
      type: "navigate",
      target: pagePath,
    };
  }

  if (isManaged(item)) {
    return {
      label: "Open docs",
      type: "navigate",
      target: skillBrowseHref(item),
    };
  }

  return item.primaryAction;
}

export function getSkillSecondaryActions(item: BrowseItem): BrowseCardAction[] {
  const metadata = getMetadata(item);
  const actions: BrowseCardAction[] = [
    {
      id: `docs-${item.id}`,
      label: "Open docs",
      icon: "BookOpen",
      type: "navigate",
      target: skillBrowseHref(item),
    },
  ];

  const pagePath = dashboardPath(metadata);
  if (pagePath) {
    actions.push({
      id: `open-page-${item.id}`,
      label: "Open dashboard page",
      icon: "ExternalLink",
      type: "navigate",
      target: pagePath,
    });
  }

  if (isManaged(item)) {
    actions.push(
      {
        id: `configure-${item.id}`,
        label: "Configure",
        icon: "Settings",
        type: "navigate",
        target: skillBrowseHref(item),
      },
      {
        id: `improve-${item.id}`,
        label: "Improve",
        icon: "Sparkles",
        type: "run-action",
        target: `/harden ${item.id}`,
      },
      {
        id: `sync-${item.id}`,
        label: "Sync/export",
        icon: "RefreshCw",
        type: "run-action",
        target: `/dev-sync ${item.id}`,
      },
    );
  }

  if (metadata.ownership === "external") {
    actions.push({
      id: `adopt-${item.id}`,
      label: "Adopt",
      icon: "ArrowDownToLine",
      type: "run-mcp",
      target: `skill-adopt:${item.id}`,
    });
  }

  const promoteAction = buildPromoteBrowseAction({
    id: item.id,
    title: item.title,
    description: item.description,
    category: "skills",
    sourcePath: item.path ?? "",
    metadata,
  });
  if (promoteAction) {
    actions.push(promoteAction);
  }

  if (item.path) {
    actions.push({
      id: `reveal-${item.id}`,
      label: "Reveal source file",
      icon: "FolderOpen",
      type: "open-file",
      target: item.path,
    });
  }

  if (isManaged(item)) {
    actions.push(
      {
        id: `disable-${item.id}`,
        label: "Disable",
        icon: "Power",
        type: "run-mcp",
        target: `disable-skill:${item.id}`,
      },
      {
        id: `remove-${item.id}`,
        label: "Remove",
        icon: "Trash",
        type: "run-mcp",
        target: `remove-skill:${item.id}`,
        variant: "danger",
      },
    );
  }

  return actions;
}

export function summarizeSkillInventory(items: BrowseItem[]): SkillInventorySummary {
  return items.reduce<SkillInventorySummary>(
    (summary, item) => {
      const metadata = getMetadata(item);
      summary.total += 1;

      if (metadata.ownership === "external") {
        summary.external += 1;
      } else if (metadata.ownership === "adopted") {
        summary.adopted += 1;
      } else if (metadata.ownership === "user") {
        summary.user += 1;
      } else {
        summary.augur += 1;
      }

      if (parseBoolean(metadata.needsSetup)) {
        summary.needsSetup += 1;
      }

      return summary;
    },
    {
      total: 0,
      augur: 0,
      external: 0,
      adopted: 0,
      user: 0,
      needsSetup: 0,
    },
  );
}
