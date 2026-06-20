// Pure helpers + shared types/constants for BrowseCard. No JSX, no hooks.
// Leaf module: imported by BrowseCard.tsx and BrowseCard.badges.tsx; imports neither.

import {
  File,
  Image as ImageIcon,
  Lightbulb,
  Link2,
  MessageSquare,
  Mic,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type * as React from "react";
import type { BrowseItem } from "@/lib/browse/types";

export const NOTE_TYPE_LABELS: Record<string, string> = {
  url: "URL",
  file: "File",
  thought: "Thought",
  "voice-memo": "Voice Memo",
  meeting: "Meeting",
  image: "Image",
  prompt: "Prompt",
};

export const NOTE_TYPE_ICONS: Record<string, LucideIcon> = {
  url: Link2,
  file: File,
  thought: Lightbulb,
  "voice-memo": Mic,
  meeting: Users,
  image: ImageIcon,
  prompt: MessageSquare,
};

export const NOTE_TYPE_CLASSES: Record<string, string> = {
  url: "border-cyan-500/25 bg-cyan-500/10 text-cyan-500",
  file: "border-slate-500/25 bg-slate-500/10 text-slate-400",
  thought: "border-amber-500/25 bg-amber-500/10 text-amber-500",
  "voice-memo": "border-violet-500/25 bg-violet-500/10 text-violet-500",
  meeting: "border-sky-500/25 bg-sky-500/10 text-sky-500",
  image: "border-emerald-500/25 bg-emerald-500/10 text-emerald-500",
  prompt: "border-rose-500/25 bg-rose-500/10 text-rose-500",
};

export function normalizeNoteType(value?: string): string | null {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "audio" || normalized === "voice") return "voice-memo";
  return NOTE_TYPE_LABELS[normalized] ? normalized : null;
}

export function noteTypeForCard(item: BrowseItem): string | null {
  return normalizeNoteType(
    item.metadata?.["x-augur-note-type"] ||
    item.metadata?.noteType ||
    item.metadata?.note_type ||
    item.typeBadge,
  );
}

export type EnrichmentBadge = {
  label: string;
  title: string;
  className: string;
};

export function enrichmentBadgeForCard(item: BrowseItem, noteType: string | null): EnrichmentBadge | null {
  if (noteType !== "url" && noteType !== "file") return null;

  const raw = (
    item.metadata?.enrichment_status ||
    item.metadata?.enrichmentStatus ||
    item.metadata?.["x-augur-enrichment-status"] ||
    ""
  ).trim().toLowerCase();

  if (raw === "enriched") {
    return {
      label: "enriched",
      title: "Enrichment status: enriched",
      className: "border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--accent-success)]",
    };
  }

  if (["pending", "queued", "enriching", "running", "in_progress"].includes(raw)) {
    return {
      label: "enriching…",
      title: `Enrichment status: ${raw}`,
      className: "border-[var(--accent-warning)]/25 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]",
    };
  }

  return {
    label: "raw",
    title: raw ? `Enrichment status: ${raw}` : "Enrichment status: raw",
    className: "border-[var(--border-color)] bg-[var(--bg-primary)] text-[var(--text-muted)]",
  };
}

export function domainFromUrl(value?: string): string | null {
  if (!value) return null;
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function formatDuration(value?: string): string | null {
  if (!value) return null;
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  return `${Math.round(seconds / 60)} min`;
}

export function noteMetadataSegments(item: BrowseItem): string[] {
  const metadata = item.metadata ?? {};
  const duration = formatDuration(metadata.duration_seconds || metadata.durationSeconds);
  const transcript = metadata.transcript_status || metadata.transcriptStatus;
  const attendeeCount = metadata.attendee_count || metadata.attendeeCount;
  const domain = metadata.source_domain || metadata.sourceDomain || domainFromUrl(metadata.canonical_url || metadata.url);
  const enrichment = metadata.enrichment_status || metadata.enrichmentStatus;
  const triggerCount = metadata.trigger_count || metadata.triggerCount;
  const variableCount = metadata.variable_count || metadata.variableCount;

  return [
    duration,
    transcript ? `transcript ${transcript}` : null,
    attendeeCount ? `${attendeeCount} attendees` : null,
    domain,
    enrichment ? `enrichment ${enrichment}` : null,
    triggerCount ? `${triggerCount} triggers` : null,
    variableCount ? `${variableCount} variables` : null,
  ].filter((segment): segment is string => Boolean(segment));
}

export type BadgeEntry = { key: string; node: React.ReactNode };

export function metadataList(value?: string): string[] {
  if (!value) return [];
  return value.split(",").flatMap((item) => {
    const trimmed = item.trim();
    return trimmed ? [trimmed] : [];
  });
}

export function itemPageTags(item: BrowseItem): string[] {
  const metadataTags = metadataList(item.metadata?.pageTags);
  return metadataTags.length > 0 ? metadataTags : (item.tags ?? []);
}

export function isWikiPageItem(item: BrowseItem): boolean {
  const typeBadge = item.typeBadge?.toLowerCase();
  const pageType = item.metadata?.pageType?.toLowerCase();
  return typeBadge === "wiki page" ||
    typeBadge === "wiki" ||
    typeBadge === "concept" ||
    typeBadge === "query" ||
    typeBadge === "overview" ||
    typeBadge === "index" ||
    pageType === "wiki" ||
    pageType === "concept" ||
    pageType === "query" ||
    pageType === "overview" ||
    pageType === "index";
}

export function kindChipClass(kind: string): string {
  if (kind === "live") return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
  if (kind === "saved") return "bg-sky-500/15 text-sky-400 border-sky-500/20";
  return "bg-amber-500/15 text-amber-400 border-amber-500/20";
}

export function wikiMaintenanceStateLabel(state: string | undefined): string {
  if (state === "no-apply") return "no apply";
  if (state === "pending") return "pending";
  if (state === "current") return "current";
  if (state === "status-error") return "status error";
  return state ? state.replace(/[_-]+/g, " ") : "";
}

export function positiveCountLabel(value: string | undefined, noun: string): string {
  const count = Number(value);
  if (!Number.isFinite(count) || count <= 0) return "";
  return `${count} ${noun}`;
}
