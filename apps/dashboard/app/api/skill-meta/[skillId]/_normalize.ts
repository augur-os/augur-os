/**
 * Pure normalization / parsing helpers for the Skill Meta API route.
 *
 * Extracted from route.ts (WS5 decomposition). No I/O, no MCP calls.
 */

import { parseMatter } from "@/lib/server/frontmatter";
import type { SkillOwnership, SkillUpstream, SkillStatusPayload, MarkdownSkillContent } from "./_types";

export function normalizeOwnership(value: unknown): SkillOwnership {
  const ownership = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (ownership === "external" || ownership === "adopted") return ownership;
  return "augur";
}

export function normalizeUpstream(value: unknown): SkillUpstream | undefined {
  if (!value) return undefined;
  if (typeof value === "string") {
    const source = value.trim();
    return source ? { source } : undefined;
  }
  if (typeof value !== "object" || Array.isArray(value)) return undefined;

  const upstream = Object.entries(value as Record<string, unknown>).reduce<SkillUpstream>(
    (acc, [key, rawValue]) => {
      if (rawValue === null || rawValue === undefined) return acc;
      if (typeof rawValue === "string") {
        const trimmed = rawValue.trim();
        if (trimmed) acc[key] = trimmed;
        return acc;
      }
      if (typeof rawValue === "number" || typeof rawValue === "boolean") {
        acc[key] = String(rawValue);
      }
      return acc;
    },
    {},
  );

  return Object.keys(upstream).length > 0 ? upstream : undefined;
}

export function normalizeSourceTag(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const source = value.trim();
  if (!source || source === "unknown" || source === "augur") return undefined;
  return source;
}

export function frontmatterString(
  data: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function humanize(id: string): string {
  return id
    .split(/[-_]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function filenameStem(fileName: string): string {
  const lastSegment = fileName.split(/[\\/]/).pop() || fileName;
  const dotIndex = lastSegment.lastIndexOf(".");
  return dotIndex > 0 ? lastSegment.slice(0, dotIndex) : lastSegment;
}

export function fileExtension(fileName: string, fallback = "unknown"): string {
  const lastSegment = fileName.split(/[\\/]/).pop() || fileName;
  const dotIndex = lastSegment.lastIndexOf(".");
  return dotIndex >= 0 ? lastSegment.slice(dotIndex + 1) || fallback : fallback;
}

export function parseMarkdownContent(
  fileName: string,
  content: string,
): MarkdownSkillContent | null {
  try {
    const parsed = parseMatter(content);
    const data = parsed.data ?? {};

    const id = frontmatterString(data, "id") ?? filenameStem(fileName);
    return {
      id,
      label: frontmatterString(data, "label") ?? humanize(id),
      description: frontmatterString(data, "description"),
      icon: frontmatterString(data, "icon"),
      body: parsed.content,
    };
  } catch {
    return null;
  }
}

export function normalizeSkillStatus(value: unknown): SkillStatusPayload | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const payload = value as Record<string, unknown>;
  const location = typeof payload.location === "string" && payload.location.trim()
    ? payload.location.trim()
    : undefined;
  return {
    ownership: normalizeOwnership(payload.ownership),
    source: normalizeSourceTag(payload.source),
    upstream: normalizeUpstream(payload.upstream),
    location,
    isNewToDashboard:
      payload.is_new_to_dashboard === true || payload.isNewToDashboard === true,
    updateAvailable: payload.update_available === true || payload.updateAvailable === true,
    latestUpstreamCommit:
      typeof payload.latest_upstream_commit === "string" && payload.latest_upstream_commit.trim()
        ? payload.latest_upstream_commit.trim()
        : (typeof payload.latestUpstreamCommit === "string" && payload.latestUpstreamCommit.trim()
          ? payload.latestUpstreamCommit.trim()
          : undefined),
  };
}
