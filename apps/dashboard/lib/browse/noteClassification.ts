import type {
  BrowseItem,
  NoteClassificationConfidence,
  NoteDomain,
  NoteSource,
  NoteStatus,
  NoteTypeFilter,
} from "./types";

export interface NoteClassification {
  noteType: NoteTypeFilter | null;
  domain: NoteDomain | null;
  source: NoteSource | null;
  status: NoteStatus | null;
  classificationConfidence: NoteClassificationConfidence | null;
  needsClassification: boolean;
}

export interface FilterOption<T extends string = string> {
  id: T;
  label: string;
}

export const NOTE_DOMAINS: readonly NoteDomain[] = [
  "projects",
  "jobs",
  "companies",
  "people",
  "research",
  "reading",
] as const;

export const NOTE_SOURCES: readonly NoteSource[] = [
  "github",
  "linkedin",
  "website",
  "email",
  "local-file",
] as const;

export const NOTE_DOMAIN_LABELS: Record<string, string> = {
  projects: "Project",
  jobs: "Job",
  companies: "Company",
  people: "Person",
  research: "Research",
  reading: "Reading",
};

export const NOTE_SOURCE_LABELS: Record<string, string> = {
  github: "GitHub",
  linkedin: "LinkedIn",
  website: "Website",
  email: "Email",
  "local-file": "Local file",
};

export const NOTE_STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  archived: "Archived",
  evaluating: "Evaluating",
  watching: "Watching",
  active: "Active",
  queued: "Queued",
  reading: "Reading",
  finished: "Finished",
};

const NOTE_TYPE_LABELS: Record<NoteTypeFilter, string> = {
  url: "URL",
  file: "File",
  thought: "Thought",
  "voice-memo": "Voice Memo",
  meeting: "Meeting",
  image: "Image",
  prompt: "Prompt",
};

const NOTE_TYPE_ALIASES: Record<string, NoteTypeFilter> = {
  url: "url",
  article: "url",
  webpage: "url",
  source: "url",
  file: "file",
  document: "file",
  markdown: "file",
  thought: "thought",
  text: "thought",
  note: "thought",
  "voice-memo": "voice-memo",
  voice: "voice-memo",
  audio: "voice-memo",
  meeting: "meeting",
  image: "image",
  prompt: "prompt",
};

const DOMAIN_ALIASES: Record<string, NoteDomain> = {
  project: "projects",
  repo: "projects",
  repository: "projects",
  job: "jobs",
  company: "companies",
  person: "people",
  profile: "people",
  article: "reading",
  read: "reading",
};

const SOURCE_ALIASES: Record<string, NoteSource> = {
  github: "github",
  "github.com": "github",
  linkedin: "linkedin",
  "linkedin.com": "linkedin",
  web: "website",
  webpage: "website",
  website: "website",
  email: "email",
  mail: "email",
  file: "local-file",
  local: "local-file",
  "local-file": "local-file",
};

const STATUSES_BY_DOMAIN: Record<string, readonly NoteStatus[]> = {
  jobs: ["saved", "applied", "interviewing", "offer", "rejected", "archived"],
  projects: ["saved", "evaluating", "watching", "active", "archived"],
  reading: ["queued", "reading", "finished", "archived"],
  companies: [],
  people: [],
  research: [],
};

function text(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return String(value);
  return "";
}

function metadataValue(metadata: Record<string, unknown> | undefined, ...keys: string[]): string {
  for (const key of keys) {
    const value = text(metadata?.[key]);
    if (value) return value;
  }
  return "";
}

export function hasExplicitNoteClassificationSignal(item: { metadata?: Record<string, unknown> }): boolean {
  const metadata = item.metadata;
  if (metadataValue(metadata, "x-augur-note-type", "noteType", "note_type", "note_type_filter")) return true;
  if (metadataValue(
    metadata,
    "x-augur-domain",
    "x-augur-source",
    "x-augur-status",
    "x-augur-note-domain",
    "x-augur-note-source",
    "x-augur-note-status",
    "x-augur-classification-confidence",
  )) return true;
  return false;
}

function token(value: string): string {
  return value.trim().toLowerCase().replace(/[\s_]+/g, "-");
}

function noteFilterLabel(value: string): string {
  return value
    .trim()
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function noteDomainLabel(value: NoteDomain): string {
  return NOTE_DOMAIN_LABELS[value] ?? noteFilterLabel(value);
}

export function noteSourceLabel(value: NoteSource): string {
  return NOTE_SOURCE_LABELS[value] ?? noteFilterLabel(value);
}

export function noteStatusLabel(value: NoteStatus): string {
  return NOTE_STATUS_LABELS[value] ?? noteFilterLabel(value);
}

export function normalizeNoteType(value: string | undefined): NoteTypeFilter | null {
  const normalized = token(value ?? "");
  if (!normalized) return null;
  return NOTE_TYPE_ALIASES[normalized] ?? null;
}

export function normalizeNoteDomain(value: string | undefined): NoteDomain | null {
  const normalized = token(value ?? "");
  if (!normalized) return null;
  return DOMAIN_ALIASES[normalized] ?? normalized;
}

export function normalizeNoteSource(value: string | undefined): NoteSource | null {
  const normalized = token(value ?? "");
  if (!normalized) return null;
  return SOURCE_ALIASES[normalized] ?? normalized;
}

export function normalizeNoteStatus(
  value: string | undefined,
  _domain: NoteDomain | null,
): NoteStatus | null {
  const normalized = token(value ?? "");
  if (!normalized) return null;
  return normalized;
}

function normalizeConfidence(value: string | undefined): NoteClassificationConfidence | null {
  const normalized = token(value ?? "");
  return normalized === "high" || normalized === "medium" || normalized === "low"
    ? normalized
    : null;
}

function sourceUrl(metadata: Record<string, unknown> | undefined): string {
  return metadataValue(metadata, "canonical_url", "canonicalUrl", "url", "source_url", "sourceUrl");
}

function parsedUrl(raw: string): URL | null {
  try {
    return raw ? new URL(raw) : null;
  } catch {
    return null;
  }
}

function pathLooksLocalFile(path: string | undefined, noteType: NoteTypeFilter | null): boolean {
  if (noteType === "file") return true;
  const normalized = path?.replace(/\\/g, "/") ?? "";
  return normalized.includes("/documents/") || normalized.includes("/sources/files/");
}

function inferNoteType(
  metadata: Record<string, unknown> | undefined,
  path: string | undefined,
): NoteTypeFilter | null {
  const normalizedPath = path?.replace(/\\/g, "/").toLowerCase() ?? "";
  if (normalizedPath.includes("/sources/urls/")) return "url";
  if (normalizedPath.includes("/sources/files/")) return "file";
  if (normalizedPath.includes("/prompts/")) return "prompt";
  if (metadataValue(metadata, "canonical_url", "url", "source_domain")) return "url";
  return null;
}

function classifyByUrl(
  rawUrl: string,
): Pick<NoteClassification, "domain" | "source" | "status" | "classificationConfidence"> | null {
  const url = parsedUrl(rawUrl);
  if (!url) return null;
  const host = url.hostname.replace(/^www\./, "").toLowerCase();
  const pathname = url.pathname.toLowerCase();
  if (host === "github.com") {
    const projectStatus = /\/(issues|pull)\//.test(pathname) ? "evaluating" : "saved";
    return { domain: "projects", source: "github", status: projectStatus, classificationConfidence: "high" };
  }
  if (host === "linkedin.com") {
    if (pathname.startsWith("/jobs/")) {
      return { domain: "jobs", source: "linkedin", status: "saved", classificationConfidence: "high" };
    }
    if (pathname.startsWith("/in/")) {
      return { domain: "people", source: "linkedin", status: null, classificationConfidence: "high" };
    }
  }
  if (/\/(careers?|about|company)\b/.test(pathname)) {
    return { domain: "companies", source: "website", status: null, classificationConfidence: "medium" };
  }
  if (host.startsWith("docs.") || /\/(docs?|reference|manual|api|learn)\b/.test(pathname)) {
    return { domain: "research", source: "website", status: null, classificationConfidence: "medium" };
  }
  if (/\/(blog|articles?|newsletter|essays?)\b/.test(pathname)) {
    return { domain: "reading", source: "website", status: "queued", classificationConfidence: "medium" };
  }
  return { domain: "research", source: "website", status: null, classificationConfidence: "low" };
}

export function classifyNoteMetadata({
  noteType,
  metadata,
  path,
  typeBadge,
}: {
  noteType?: string;
  metadata?: Record<string, unknown>;
  path?: string;
  typeBadge?: string;
}): NoteClassification {
  const explicitNoteType = normalizeNoteType(
    noteType ||
      metadataValue(metadata, "x-augur-note-type", "noteType", "note_type", "note_type_filter") ||
      typeBadge,
  );
  const normalizedNoteType = explicitNoteType ?? inferNoteType(metadata, path);
  const domain = normalizeNoteDomain(metadataValue(
    metadata,
    "x-augur-domain",
    "x-augur-note-domain",
    "noteDomain",
    "note_domain",
  ));
  const source = normalizeNoteSource(metadataValue(
    metadata,
    "x-augur-source",
    "x-augur-note-source",
    "noteSource",
    "note_source",
  ));
  const rawStatus = metadataValue(
    metadata,
    "x-augur-status",
    "x-augur-note-status",
    "noteStatus",
    "note_status",
  );
  const status = normalizeNoteStatus(rawStatus, domain);
  const confidence = normalizeConfidence(metadataValue(
    metadata,
    "x-augur-classification-confidence",
    "classificationConfidence",
  ));

  if (domain || source || status || confidence) {
    const resolvedDomain = domain ?? "research";
    const resolvedSource = source ?? (pathLooksLocalFile(path, normalizedNoteType) ? "local-file" : "website");
    const resolvedConfidence = confidence ?? "medium";
    return {
      noteType: normalizedNoteType,
      domain: resolvedDomain,
      source: resolvedSource,
      status: normalizeNoteStatus(status ?? rawStatus, resolvedDomain),
      classificationConfidence: resolvedConfidence,
      needsClassification: resolvedConfidence === "low",
    };
  }

  if (pathLooksLocalFile(path, normalizedNoteType)) {
    return {
      noteType: normalizedNoteType,
      domain: "research",
      source: "local-file",
      status: null,
      classificationConfidence: "low",
      needsClassification: true,
    };
  }

  const urlGuess = classifyByUrl(sourceUrl(metadata));
  if (urlGuess) {
    return {
      noteType: normalizedNoteType,
      ...urlGuess,
      needsClassification: urlGuess.classificationConfidence === "low",
    };
  }

  return {
    noteType: normalizedNoteType,
    domain: "research",
    source: "website",
    status: null,
    classificationConfidence: "low",
    needsClassification: true,
  };
}

export function noteClassificationForItem(item: BrowseItem): NoteClassification {
  return classifyNoteMetadata({
    noteType: item.metadata?.["x-augur-note-type"] ||
      item.metadata?.noteType ||
      item.metadata?.note_type ||
      item.metadata?.note_type_filter,
    metadata: item.metadata,
    path: item.path || item.metadata?.source_path || item.primaryAction.target,
    typeBadge: item.typeBadge,
  });
}

export function noteStatusOptionsForDomain(domain: NoteDomain | null): FilterOption<NoteStatus>[] {
  if (!domain) return [];
  return (STATUSES_BY_DOMAIN[domain] ?? []).map((id) => ({ id, label: noteStatusLabel(id) }));
}

export function noteDomainOptions(): FilterOption<NoteDomain>[] {
  return NOTE_DOMAINS.map((id) => ({ id, label: noteDomainLabel(id) }));
}

export function noteSourceOptions(): FilterOption<NoteSource>[] {
  return NOTE_SOURCES.map((id) => ({ id, label: noteSourceLabel(id) }));
}

export function classificationBadgesForItem(item: BrowseItem): Array<{ id: string; label: string; icon?: string }> {
  const classification = noteClassificationForItem(item);
  const badges: Array<{ id: string; label: string; icon?: string }> = [];
  if (classification.noteType) {
    badges.push({ id: `note-type-${classification.noteType}`, label: NOTE_TYPE_LABELS[classification.noteType] });
  }
  if (classification.domain) {
    badges.push({ id: `note-domain-${classification.domain}`, label: noteDomainLabel(classification.domain) });
  }
  if (classification.source) {
    badges.push({ id: `note-source-${classification.source}`, label: noteSourceLabel(classification.source) });
  }
  if (classification.status) {
    badges.push({ id: `note-status-${classification.status}`, label: noteStatusLabel(classification.status) });
  }
  if (classification.needsClassification) {
    badges.push({ id: "note-needs-classification", label: "Needs classification", icon: "AlertTriangle" });
  }
  return badges;
}
