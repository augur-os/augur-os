/**
 * Skill coverage — ADR-741 check-resolvable report, surfaced through the
 * shared browse file-card mechanism.
 *
 * The check-resolvable audit is NOT a browse view of its own. Per the
 * browse-page discovery contract (docs/architecture-dashboard.md), every
 * finding rides an existing file card:
 *   - unrouted_intents / orphaned_skills / routing_collisions → skill cards
 *   - stale_capability_entries                               → mcp-tool cards
 *
 * This module parses the `skill-resolvable-report` MCP payload and indexes it
 * by skill name and tool id so the card transforms can join against it.
 */

import type { BrowseItem, ViewMode } from "@/lib/browse/types";

// ── Report shape (matches the check-resolvable JSON, spec ADR-741 §4.2) ──────

export interface UnroutedFinding {
  skill_id: string;
  intent_phrase: string;
  remediation: string;
}

export interface CollisionFinding {
  phrase: string;
  skill_ids: string[];
  remediation: string;
}

export interface OrphanFinding {
  skill_id: string;
  remediation: string;
}

export interface StaleFinding {
  tool_id: string;
  remediation: string;
}

export interface ResolvableReport {
  generated_at: string;
  auditor_version: string;
  summary: {
    skills_scanned: number;
    surfaces_scanned: number;
    findings: {
      unrouted_intents: number;
      routing_collisions: number;
      orphaned_skills: number;
      stale_capability_entries: number;
    };
  };
  findings: {
    unrouted_intents: UnroutedFinding[];
    routing_collisions: CollisionFinding[];
    orphaned_skills: OrphanFinding[];
    stale_capability_entries: StaleFinding[];
  };
}

/** MCP tools return JSON-stringified payloads — accept string or object. */
export function parseReport(raw: unknown): ResolvableReport | null {
  if (!raw) return null;
  let value: unknown = raw;
  if (typeof raw === "string") {
    try {
      value = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as Partial<ResolvableReport>;
  if (!candidate.findings || !candidate.summary) return null;
  return candidate as ResolvableReport;
}

// ── Per-skill aggregate ─────────────────────────────────────────────────────

export interface SkillCoverageFindings {
  skillId: string;
  unrouted: UnroutedFinding[];
  orphaned: OrphanFinding | null;
  collisions: CollisionFinding[];
  /** Total findings touching this skill — drives the card tag count. */
  issueCount: number;
}

export interface CoverageIndex {
  generatedAt: string | null;
  bySkill: Map<string, SkillCoverageFindings>;
  byTool: Map<string, StaleFinding>;
}

export const EMPTY_COVERAGE_INDEX: CoverageIndex = {
  generatedAt: null,
  bySkill: new Map(),
  byTool: new Map(),
};

/** Capability ids carry a `mcp-tool:` (or similar) prefix — strip it for matching. */
export function normalizeToolId(id: string): string {
  const trimmed = id.trim().toLowerCase();
  const colon = trimmed.indexOf(":");
  return colon >= 0 ? trimmed.slice(colon + 1) : trimmed;
}

/**
 * Mirror of transforms.ts skill-id slugification. The check-resolvable report
 * keys findings by raw skill name; browse items key by slug. Indexing under
 * both lets either side join without a lookup table.
 */
export function slugifySkillId(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function ensureSkill(
  map: Map<string, SkillCoverageFindings>,
  skillId: string,
): SkillCoverageFindings {
  let entry = map.get(skillId);
  if (!entry) {
    entry = { skillId, unrouted: [], orphaned: null, collisions: [], issueCount: 0 };
    map.set(skillId, entry);
  }
  return entry;
}

export function buildCoverageIndex(report: ResolvableReport | null): CoverageIndex {
  if (!report) return EMPTY_COVERAGE_INDEX;

  const bySkill = new Map<string, SkillCoverageFindings>();
  const byTool = new Map<string, StaleFinding>();

  for (const finding of report.findings.unrouted_intents ?? []) {
    const entry = ensureSkill(bySkill, finding.skill_id);
    entry.unrouted.push(finding);
    entry.issueCount += 1;
  }
  for (const finding of report.findings.orphaned_skills ?? []) {
    const entry = ensureSkill(bySkill, finding.skill_id);
    entry.orphaned = finding;
    entry.issueCount += 1;
  }
  for (const finding of report.findings.routing_collisions ?? []) {
    // A collision touches every participating skill's card.
    for (const skillId of finding.skill_ids ?? []) {
      const entry = ensureSkill(bySkill, skillId);
      entry.collisions.push(finding);
      entry.issueCount += 1;
    }
  }
  for (const finding of report.findings.stale_capability_entries ?? []) {
    byTool.set(normalizeToolId(finding.tool_id), finding);
  }

  // Alias each skill entry under its slug too, so browse items (slug-keyed)
  // and the raw report (name-keyed) both resolve. Identical for kebab-case
  // names, which is nearly all of them.
  for (const [skillId, entry] of [...bySkill.entries()]) {
    const slug = slugifySkillId(skillId);
    if (slug !== skillId && !bySkill.has(slug)) {
      bySkill.set(slug, entry);
    }
  }

  return { generatedAt: report.generated_at ?? null, bySkill, byTool };
}

// ── Card-facing helpers ─────────────────────────────────────────────────────

/** `danger` when the skill is fully orphaned (unreachable), else `warning`. */
export type CoverageTone = "danger" | "warning";

/** Short label + tooltip text + tone for the skill-card coverage state tag. */
export function coverageTagFor(
  findings: SkillCoverageFindings,
): { label: string; title: string; tone: CoverageTone } {
  const parts: string[] = [];
  if (findings.orphaned) parts.push("orphaned skill");
  if (findings.unrouted.length > 0) {
    parts.push(
      `${findings.unrouted.length} unrouted intent${findings.unrouted.length === 1 ? "" : "s"}`,
    );
  }
  if (findings.collisions.length > 0) {
    parts.push(
      `${findings.collisions.length} routing collision${findings.collisions.length === 1 ? "" : "s"}`,
    );
  }
  const label =
    findings.issueCount === 1 ? "1 coverage issue" : `${findings.issueCount} coverage issues`;
  return {
    label,
    title: `Skill coverage (ADR-741): ${parts.join(", ")}`,
    tone: findings.orphaned ? "danger" : "warning",
  };
}

/**
 * Join the coverage index onto a list of browse items by writing discrete
 * metadata keys the existing card transforms already understand:
 *   - skills    → `coverageIssueCount`, `coverageSummary`
 *   - mcp-tools → `coverageStale`
 *
 * Returns new item objects (with cloned metadata); inputs are not mutated.
 * Items with no matching finding are returned unchanged.
 */
export function enrichItemsWithCoverage(
  items: BrowseItem[],
  index: CoverageIndex,
  viewMode: ViewMode,
): BrowseItem[] {
  if (viewMode === "skills") {
    if (index.bySkill.size === 0) return items;
    return items.map((item) => {
      // Primary join: the canonical skill name in metadata. Fallbacks: the
      // raw id, then its last `:` segment (browse ids are `skill:<source>:<name>`).
      const findings =
        (item.metadata?.skillName && index.bySkill.get(item.metadata.skillName)) ||
        index.bySkill.get(item.id) ||
        (item.id.includes(":")
          ? index.bySkill.get(item.id.slice(item.id.lastIndexOf(":") + 1))
          : undefined);
      if (!findings || findings.issueCount === 0) return item;
      const { label, title, tone } = coverageTagFor(findings);
      return {
        ...item,
        metadata: {
          ...item.metadata,
          coverageIssueCount: String(findings.issueCount),
          coverageSummary: title,
          coverageLabel: label,
          coverageTone: tone,
        },
      };
    });
  }

  if (viewMode === "mcp-tools") {
    if (index.byTool.size === 0) return items;
    return items.map((item) => {
      const candidates = [
        item.metadata?.toolId,
        item.metadata?.capabilityId,
        item.id,
        item.title,
      ].filter((v): v is string => Boolean(v));
      let stale: StaleFinding | undefined;
      for (const candidate of candidates) {
        stale = index.byTool.get(normalizeToolId(candidate));
        if (stale) break;
      }
      if (!stale) return item;
      return {
        ...item,
        metadata: {
          ...item.metadata,
          coverageStale: stale.remediation,
        },
      };
    });
  }

  return items;
}
