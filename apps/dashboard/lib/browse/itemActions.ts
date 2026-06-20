import type { ItemActionDef } from "./itemActionSchema";
import type { ActiveFolderContext } from "./folderContext";
import type { BrowseItem } from "./types";
import {
  hasExplicitNoteClassificationSignal,
  noteClassificationForItem,
  noteDomainLabel,
  noteSourceLabel,
  noteStatusLabel,
} from "./noteClassification";
import { buildProblemPrompt, hasInventoryProblemMetadata } from "./problems";

export interface AiItemActionItem {
  id?: string;
  title: string;
  path?: string;
  hub?: string;
  typeBadge?: string;
  metadata?: Record<string, string>;
}

export interface AiItemAction {
  id: string;
  label: string;
  icon: string;
  template: (item: AiItemActionItem) => string;
}

export interface AiItemActionOptions {
  activeFolderContext?: ActiveFolderContext | null;
}

export type DirectItemAction = ItemActionDef & { kind: "direct" };
export type GeneratedItemAction = ItemActionDef;

const PLACEHOLDER_PATTERN = /\{\{?(title|path|id|hub|metadata\.[A-Za-z0-9_]+)\}?\}/g;

function loadGeneratedItemActions(): Record<string, ItemActionDef[]> {
  try {
    // The generated module is intentionally gitignored. Clean checkouts may
    // import this file before generation; keep Browse loadable until prebuild
    // or Jest setup writes the registry.
    const generated = require("./generated-item-actions") as {
      GENERATED_ITEM_ACTIONS?: Record<string, ItemActionDef[]>;
    };
    return generated.GENERATED_ITEM_ACTIONS ?? {};
  } catch {
    return {};
  }
}

const GENERATED_ITEM_ACTIONS = loadGeneratedItemActions();

function normalizedNoteType(item: AiItemActionItem): string {
  const raw = (
    item.metadata?.["x-augur-note-type"] ||
    item.metadata?.noteType ||
    item.metadata?.note_type ||
    item.typeBadge ||
    "thought"
  )
    .toLowerCase()
    .replace(/[\s_]+/g, "-");
  if (raw === "audio" || raw === "voice") return "voice-memo";
  return raw;
}

function normalizeFileExtension(value: string): string {
  return value.trim().toLowerCase().replace(/^\./, "");
}

function itemFileExtension(item: AiItemActionItem): string {
  const fromMeta = item.metadata?.file_ext || item.metadata?.fileType || item.metadata?.format;
  if (fromMeta) return normalizeFileExtension(fromMeta);
  const path = item.path || "";
  const base = path.split(/[\\/]/).pop() || "";
  const idx = base.lastIndexOf(".");
  return idx > 0 ? normalizeFileExtension(base.slice(idx + 1)) : "";
}

function mediaKindForExtension(extension: string): string {
  if (["aac", "flac", "m4a", "mp3", "ogg", "wav"].includes(extension)) return "audio";
  if (["mov", "mp4", "webm"].includes(extension)) return "video";
  if (["avif", "gif", "heic", "jpeg", "jpg", "png", "tif", "tiff", "webp"].includes(extension)) return "image";
  return "";
}

function itemMediaKind(item: AiItemActionItem): string {
  const fromMeta = item.metadata?.media_kind || item.metadata?.mediaKind || item.metadata?.document_kind || "";
  const normalized = fromMeta.trim().toLowerCase().replace(/[\s_]+/g, "-");
  return normalized || mediaKindForExtension(itemFileExtension(item));
}

const SHARED_DOCUMENT_PROVIDERS = new Set([
  "google-drive",
  "google-docs",
  "sharepoint",
  "onedrive",
  "github",
  "notion",
  "confluence",
  "shared-folder",
]);
const PERSONAL_DOCUMENT_SOURCE_IDS = new Set(["documents", "desktop", "downloads"]);

function metadataValue(metadata: Record<string, string>, ...keys: string[]): string {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function isSharedProjectDocumentCatalogItem(item: AiItemActionItem): boolean {
  const metadata = item.metadata ?? {};
  const provider = metadataValue(metadata, "provider").toLowerCase();
  const sourceId = metadataValue(metadata, "source_id", "sourceId").toLowerCase();
  const sourceType = metadataValue(metadata, "source_type", "sourceType").toLowerCase();
  const identity = metadataValue(
    metadata,
    "remote_id",
    "remoteId",
    "canonical_document_id",
    "canonicalDocumentId",
    "source_relative_path",
    "sourceRelativePath",
  );

  if (!SHARED_DOCUMENT_PROVIDERS.has(provider)) return false;
  if (sourceId && PERSONAL_DOCUMENT_SOURCE_IDS.has(sourceId)) return false;
  if (sourceType && sourceType !== "shared") return false;
  return Boolean(identity);
}

function itemActionMatchesItem(action: GeneratedItemAction, item?: AiItemActionItem): boolean {
  if (action.id === "document-update-catalog-summary") {
    return Boolean(item && isSharedProjectDocumentCatalogItem(item));
  }
  if (!action.when) return true;
  if (!item) return false;
  if (action.when.noteTypes && !action.when.noteTypes.includes(normalizedNoteType(item))) {
    return false;
  }
  if (action.when.fileExtensions && !action.when.fileExtensions.includes(itemFileExtension(item))) {
    return false;
  }
  if (action.when.mediaKinds && !action.when.mediaKinds.includes(itemMediaKind(item))) {
    return false;
  }
  return true;
}

function resolveItemActionTemplate(template: string, item: AiItemActionItem): string {
  return template.replace(PLACEHOLDER_PATTERN, (_, key: string) => {
    if (key === "title") return item.title ?? "";
    if (key === "path") return item.path ?? "";
    if (key === "id") return item.id ?? "";
    if (key === "hub") return item.metadata?.hub ?? "";
    if (key.startsWith("metadata.")) return item.metadata?.[key.slice("metadata.".length)] ?? "";
    return "";
  });
}

function noteBrowseItemForClassification(item: AiItemActionItem): BrowseItem {
  const path = item.path ?? item.id ?? "";
  return {
    id: item.id ?? path,
    title: item.title,
    description: item.title,
    icon: "FileText",
    path: item.path,
    typeBadge: item.typeBadge,
    primaryAction: {
      label: "Open Note",
      type: "open-file",
      target: path,
    },
    metadata: item.metadata,
  };
}

function noteSourceReference(item: AiItemActionItem): { label: string; value: string } | null {
  const metadata = item.metadata ?? {};
  const url = metadata.canonical_url ||
    metadata.canonicalUrl ||
    metadata.url ||
    metadata.source_url ||
    metadata.sourceUrl;
  if (url) return { label: "Source URL", value: url };
  const sourcePath = metadata.source_path || metadata.sourcePath;
  if (sourcePath) return { label: "Source Path", value: sourcePath };
  return null;
}

function noteAskInstruction(domain: string | null): string {
  switch (domain) {
    case "projects":
      return "Review this repo or project. Explain what it does, why it matters, risks, and the next concrete action.";
    case "jobs":
      return "Analyze this job. Match it to my profile, identify fit gaps, and suggest the next application step.";
    case "companies":
      return "Analyze this company. Summarize what it does, strategic fit, signals to investigate, and likely opportunities.";
    case "people":
      return "Analyze this person. Summarize their relevance, relationship context, and useful follow-up angles.";
    case "research":
      return "Review this research. Extract the core claims, evidence, implications, and open questions.";
    case "reading":
      return "Review this reading note. Summarize the useful ideas, why they matter, and what to retain or act on.";
    default:
      return "Review this note. Summarize what matters, why it matters, and the next useful action.";
  }
}

function noteAskPrompt(item: AiItemActionItem): string {
  const classification = noteClassificationForItem(noteBrowseItemForClassification(item));
  const sourceReference = noteSourceReference(item);
  const lines = [
    noteAskInstruction(classification.domain),
    "",
    `Title: ${item.title}`,
  ];
  if (item.path) lines.push(`Path: ${item.path}`);
  if (sourceReference) lines.push(`${sourceReference.label}: ${sourceReference.value}`);
  if (classification.domain) {
    lines.push(`Domain: ${classification.domain} (${noteDomainLabel(classification.domain)})`);
  }
  if (classification.source) {
    lines.push(`Source: ${classification.source} (${noteSourceLabel(classification.source)})`);
  }
  if (classification.status) {
    lines.push(`Status: ${classification.status} (${noteStatusLabel(classification.status)})`);
  }
  if (classification.classificationConfidence) {
    lines.push(`Confidence: ${classification.classificationConfidence}`);
  }
  return lines.join("\n");
}

function noteAskAction(category: string | undefined, item?: AiItemActionItem): AiItemAction | null {
  if (category !== "notes" || !item) return null;
  if (!hasExplicitNoteClassificationSignal(item)) return null;
  return {
    id: "note-ask-augur",
    label: "Ask Augur about this",
    icon: "MessageSquare",
    template: noteAskPrompt,
  };
}

export function itemActionsFor(category: string | undefined, item?: AiItemActionItem): GeneratedItemAction[] {
  if (!category) return [];
  return (GENERATED_ITEM_ACTIONS[category] ?? []).filter((action) => itemActionMatchesItem(action, item));
}

export function aiItemActionsFor(
  category: string | undefined,
  item?: AiItemActionItem,
  options: AiItemActionOptions = {},
): AiItemAction[] {
  const generated = itemActionsFor(category, item).flatMap((action) =>
    action.kind === "ai" && typeof action.template === "string"
      ? [{
          id: action.id,
          label: action.label,
          icon: action.icon,
          template: (item: AiItemActionItem) => resolveItemActionTemplate(action.template ?? "", item),
        }]
      : [],
  );
  const actions = [...generated];
  const askAction = noteAskAction(category, item);
  if (askAction && !actions.some((action) => action.id === askAction.id)) {
    actions.unshift(askAction);
  }
  if (item && hasInventoryProblemMetadata(item) && !actions.some((action) => action.id === "artifact-problem-chat")) {
    actions.push({
      id: "artifact-problem-chat",
      label: "Send action items to chat",
      icon: "MessageSquare",
      template: (item: AiItemActionItem) => buildProblemPrompt(item, options.activeFolderContext),
    });
  }
  return actions;
}

export function directItemActionsFor(category: string | undefined, item?: AiItemActionItem): DirectItemAction[] {
  return itemActionsFor(category, item).filter((action): action is DirectItemAction => action.kind === "direct");
}

export function resolveDirectItemActionArgs(
  action: DirectItemAction,
  item: AiItemActionItem,
): Record<string, string> {
  const resolved: Record<string, string> = {};
  for (const [key, value] of Object.entries(action.args ?? {})) {
    resolved[key] = resolveItemActionTemplate(value, item);
  }
  return resolved;
}
