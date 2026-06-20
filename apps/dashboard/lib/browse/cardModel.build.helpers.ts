import type { BrowseItem, NoteSource, NoteTypeFilter, ViewMode } from "@/lib/browse/types";
import { getSkillIdentityTags, getSkillStateTags, type SkillTag } from "@/lib/browse/skill-card-ux";
import {
  classificationBadgesForItem,
  hasExplicitNoteClassificationSignal,
  noteClassificationForItem,
  noteDomainLabel,
  noteSourceLabel,
  noteStatusLabel,
} from "@/lib/browse/noteClassification";
import { overlayScope, overlayScopeLabel } from "@/lib/browse/overlay";
import { problemBadgesForItem, problemTagsForItem } from "@/lib/browse/problems";
import { formatTimeAgo } from "@/lib/timestamps";
import type {
  BrowseCardBadge,
  BrowseCardBadgeTone,
  BrowseCardDetailSection,
  BrowseCardMetadataRow,
  BrowseCardModel,
} from "./cardModel.types";
import { parseSkillDemos } from "./cardModel.demos";
import { splitMetadataList } from "./cardModel.shared";

function value(metadata: BrowseItem["metadata"], ...keys: string[]): string | undefined {
  for (const key of keys) {
    const candidate = metadata?.[key]?.trim();
    if (candidate) return candidate;
  }
  return undefined;
}

/**
 * Humanize an ISO/parseable timestamp into a relative label (e.g. "4d ago").
 * Falls back to the raw string when the value is not a parseable date, so
 * already-friendly values pass through untouched.
 */
function humanizeTimestamp(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  const parsed = Date.parse(raw);
  if (Number.isNaN(parsed)) return raw;
  return formatTimeAgo(parsed);
}

function boolLabel(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  const normalized = raw.toLowerCase();
  if (normalized === "true" || normalized === "1" || normalized === "yes") return "Yes";
  if (normalized === "false" || normalized === "0" || normalized === "no") return "No";
  return raw;
}

function titleCaseMetadata(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  return raw
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function enabledBadge(raw: string | undefined): BrowseCardBadge | undefined {
  const normalized = raw?.toLowerCase();
  if (normalized === "true" || normalized === "1" || normalized === "yes") {
    return { id: "enabled", label: "Enabled", tone: "success" };
  }
  if (normalized === "false" || normalized === "0" || normalized === "no") {
    return { id: "enabled", label: "Disabled", tone: "neutral" };
  }
  return undefined;
}

function qualityTone(tier: string | undefined): BrowseCardBadge["tone"] {
  if (tier === "A" || tier === "B") return "success";
  if (tier === "C") return "warning";
  if (tier === "D" || tier === "F") return "danger";
  return "neutral";
}

function qualityLabel(tier: string | undefined, score: string | undefined): string | undefined {
  if (!tier) return undefined;
  return score !== undefined && score !== "" ? `Quality ${tier} ${score}` : `Quality ${tier}`;
}

function kpiBadge(raw: string | undefined): BrowseCardBadge | undefined {
  if (raw === "pass") return { id: "kpi", label: "KPI ✓", tone: "success" };
  if (raw === "fail") return { id: "kpi", label: "KPI ✗", tone: "danger" };
  return undefined;
}

function addRow(rows: BrowseCardMetadataRow[], label: string, rowValue: string | undefined): void {
  if (rowValue) rows.push({ label, value: rowValue });
}

function addBadge(badges: BrowseCardBadge[], badge: BrowseCardBadge | undefined): void {
  if (badge?.label) badges.push(badge);
}

function statusTone(status: string | undefined): BrowseCardBadge["tone"] {
  const normalized = status?.toLowerCase() ?? "";
  if (normalized.includes("stale") || normalized.includes("error") || normalized.includes("fail")) {
    return "warning";
  }
  if (normalized === "enabled" || normalized === "running" || normalized === "configured" || normalized === "synced") {
    return "success";
  }
  return undefined;
}

function documentProviderLabel(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  const labels: Record<string, string> = {
    "google-drive": "Google Drive",
    "google-docs": "Google Docs",
    sharepoint: "SharePoint",
    onedrive: "OneDrive",
    filesystem: "Local folder",
  };
  return labels[raw] || raw;
}

function documentIndexStatusLabel(raw: string | undefined): string | undefined {
  const labels: Record<string, string> = {
    synced: "Synced",
    source_changed: "Source changed",
    summary_stale: "Summary stale",
    needs_access: "Needs access",
    not_indexed: "Not indexed",
    unassigned: "Unassigned",
  };
  return raw ? labels[raw] || raw : undefined;
}

function wikiMaintenanceStateLabel(raw: string | undefined): string | undefined {
  if (raw === "no-apply") return "no apply";
  if (raw === "status-error") return "status error";
  return raw ? raw.replace(/[_-]+/g, " ") : undefined;
}

function wikiMaintenanceTone(raw: string | undefined): BrowseCardBadgeTone | undefined {
  if (raw === "current") return "success";
  if (raw === "no-apply" || raw === "status-error") return "warning";
  if (raw) return "info";
  return undefined;
}

function positiveCountLabel(raw: string | undefined, noun: string): string | undefined {
  const count = Number(raw);
  if (!Number.isFinite(count) || count <= 0) return undefined;
  return `${count} ${noun}`;
}

const OVERLAY_TONES: Record<"packet" | "private" | "shared", BrowseCardBadge["tone"]> = {
  packet: "warning",
  private: "info",
  shared: "success",
};

function section(id: string, title: string, rows: BrowseCardMetadataRow[]): BrowseCardDetailSection[] {
  return rows.length > 0 ? [{ id, title, rows }] : [];
}

function badgeId(prefix: string, label: string): string {
  return `${prefix}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
}

function addUniqueBadge(badges: BrowseCardBadge[], badge: BrowseCardBadge | undefined): void {
  if (!badge?.label) return;
  if (badges.some((existing) => existing.id === badge.id)) return;
  badges.push(badge);
}

function addUniqueRow(rows: BrowseCardMetadataRow[], label: string, rowValue: string | undefined): void {
  if (!rowValue) return;
  if (rows.some((row) => row.label === label && row.value === rowValue)) return;
  rows.push({ label, value: rowValue });
}

function normalizedDisplayValue(raw: string | undefined): string {
  return raw?.trim().toLowerCase() ?? "";
}

function displayableTypeBadge(raw: string | undefined): raw is string {
  const normalized = normalizedDisplayValue(raw);
  return Boolean(raw && !["unknown", "rag"].includes(normalized));
}

function displayableTag(raw: string | undefined): raw is string {
  const normalized = normalizedDisplayValue(raw);
  return Boolean(raw && normalized !== "rag");
}

function mergeRows(...groups: BrowseCardMetadataRow[][]): BrowseCardMetadataRow[] {
  const rows: BrowseCardMetadataRow[] = [];
  for (const group of groups) {
    for (const row of group) addUniqueRow(rows, row.label, row.value);
  }
  return rows;
}

function mergeBadges(...groups: BrowseCardBadge[][]): BrowseCardBadge[] {
  const badges: BrowseCardBadge[] = [];
  for (const group of groups) {
    for (const badge of group) addUniqueBadge(badges, badge);
  }
  return badges;
}

function commonTags(item: BrowseItem): string[] {
  const metadata = item.metadata;
  const pageTags = splitMetadataList(metadata?.pageTags);
  if (pageTags.length > 0) return pageTags;
  return item.tags ?? [];
}

function skillTags(item: BrowseItem): string[] {
  return splitMetadataList(item.metadata?.skillTags);
}

const NOTE_TYPE_ICONS: Record<NoteTypeFilter, string> = {
  url: "Link",
  file: "FileText",
  thought: "Lightbulb",
  "voice-memo": "Mic",
  meeting: "Users",
  image: "Image",
  prompt: "MessageSquare",
};

const NOTE_TYPE_TONES: Record<NoteTypeFilter, BrowseCardBadgeTone> = {
  url: "note-url",
  file: "note-file",
  thought: "note-thought",
  "voice-memo": "note-voice-memo",
  meeting: "note-meeting",
  image: "note-image",
  prompt: "note-prompt",
};

function commonSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const rows: BrowseCardMetadataRow[] = [];
  const badges: BrowseCardBadge[] = [];

  if (displayableTypeBadge(item.typeBadge)) {
    addUniqueBadge(badges, { id: "type", label: item.typeBadge, tone: "neutral" });
    addUniqueRow(rows, "Type", item.typeBadge);
  }

  // ADR-772: federated records carry their owning brain. Badge + detail row
  // (rule 32) so cross-brain views are visibly attributed by brain.
  const brainId = value(metadata, "brain_id", "brainId");
  if (brainId) {
    addUniqueBadge(badges, { id: "brain", label: brainId, tone: "info", icon: "Layers" });
    addUniqueRow(rows, "Brain", brainId);
  }

  const scope = overlayScope(metadata);
  if (scope) {
    const label = overlayScopeLabel(scope);
    addUniqueBadge(badges, { id: `overlay-${scope}`, label, tone: OVERLAY_TONES[scope] });
    addUniqueRow(rows, "Scope", label);
  }

  const status = value(metadata, "status");
  addUniqueBadge(badges, status ? { id: "status", label: status, tone: statusTone(status) } : undefined);
  addUniqueRow(rows, "Status", status);

  const enabled = value(metadata, "enabled");
  addUniqueBadge(badges, enabledBadge(enabled));
  addUniqueRow(rows, "Enabled", boolLabel(enabled));

  const qualityTier = value(metadata, "qualityTier", "quality_tier");
  const qualityScore = value(metadata, "qualityScore", "quality_score");
  const quality = qualityLabel(qualityTier, qualityScore);
  addUniqueBadge(badges, quality ? { id: "quality", label: quality, tone: qualityTone(qualityTier) } : undefined);
  addUniqueRow(rows, "Quality", quality);
  addUniqueRow(rows, "Docs", value(metadata, "docsScore", "docs_score"));
  addUniqueRow(rows, "Wiring", value(metadata, "wiringScore", "wiring_score"));

  const kpiStatus = value(metadata, "kpiStatus", "kpi_status");
  addUniqueBadge(badges, kpiBadge(kpiStatus));
  if (kpiStatus && kpiStatus !== "untested") addUniqueRow(rows, "KPI", kpiStatus);

  const problemTags = problemTagsForItem(item);
  for (const badge of problemBadgesForItem(item)) {
    addUniqueBadge(badges, badge);
  }
  if (problemTags.length > 0) {
    addUniqueRow(rows, "Problems", String(problemTags.length));
  }

  const kind = value(metadata, "kind");
  addUniqueBadge(badges, kind ? { id: "kind", label: kind, tone: "neutral" } : undefined);
  addUniqueRow(rows, "Kind", kind);

  const source = value(metadata, "source_domain", "sourceDomain", "source", "source_root", "sourceRoot");
  addUniqueRow(rows, "Source", source);

  const enrichment = value(metadata, "enrichment_status", "enrichmentStatus", "x-augur-enrichment-status");
  addUniqueBadge(
    badges,
    enrichment
      ? {
        id: "enrichment",
        label: enrichment,
        tone: enrichment === "enriched" ? "success" : enrichment === "raw" ? "neutral" : "warning",
      }
      : undefined,
  );
  addUniqueRow(rows, "Enrichment", enrichment);

  const modified = value(metadata, "modified", "updated", "lastModified");
  addUniqueRow(rows, "Modified", humanizeTimestamp(modified));

  for (const tag of commonTags(item).filter(displayableTag).slice(0, 6)) {
    addUniqueBadge(badges, { id: badgeId("tag", tag), label: tag, tone: "info" });
    addUniqueRow(rows, "Tag", tag);
  }

  for (const tag of skillTags(item).filter(displayableTag).slice(0, 6)) {
    addUniqueBadge(badges, { id: badgeId("skill-tag", tag), label: tag, tone: "info" });
    addUniqueRow(rows, "Tag", tag);
  }

  return { badges, metadataRows: rows, detailSections: section("signals", "Signals", rows) };
}

function isNoteTypeFilter(value: string): value is NoteTypeFilter {
  return value in NOTE_TYPE_TONES;
}

function noteClassificationBadge(badge: { id: string; label: string; icon?: string }): BrowseCardBadge {
  const noteType = badge.id.startsWith("note-type-")
    ? badge.id.replace(/^note-type-/, "")
    : "";
  if (isNoteTypeFilter(noteType)) {
    return {
      ...badge,
      tone: NOTE_TYPE_TONES[noteType],
      icon: NOTE_TYPE_ICONS[noteType] ?? badge.icon,
    };
  }
  if (badge.id === "note-needs-classification") {
    return { ...badge, tone: "warning", icon: badge.icon ?? "AlertTriangle" };
  }
  return { ...badge, tone: "info" };
}

function noteMetadataUrl(metadata: BrowseItem["metadata"]): string | undefined {
  return value(metadata, "canonical_url", "canonicalUrl", "url", "source_url", "sourceUrl");
}

function metadataBool(raw: string | undefined): boolean {
  const normalized = raw?.trim().toLowerCase();
  return normalized === "true" || normalized === "1" || normalized === "yes";
}

function genericRecordSource(metadata: BrowseItem["metadata"]): string | undefined {
  return value(metadata, "source", "source_root", "sourceRoot");
}

function sourceLabelForProvenance(classificationSource: NoteSource | null): string | undefined {
  if (!classificationSource) return undefined;
  return noteSourceLabel(classificationSource);
}

function addProvenanceRow(
  rows: BrowseCardMetadataRow[],
  metadata: BrowseItem["metadata"],
  classificationSource: NoteSource | null,
): void {
  const provenance = genericRecordSource(metadata);
  const classificationSourceLabel = sourceLabelForProvenance(classificationSource);
  if (!provenance || provenance === classificationSource || provenance === classificationSourceLabel) return;
  addUniqueRow(rows, "Provenance", provenance);
}

function shouldUseNoteClassificationSlots(item: BrowseItem): boolean {
  return hasExplicitNoteClassificationSignal(item);
}

function noteClassificationSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const rows: BrowseCardMetadataRow[] = [];
  const badges: BrowseCardBadge[] = [];

  const classificationBadges = classificationBadgesForItem(item);
  const needsClassification = metadataBool(value(metadata, "needsClassification"));
  const hasNeedsClassificationBadge = classificationBadges.some((badge) => badge.id === "note-needs-classification");
  if (needsClassification && !hasNeedsClassificationBadge) {
    classificationBadges.push({
      id: "note-needs-classification",
      label: "Needs classification",
      icon: "AlertTriangle",
    });
  }

  for (const badge of classificationBadges) {
    addUniqueBadge(badges, noteClassificationBadge(badge));
  }

  const classification = noteClassificationForItem(item);
  if (classification.noteType) {
    const typeBadge = classificationBadges.find((badge) => badge.id.startsWith("note-type-"));
    addUniqueRow(rows, "Type", typeBadge?.label);
  }
  if (classification.domain) {
    addUniqueRow(rows, "Domain", noteDomainLabel(classification.domain));
  }
  if (classification.source) {
    addUniqueRow(rows, "Source", noteSourceLabel(classification.source));
  }
  if (classification.status) {
    addUniqueRow(rows, "Status", noteStatusLabel(classification.status));
  }
  addUniqueRow(rows, "Confidence", classification.classificationConfidence ?? undefined);
  addUniqueRow(rows, "Source domain", value(metadata, "source_domain", "sourceDomain"));
  addProvenanceRow(rows, metadata, classification.source);
  addUniqueRow(rows, "URL", noteMetadataUrl(metadata));

  const problemTags = problemTagsForItem(item);
  for (const badge of problemBadgesForItem(item)) {
    addUniqueBadge(badges, badge);
  }
  if (problemTags.length > 0) {
    addUniqueRow(rows, "Problems", String(problemTags.length));
  }

  // ADR-772: federated records carry their owning brain. Badge + detail row
  // (rule 32) so cross-brain views are visibly attributed by brain.
  const brainId = value(metadata, "brain_id", "brainId");
  if (brainId) {
    addUniqueBadge(badges, { id: "brain", label: brainId, tone: "info", icon: "Layers" });
    addUniqueRow(rows, "Brain", brainId);
  }

  const scope = overlayScope(metadata);
  if (scope) {
    const label = overlayScopeLabel(scope);
    addUniqueBadge(badges, { id: `overlay-${scope}`, label, tone: OVERLAY_TONES[scope] });
    addUniqueRow(rows, "Scope", label);
  }

  const enrichment = value(metadata, "enrichment_status", "enrichmentStatus", "x-augur-enrichment-status");
  addUniqueBadge(
    badges,
    enrichment
      ? {
        id: "enrichment",
        label: enrichment,
        tone: enrichment === "enriched" ? "success" : enrichment === "raw" ? "neutral" : "warning",
      }
      : undefined,
  );
  addUniqueRow(rows, "Enrichment", enrichment);

  const modified = value(metadata, "modified", "updated", "lastModified");
  addUniqueRow(rows, "Modified", humanizeTimestamp(modified));

  for (const tag of commonTags(item).filter(displayableTag).slice(0, 6)) {
    addUniqueBadge(badges, { id: badgeId("tag", tag), label: tag, tone: "info" });
    addUniqueRow(rows, "Tag", tag);
  }

  for (const tag of skillTags(item).filter(displayableTag).slice(0, 6)) {
    addUniqueBadge(badges, { id: badgeId("skill-tag", tag), label: tag, tone: "info" });
    addUniqueRow(rows, "Tag", tag);
  }

  return { badges, metadataRows: rows, detailSections: section("signals", "Signals", rows) };
}

function skillTagBadges(item: BrowseItem): BrowseCardBadge[] {
  return [...getSkillIdentityTags(item), ...getSkillStateTags(item)].map((tag) => ({
    id: tag.key,
    label: tag.label,
    tone: tag.tone,
  }));
}

function skillTagRowLabel(tag: SkillTag): string {
  if (tag.key === "hub") return "Hub";
  if (tag.key.startsWith("overlay-")) return "Scope";
  if (tag.key === "ownership") return "Ownership";
  if (tag.key.startsWith("client-")) return "Client";
  if (tag.key === "skill-type") return "Skill type";
  if (tag.key === "enabled") return "State";
  if (tag.key === "needs-setup") return "Setup";
  if (tag.key === "coverage") return "Coverage";
  if (tag.key === "quality") return "Quality";
  if (tag.key === "update") return "Update";
  if (tag.key === "tools") return "Tools";
  if (tag.key === "actions") return "Actions";
  if (tag.key === "pages") return "Pages";
  if (tag.title) return tag.title;
  return tag.label;
}

function skillTagRows(item: BrowseItem): BrowseCardMetadataRow[] {
  return [...getSkillIdentityTags(item), ...getSkillStateTags(item)].map((tag) => ({
    label: skillTagRowLabel(tag),
    value: tag.label,
  }));
}

function skillSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const capability = value(metadata, "capabilityId", "capability");
  const common = commonSlots(item);

  const badges = mergeBadges(skillTagBadges(item), common.badges);
  addBadge(badges, capability ? { id: "capability", label: capability } : undefined);

  const metadataRows = mergeRows(skillTagRows(item), common.metadataRows);
  addRow(metadataRows, "Capability", capability);

  // Rule 32: demo runbooks ride the owning skill's card as a badge + row.
  const demos = parseSkillDemos(value(metadata, "demos"));
  if (demos.length > 0) {
    addBadge(badges, {
      id: "demos",
      label: `${demos.length} demo${demos.length === 1 ? "" : "s"}`,
      tone: "info",
    });
    addRow(metadataRows, "Demos", String(demos.length));
  }

  return { badges, metadataRows, detailSections: section("skills", "Skill signals", metadataRows) };
}

function driftBadge(drift: string | undefined): BrowseCardBadge | undefined {
  if (!drift || drift === "unknown") return undefined;
  switch (drift) {
    case "in-sync":
      return { id: "drift", label: "in sync", tone: "success" };
    case "codex-edited":
      return { id: "drift", label: "codex-edited", tone: "warning" };
    case "cloud-edited":
      return { id: "drift", label: "cloud-edited", tone: "warning" };
    case "cloud-deleted":
      return { id: "drift", label: "cloud-deleted", tone: "danger" };
    case "augur-managed-but-removed":
      return { id: "drift", label: "seed removed", tone: "warning" };
    case "seed-evolved":
      return { id: "drift", label: "seed-evolved", tone: "warning" };
    case "external":
      return { id: "drift", label: "manual", tone: "info" };
    default:
      return { id: "drift", label: drift, tone: "neutral" };
  }
}

function ownerBadge(managedBy: string | undefined): BrowseCardBadge | undefined {
  if (!managedBy || managedBy === "unknown") return undefined;
  if (managedBy === "augur") return { id: "owner", label: "augur", tone: "info" };
  if (managedBy === "manual") return { id: "owner", label: "manual", tone: "neutral" };
  return { id: "owner", label: managedBy, tone: "neutral" };
}

function routineSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const cadence = value(metadata, "cadence");
  const status = value(metadata, "status");
  const managedBy = value(metadata, "managed_by");
  const drift = value(metadata, "drift_status");
  const rows: BrowseCardMetadataRow[] = [];
  addRow(rows, "Cadence", cadence);
  addRow(rows, "Status", status);
  addRow(rows, "Managed by", managedBy);
  addRow(rows, "Drift", drift);
  const cacheFetchedAt = value(metadata, "cacheFetchedAt");
  addRow(rows, "Cache", cacheFetchedAt ? `fetched ${cacheFetchedAt}` : undefined);
  addRow(rows, "Next run", value(metadata, "nextRun"));
  addRow(rows, "Last run", value(metadata, "lastRun"));
  addRow(rows, "Tokens", value(metadata, "tokenCost", "token_cost"));
  addRow(rows, "Tokens/run", value(metadata, "tokensPerRun"));
  addRow(rows, "Tokens/day", value(metadata, "tokensPerDay"));

  const badges: BrowseCardBadge[] = [];
  addBadge(badges, cadence ? { id: "cadence", label: cadence } : undefined);
  addBadge(badges, status ? { id: "status", label: status, tone: statusTone(status) } : undefined);
  addBadge(badges, ownerBadge(managedBy));
  addBadge(badges, driftBadge(drift));

  const common = commonSlots(item);
  const mergedRows = mergeRows(rows, common.metadataRows);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergedRows,
    detailSections: section("background-routines", "Routine signals", mergedRows),
  };
}

function mcpServerSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const runtime = value(metadata, "runtimeStatus", "status");
  const tier = value(metadata, "tier") ?? item.typeBadge;
  const clients = value(metadata, "clients", "runningClients");
  const rows: BrowseCardMetadataRow[] = [];
  addRow(rows, "Runtime", runtime);
  addRow(rows, "Tier", tier);
  addRow(rows, "Clients", clients);
  addRow(rows, "PID", value(metadata, "pid", "runtimePids"));
  addRow(rows, "Manifest", value(metadata, "manifestPath", "source_path") ?? item.path);
  addRow(rows, "Bundle", value(metadata, "bundle"));

  const badges: BrowseCardBadge[] = [];
  addBadge(badges, runtime ? { id: "runtimeStatus", label: runtime, tone: statusTone(runtime) } : undefined);
  addBadge(badges, tier ? { id: "tier", label: tier } : undefined);
  addBadge(badges, clients ? { id: "clients", label: clients } : undefined);

  const common = commonSlots(item);
  const mergedRows = mergeRows(rows, common.metadataRows);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergedRows,
    detailSections: section("mcp-servers", "MCP server signals", mergedRows),
  };
}

function apiRouteSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const methods = value(metadata, "method", "methods") ?? item.typeBadge;
  const route = value(metadata, "route") ?? item.id;
  const source = value(metadata, "source_path") ?? item.path;
  const rows: BrowseCardMetadataRow[] = [];
  addRow(rows, "Method", methods);
  addRow(rows, "Route", route);
  addRow(rows, "Source", source);

  const badges: BrowseCardBadge[] = [];
  addBadge(badges, methods ? { id: "methods", label: methods } : undefined);

  const common = commonSlots(item);
  const mergedRows = mergeRows(rows, common.metadataRows);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergedRows,
    detailSections: section("api-routes", "API route signals", mergedRows),
  };
}

function documentSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const provider = value(metadata, "provider");
  const status = value(metadata, "indexStatus", "index_status");
  const attached = splitMetadataList(value(metadata, "attachedBrainIds", "attached_brain_ids"));
  const providerLabel = documentProviderLabel(provider);
  const statusLabel = documentIndexStatusLabel(status);
  const rows: BrowseCardMetadataRow[] = [];
  const badges: BrowseCardBadge[] = [];

  addUniqueBadge(badges, {
    id: "document-provider",
    label: providerLabel || "",
    tone: provider === "filesystem" ? "neutral" : "info",
  });
  addUniqueBadge(badges, {
    id: "document-index-status",
    label: statusLabel || "",
    tone: status === "synced" ? "success" : status ? "warning" : undefined,
  });
  if (attached.length > 1) {
    addUniqueBadge(badges, { id: "document-attachments", label: `${attached.length} folders`, tone: "info" });
  } else if (attached.length === 1) {
    addUniqueBadge(badges, { id: "document-attachments", label: attached[0], tone: "info" });
  }

  addUniqueRow(rows, "Attached to", attached.join(", "));
  addUniqueRow(rows, "Provider", providerLabel);
  addUniqueRow(rows, "Index status", statusLabel);
  addUniqueRow(rows, "Remote revision", value(metadata, "remoteRevision", "remote_revision"));
  addUniqueRow(rows, "Indexed revision", value(metadata, "indexedRevision", "indexed_revision"));

  // Source section — rows for canonical_url, source_url; only shown when present.
  const canonicalUrl = value(metadata, "canonical_url", "canonicalUrl");
  const sourceUrl = value(metadata, "source_url", "sourceUrl");
  const sourceRows: BrowseCardMetadataRow[] = [];
  addUniqueRow(sourceRows, "Canonical URL", canonicalUrl);
  addUniqueRow(sourceRows, "Source URL", sourceUrl);

  const common = commonSlots(item);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergeRows(rows, common.metadataRows),
    detailSections: [
      ...section("document-sync", "Document Sync", rows),
      ...section("document-source", "Source", sourceRows),
      ...common.detailSections,
    ],
  };
}

function wikiSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const state = value(metadata, "wikiMaintenanceState");
  const stateLabel = wikiMaintenanceStateLabel(state);
  const pending = value(metadata, "wikiPendingSources");
  const total = value(metadata, "wikiSourceTotal");
  const lastChecked = value(metadata, "wikiMaintenanceCheckedAt");
  const lastReindexed = value(metadata, "wikiLastReindexedAt");
  const batchQuality = value(metadata, "wikiLastBatchQuality");
  const batchReason = value(metadata, "wikiLastBatchReason");

  const rows: BrowseCardMetadataRow[] = [];
  addUniqueRow(rows, "Maintenance", titleCaseMetadata(stateLabel));
  addUniqueRow(rows, "Pending sources", pending ? (total ? `${pending} / ${total}` : pending) : undefined);
  addUniqueRow(rows, "Last checked", humanizeTimestamp(lastChecked));
  addUniqueRow(rows, "Last reindexed", humanizeTimestamp(lastReindexed));
  addUniqueRow(rows, "Batch quality", titleCaseMetadata(batchQuality));
  addUniqueRow(rows, "Batch reason", batchReason);

  const badges: BrowseCardBadge[] = [];
  addUniqueBadge(badges, stateLabel ? {
    id: "wiki-maintenance",
    label: stateLabel,
    tone: wikiMaintenanceTone(state),
  } : undefined);
  addUniqueBadge(badges, pending ? {
    id: "wiki-pending",
    label: positiveCountLabel(pending, "pending") || pending,
    tone: "neutral",
  } : undefined);
  addUniqueBadge(badges, lastReindexed ? {
    id: "wiki-reindexed",
    label: "reindexed",
    tone: "success",
  } : undefined);
  addUniqueBadge(badges, batchQuality ? {
    id: "wiki-batch-quality",
    label: `batch ${batchQuality}`,
    tone: batchQuality === "weak" ? "warning" : "info",
  } : undefined);

  const common = commonSlots(item);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergeRows(rows, common.metadataRows),
    detailSections: [
      ...section("wiki-maintenance", "Wiki Maintenance", rows),
      ...common.detailSections,
    ],
  };
}

function agentProfileSlots(item: BrowseItem): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  const metadata = item.metadata;
  const master = value(metadata, "master_client", "masterClient", "x-augur-master");
  const sourceModel = value(metadata, "source_model", "sourceModel") ?? value(metadata, "model");
  const sourceTier = value(metadata, "source_tier", "sourceTier");
  const codexModel = value(metadata, "codex_model", "codexModel");
  const codexSync = value(metadata, "codex_sync_status", "codexSyncStatus");
  const codexProfile = value(metadata, "codex_profile_path", "codexProfilePath");
  const mode = value(metadata, "mode");

  const rows: BrowseCardMetadataRow[] = [];
  addRow(rows, "Master", master);
  addRow(rows, "Source model", sourceModel);
  addRow(rows, "Source tier", sourceTier);
  addRow(rows, "Codex model", codexModel);
  addRow(rows, "Codex sync", codexSync);
  addRow(rows, "Codex profile", codexProfile);
  addRow(rows, "Mode", mode);

  const badges: BrowseCardBadge[] = [];
  addBadge(badges, sourceTier ? { id: "agent-source-tier", label: `source ${sourceTier}`, tone: "info" } : undefined);
  addBadge(badges, codexModel ? { id: "agent-codex-model", label: `codex ${codexModel}`, tone: "success" } : undefined);
  addBadge(badges, codexSync ? { id: "agent-codex-sync", label: `codex ${codexSync}`, tone: statusTone(codexSync) } : undefined);

  const common = commonSlots(item);
  const mergedRows = mergeRows(rows, common.metadataRows);
  return {
    badges: mergeBadges(badges, common.badges),
    metadataRows: mergedRows,
    detailSections: section("agent-profiles", "Agent projection", mergedRows),
  };
}

export function slotsFor(item: BrowseItem, viewMode: ViewMode): Pick<BrowseCardModel, "badges" | "metadataRows" | "detailSections"> {
  switch (viewMode) {
    case "notes":
      return shouldUseNoteClassificationSlots(item) ? noteClassificationSlots(item) : commonSlots(item);
    case "skills":
      return skillSlots(item);
    case "documents":
      return documentSlots(item);
    case "wiki":
      return wikiSlots(item);
    case "agent-profiles":
      return agentProfileSlots(item);
    case "background-routines":
      return routineSlots(item);
    case "mcp-servers":
      return mcpServerSlots(item);
    case "api-routes":
      return apiRouteSlots(item);
    default:
      return commonSlots(item);
  }
}
