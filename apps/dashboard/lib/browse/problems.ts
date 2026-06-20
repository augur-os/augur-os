import type { BrowseCardBadge } from "./cardModel";
import type { ActiveFolderContext } from "./folderContext";

export interface ProblemMetadataItem {
  id?: string;
  title: string;
  description?: string;
  hub?: string;
  typeBadge?: string;
  path?: string;
  primaryAction?: { target?: string };
  metadata?: Record<string, string>;
}

export type BrowseProblemSeverity = "info" | "warning" | "danger";

export interface BrowseProblemEvidence {
  id: string;
  severity?: BrowseProblemSeverity;
  reason?: string;
  source_path?: string;
  related_paths?: string[];
}

export const PROBLEM_LABELS: Record<string, string> = {
  permission_denied: "Permission denied",
  unreadable: "Unreadable",
  unknown_source: "Unknown source",
  low_confidence: "Low confidence",
  duplicate: "Duplicate",
  stale_generated: "Stale generated",
  conflicting_instruction: "Conflicting instruction",
  missing_mcp_config: "Missing MCP config",
};

const ALLOWED_PROBLEM_SEVERITIES = new Set<BrowseProblemSeverity>(["info", "warning", "danger"]);

const PROBLEM_SEVERITY: Record<string, BrowseProblemSeverity> = {
  permission_denied: "danger",
  unreadable: "danger",
  unknown_source: "warning",
  low_confidence: "warning",
  duplicate: "warning",
  stale_generated: "warning",
  conflicting_instruction: "warning",
  missing_mcp_config: "info",
};

function humanizeProblemId(id: string): string {
  return id
    .replace(/[-_]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/^./, (char) => char.toUpperCase());
}

function problemLabel(id: string): string {
  return PROBLEM_LABELS[id] ?? humanizeProblemId(id);
}

function safeSeverity(value: unknown): BrowseProblemSeverity | undefined {
  return typeof value === "string" && ALLOWED_PROBLEM_SEVERITIES.has(value as BrowseProblemSeverity)
    ? value as BrowseProblemSeverity
    : undefined;
}

function severityForProblem(id: string, evidence?: BrowseProblemEvidence): BrowseProblemSeverity {
  return safeSeverity(evidence?.severity) ?? PROBLEM_SEVERITY[id] ?? "warning";
}

function splitProblemTags(raw: string | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => {
      if (!tag || seen.has(tag)) return false;
      seen.add(tag);
      return true;
    });
}

function fallbackEvidenceFromTags(item: ProblemMetadataItem): BrowseProblemEvidence[] {
  return problemTagsForItem(item).map((id) => ({ id, severity: PROBLEM_SEVERITY[id] ?? "warning" }));
}

function isEvidenceRecord(value: unknown): value is BrowseProblemEvidence {
  return Boolean(value && typeof value === "object" && typeof (value as BrowseProblemEvidence).id === "string");
}

function pathForItem(item: ProblemMetadataItem): string {
  return item.metadata?.source_path || item.metadata?.relative_path || item.path || item.primaryAction?.target || "";
}

function metadataValue(item: ProblemMetadataItem, ...keys: string[]): string {
  for (const key of keys) {
    const value = item.metadata?.[key]?.trim();
    if (value) return value;
  }
  return "";
}

export function problemTagsForItem(item: ProblemMetadataItem): string[] {
  return splitProblemTags(item.metadata?.problem_tags);
}

export function problemEvidenceForItem(item: ProblemMetadataItem): BrowseProblemEvidence[] {
  const raw = item.metadata?.problem_evidence;
  if (!raw) return fallbackEvidenceFromTags(item);
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return fallbackEvidenceFromTags(item);
    const records = parsed.filter(isEvidenceRecord);
    return records.length > 0 ? records : fallbackEvidenceFromTags(item);
  } catch {
    return fallbackEvidenceFromTags(item);
  }
}

function completeProblemEvidenceForItem(item: ProblemMetadataItem): BrowseProblemEvidence[] {
  const evidence = problemEvidenceForItem(item);
  const evidenceById = new Map(evidence.map((record) => [record.id, record]));
  return problemTagsForItem(item).map((id) => evidenceById.get(id) ?? {
    id,
    severity: PROBLEM_SEVERITY[id] ?? "warning",
    reason: "No detailed evidence was provided for this problem tag.",
  });
}

export function problemBadgesForItem(item: ProblemMetadataItem): BrowseCardBadge[] {
  const evidenceById = new Map(problemEvidenceForItem(item).map((evidence) => [evidence.id, evidence]));
  return problemTagsForItem(item).map((id) => ({
    id: `problem-${id}`,
    label: problemLabel(id),
    tone: severityForProblem(id, evidenceById.get(id)),
  }));
}

export function problemDetailRowsForItem(item: ProblemMetadataItem): Array<{ label: string; value: string }> {
  return completeProblemEvidenceForItem(item).map((evidence) => {
    const parts = [
      evidence.reason,
      evidence.source_path ? `Source: ${evidence.source_path}` : undefined,
      evidence.related_paths?.length ? `Related: ${evidence.related_paths.join(", ")}` : undefined,
    ].filter((part): part is string => Boolean(part));
    return {
      label: problemLabel(evidence.id),
      value: parts.join(" ") || evidence.id,
    };
  });
}

export function buildProblemFilterOptions(items: ProblemMetadataItem[]): Array<{ id: string; label: string }> {
  const counts = new Map<string, number>();
  for (const item of items) {
    for (const tag of problemTagsForItem(item)) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  }
  return [...counts.entries()].map(([id, count]) => ({ id, label: `${problemLabel(id)} (${count})` }));
}

export function itemMatchesProblemFilter(item: ProblemMetadataItem, filter: string | null): boolean {
  if (!filter) return true;
  return problemTagsForItem(item).includes(filter);
}

export function hasInventoryProblemMetadata(item: ProblemMetadataItem): boolean {
  if (problemTagsForItem(item).length === 0) return false;
  const metadata = item.metadata ?? {};
  if (metadata.inventory_source === "ai-artifact-inventory") return true;
  return Boolean(
    (metadata.artifact_type || metadata.artifactType) &&
      (metadata.client || metadata.vendor || metadata.classification || metadata.confidence),
  );
}

export function buildProblemPrompt(
  item: ProblemMetadataItem,
  activeFolderContext?: ActiveFolderContext | null,
): string {
  const problemRows = problemDetailRowsForItem(item);
  const problemLines = problemRows.length > 0
    ? problemRows.map((row) => `- ${row.label}: ${row.value}`).join("\n")
    : problemTagsForItem(item).map((id) => `- ${problemLabel(id)}`).join("\n");

  return [
    "Review this Augur AI artifact inventory item and prepare safe next steps.",
    "",
    "Context:",
    `- Folder: ${activeFolderContext?.label || "All Brains"}`,
    `- Brain: ${activeFolderContext?.brain_id || metadataValue(item, "brain_id", "brainId")}`,
    `- Project root: ${activeFolderContext?.project_root || metadataValue(item, "project_root", "projectRoot")}`,
    "",
    "Artifact:",
    `- Title: ${item.title}`,
    `- Path: ${pathForItem(item)}`,
    `- Brain: ${metadataValue(item, "brain_id", "brainId")}`,
    `- Project: ${metadataValue(item, "project_root", "projectRoot")}`,
    `- Type: ${metadataValue(item, "artifact_type", "artifactType") || item.typeBadge || ""}`,
    `- Client/vendor: ${metadataValue(item, "client")}/${metadataValue(item, "vendor")}`,
    "",
    "Problems:",
    problemLines || "- None",
    "",
    "Constraints:",
    "- Do not modify, adopt, sync, rewrite, delete, or project files until I approve.",
  ].join("\n");
}
