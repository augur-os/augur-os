"use client";

import { useState } from "react";
import { LayoutDashboard } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { GlassCard, type GlassCardColor } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/Badge";
import {
  detectFields,
  detectFieldRole,
  autoFormat,
  badgeColor,
  type FieldRole,
  type BadgeColor,
} from "@/lib/blocks/auto-detect";
import { keyedRenderItems, stableRenderKey } from "@/lib/stable-render-key";

/* ---------- Config types ---------- */

interface SourceConfig {
  mcp_tool: string;
  title?: string;
  icon?: string;
  color?: string;
  skill_id?: string;
}

interface MetricsDashboardConfig {
  title?: string;
  sources?: SourceConfig[];
}

/* ---------- Helpers ---------- */

const VALID_GLASS_COLORS = new Set<GlassCardColor>([
  "cyan",
  "purple",
  "emerald",
  "amber",
  "blue",
  "rose",
  "violet",
  "pink",
]);

function toGlassColor(color?: string): GlassCardColor {
  if (color && VALID_GLASS_COLORS.has(color as GlassCardColor)) {
    return color as GlassCardColor;
  }
  return "cyan";
}

const BADGE_VARIANT_MAP: Record<BadgeColor, "success" | "destructive" | "outline" | "default"> = {
  green: "success",
  red: "destructive",
  amber: "outline",
  gray: "outline",
  blue: "default",
};

/** Convert snake_case keys to Title Case labels */
function smartLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const STAT_ROLES = new Set<FieldRole>([
  "metric",
  "metric-pct",
  "currency",
  "progress",
  "badge",
  "timestamp",
  "duration",
  "boolean",
]);

/* ---------- SourceCard ---------- */

/** When bare=true, render content directly (BlockShell is the container).
 *  When bare=false, wrap in GlassCard for multi-source dashboards. */
function CardWrapper({ bare, color, title, children }: {
  bare?: boolean; color: GlassCardColor; title: string; children: React.ReactNode;
}) {
  if (bare) return <>{children}</>;
  return <GlassCard color={color} title={title}>{children}</GlassCard>;
}

function SourceCardSkeleton() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {["metric-skeleton-a", "metric-skeleton-b", "metric-skeleton-c"].map((key) => (
          <div
            key={key}
            className="text-center p-2 rounded-lg bg-[var(--bg-hover)]/30"
          >
            <div className="h-5 w-10 mx-auto rounded bg-[var(--bg-hover)] animate-pulse mb-1" />
            <div className="h-3 w-12 mx-auto rounded bg-[var(--bg-hover)] animate-pulse" />
          </div>
        ))}
      </div>
      <div className="space-y-1.5">
        {["metric-line-skeleton-a", "metric-line-skeleton-b"].map((key) => (
          <div
            key={key}
            className="h-4 rounded bg-[var(--bg-hover)] animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}

function SourceCard({ source, bare }: { source: SourceConfig; bare?: boolean }) {
  const sourceArgs = source.skill_id ? { skillId: source.skill_id } : {};
  const [expanded, setExpanded] = useState(false);
  const { data, loading, error } = useBlockData(
    { mcpTool: source.mcp_tool },
    sourceArgs,
    "metrics-dashboard",
  );

  const glassColor = toGlassColor(source.color);
  const cardTitle = source.title || source.mcp_tool;

  if (loading) {
    return (
      <CardWrapper bare={bare} color={glassColor} title={cardTitle}>
        <SourceCardSkeleton />
      </CardWrapper>
    );
  }

  if (error) {
    return (
      <CardWrapper bare={bare} color={glassColor} title={cardTitle}>
        <div className="text-center py-4">
          <p className="text-xs text-red-400/80">Failed to load data</p>
          <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      </CardWrapper>
    );
  }

  // Handle different data shapes:
  // 1. Dict → render as stat tiles + detail rows
  // 2. Array of {value, label} → convert to dict (from all-scalar conversion)
  // 3. Array of objects → render as item count + first item preview
  // 4. Empty/null → show "No data"

  // Arrays of real objects (e.g., symptoms, medications)
  if (Array.isArray(data) && data.length > 0 && typeof data[0] === "object" && !("label" in data[0] && "value" in data[0])) {
    const items = data as Record<string, unknown>[];
    const firstItem = items[0];
    const itemFields = detectFields(firstItem);
    // Find title field for display
    let titleKey: string | null = null;
    for (const [key, role] of itemFields) {
      if (role === "title") { titleKey = key; break; }
    }

    // Compute summary totals for currency fields
    const currencyKeys = Array.from(itemFields.entries()).flatMap(([key, role]) =>
      role === "currency" ? [key] : [],
    );
    const summaryTotals: Array<{ label: string; total: number }> = [];
    for (const ck of currencyKeys.slice(0, 3)) {
      const total = items.reduce((sum, item) => sum + (typeof item[ck] === "number" ? (item[ck] as number) : 0), 0);
      if (total > 0) summaryTotals.push({ label: smartLabel(ck), total });
    }

    return (
      <CardWrapper bare={bare} color={glassColor} title={cardTitle}>
        <div className="space-y-2">
          {/* Summary header with totals */}
          {summaryTotals.length > 0 ? (
            <div className="flex items-baseline gap-4 flex-wrap">
              {summaryTotals.map(({ label, total }) => (
                <div key={label}>
                  <span className="text-lg font-bold text-[var(--text-primary)] tabular-nums">{autoFormat(total, "currency")}</span>
                  <span className="text-xs text-[var(--text-muted)] ml-1">{label}</span>
                </div>
              ))}
              <span className="text-xs text-[var(--text-muted)]">{items.length} item{items.length !== 1 ? "s" : ""}</span>
            </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">{items.length} item{items.length !== 1 ? "s" : ""}</p>
          )}
          {keyedRenderItems(items.slice(0, expanded ? items.length : 4)).map(({ item, key }) => {
            const label = titleKey ? String(item[titleKey] ?? "") : stableRenderKey(item, "item");
            const badgeKey = Array.from(itemFields.entries()).find(([, r]) => r === "badge")?.[0];
            const badge = badgeKey ? String(item[badgeKey] ?? "") : null;
            // Show more detail fields, prioritize currency and progress
            const detailKeys = Array.from(itemFields.entries())
              .filter(([k, r]) => k !== titleKey && k !== badgeKey && r !== "nested" && r !== "array" && r !== "icon" && r !== "title" && r !== "subtitle" && r !== "meta")
              .sort(([, a], [, b]) => {
                const priority: Record<string, number> = { currency: 0, progress: 1, "metric-pct": 2, metric: 3 };
                return (priority[a] ?? 9) - (priority[b] ?? 9);
              })
              .slice(0, 4);

            // Check if item has a progress field for a visual bar
            const progressKey = Array.from(itemFields.entries()).find(([, r]) => r === "progress")?.[0];
            const progressValue = progressKey ? Number(item[progressKey] ?? 0) : null;

            return (
              <div key={key} className="rounded-lg border border-[var(--border-color)]/50 bg-[var(--bg-secondary)]/30 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)] truncate">{label}</span>
                  {badge && (
                    <Badge variant={BADGE_VARIANT_MAP[badgeColor(badge)]}>{badge}</Badge>
                  )}
                </div>
                {progressValue !== null && (
                  <div className="mt-1.5">
                    <div className="w-full h-1.5 rounded-full bg-[var(--bg-hover)]">
                      <div
                        className="h-full rounded-full bg-[var(--accent-primary)] transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, progressValue))}%` }}
                      />
                    </div>
                  </div>
                )}
                {detailKeys.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {detailKeys.map(([k, role]) => (
                      <div key={k} className="flex justify-between text-xs">
                        <span className="text-[var(--text-muted)]">{smartLabel(k)}</span>
                        <span className={`text-[var(--text-secondary)] ${role === "currency" ? "tabular-nums font-medium" : ""}`}>
                          {autoFormat(item[k], role)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {items.length > 4 && (
            <button type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-[var(--accent-primary)] hover:text-[var(--accent-primary)]/80 text-center w-full py-1 cursor-pointer transition-colors"
            >
              {expanded ? "Show less" : `+${items.length - 4} more`}
            </button>
          )}
        </div>
      </CardWrapper>
    );
  }

  // Array of {value, label} pairs (from all-scalar dict conversion)
  let record: Record<string, unknown> = {};
  if (data && typeof data === "object" && !Array.isArray(data)) {
    record = data as Record<string, unknown>;
  } else if (Array.isArray(data) && data.length > 0 && typeof data[0] === "object" && "label" in data[0]) {
    for (const item of data as Array<{ value: unknown; label: string }>) {
      record[item.label] = item.value;
    }
  }

  if (Object.keys(record).length === 0) {
    return (
      <CardWrapper bare={bare} color={glassColor} title={cardTitle}>
        <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
          No data available
        </p>
      </CardWrapper>
    );
  }

  const fields = detectFields(record);
  const statEntries: Array<[string, unknown, FieldRole]> = [];
  const detailEntries: Array<[string, unknown, FieldRole]> = [];

  for (const [key, role] of fields) {
    if (role === "icon" || role === "title" || role === "subtitle" || role === "meta") continue;
    if (STAT_ROLES.has(role)) {
      statEntries.push([key, record[key], role]);
    } else {
      detailEntries.push([key, record[key], role]);
    }
  }

  const visibleDetails = detailEntries.slice(0, 6);

  return (
    <CardWrapper bare={bare} color={glassColor} title={cardTitle}>
      {/* Stat tiles */}
      {statEntries.length > 0 && (
        <div className={`grid ${bare && statEntries.length <= 4 ? "grid-cols-2" : "grid-cols-3"} gap-2 mb-3`}>
          {statEntries.map(([key, value, role]) => (
            <div
              key={key}
              className="text-center p-2 rounded-lg bg-[var(--bg-hover)]/30"
            >
              {role === "badge" ? (
                <Badge
                  variant={BADGE_VARIANT_MAP[badgeColor(String(value ?? ""))]}
                  size="sm"
                >
                  {String(value ?? "")}
                </Badge>
              ) : role === "progress" && typeof value === "number" ? (
                <>
                  <div className={`${bare ? "text-base" : "text-sm"} font-bold text-[var(--text-primary)] tabular-nums`}>
                    {Number(value.toFixed(1))}%
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[var(--bg-hover)] mt-1">
                    <div
                      className="h-full rounded-full bg-[var(--accent-primary)] transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
                    />
                  </div>
                </>
              ) : (
                <div className={`${bare ? "text-base" : "text-sm"} font-bold text-[var(--text-primary)] tabular-nums`}>
                  {autoFormat(value, role)}
                </div>
              )}
              <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                {smartLabel(key)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail rows */}
      {visibleDetails.length > 0 && (
        <div className="space-y-1.5">
          {visibleDetails.map(([key, value, role]) => {
            // Expand nested dicts inline
            if (role === "nested" && value && typeof value === "object") {
              const nested = value as Record<string, unknown>;
              const entries = Object.entries(nested).slice(0, 8);
              const allBooleans = entries.every(([, v]) => typeof v === "boolean");

              if (allBooleans && entries.length > 0) {
                // Boolean dict → green/gray tags
                return (
                  <div key={key}>
                    <span className="text-xs text-[var(--text-muted)]">{smartLabel(key)}</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {entries.map(([k, v]) => (
                        <span key={k} className={`text-[10px] px-1.5 py-0.5 rounded ${v ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-[var(--bg-hover)] text-[var(--text-muted)] line-through"}`}>
                          {smartLabel(k)}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              }

              // Non-boolean dict → key-value pairs
              return (
                <div key={key}>
                  <span className="text-xs text-[var(--text-muted)]">{smartLabel(key)}</span>
                  <div className="mt-0.5 space-y-0.5 pl-2 border-l-2 border-[var(--border-color)]/30">
                    {entries.map(([k, v]) => {
                      const nestedRole = detectFieldRole(k, v);
                      return (
                        <div key={k} className="flex justify-between text-[10px]">
                          <span className="text-[var(--text-muted)]">{smartLabel(k)}</span>
                          <span className={`text-[var(--text-secondary)] ${nestedRole === "currency" ? "tabular-nums font-medium" : ""}`}>
                            {autoFormat(v, nestedRole)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            }

            return (
              <div
                key={key}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-[var(--text-muted)]">
                  {smartLabel(key)}
                </span>
                <span className={`text-[var(--text-secondary)] font-medium truncate ml-2 max-w-[60%] text-right ${role === "currency" ? "tabular-nums" : ""}`}>
                  {autoFormat(value, role)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state when no stats and no details */}
      {statEntries.length === 0 && visibleDetails.length === 0 && (
        <p className="text-xs text-[var(--text-muted)] italic text-center py-2">
          No fields detected
        </p>
      )}
    </CardWrapper>
  );
}

/* ---------- Main component ---------- */

export default function MetricsDashboardBlock({
  config,
}: BlockProps<MetricsDashboardConfig>) {
  const { title = "Metrics Dashboard", sources = [] } = config;

  return (
    <BlockShell title={title} icon={LayoutDashboard} color="purple">
      {sources.length === 0 && (
        <div className="p-4">
          <p className="text-xs text-[var(--text-muted)] italic text-center">
            No sources configured
          </p>
        </div>
      )}

      {sources.length > 0 && (
        <div className={`p-4 grid gap-4 ${sources.length === 1 ? "grid-cols-1" : "grid-cols-1 md:grid-cols-2"}`}>
          {keyedRenderItems(sources, (source) => source.mcp_tool).map(({ item: source, key }) => (
            <SourceCard
              key={key}
              source={source}
              bare={sources.length === 1}
            />
          ))}
        </div>
      )}
    </BlockShell>
  );
}
