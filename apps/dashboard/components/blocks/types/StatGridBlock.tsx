"use client";

import { BarChart2 } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { keyedRenderItems } from "@/lib/stable-render-key";
import { cn } from "@/lib/utils";
import { BlockShell } from "../BlockShell";

interface StatGridConfig {
  title?: string;
  stats?: Array<{ value: string | number | boolean | null; label: string }>;
}
interface StatItem {
  value: string | number | boolean | null;
  label: string;
}

const LABEL_OVERRIDES: Record<string, string> = {
  vault_exists: "Vault",
  vault_path: "Vault Path",
  obsidian_configured: "Obsidian",
  markdown_files: "Markdown Files",
  note_count: "Note Count",
  directory_count: "Directory Count",
  total_size_bytes: "Vault Size",
  checked_at: "Checked At",
  modified_at: "Modified",
  last_modified: "Modified",
};

function formatStatLabel(label: string): string {
  if (LABEL_OVERRIDES[label]) return LABEL_OVERRIDES[label];
  return label
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const precision = unit === 0 || size >= 10 ? 0 : 1;
  return `${size.toFixed(precision)} ${units[unit]}`;
}

function formatPathValue(value: string): string {
  const normalized = value.replace(/^\/Users\/[^/]+/, "~");
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 2) return normalized;
  const last = parts[parts.length - 1];
  if (normalized.startsWith("~/")) return `~/.../${last}`;
  if (normalized.startsWith("/")) return `/.../${last}`;
  return `${parts[0]}/.../${last}`;
}

function formatStatValue(value: StatItem["value"], label: string): string {
  if (value == null) return "N/A";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && /bytes/i.test(label)) return formatBytes(value);
  if (typeof value === "string") {
    if (/path/i.test(label) && value.includes("/")) {
      return formatPathValue(value);
    }
    const parsed = new Date(value);
    if (
      /\d{4}-\d{2}-\d{2}T/.test(value) &&
      Number.isFinite(parsed.getTime())
    ) {
      return parsed.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }
  return String(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isStatValue(value: unknown): value is StatItem["value"] {
  return (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}

function normalizeStatItems(
  data: unknown,
  fallback: StatItem[] | undefined,
): StatItem[] {
  if (Array.isArray(data)) {
    return data.filter(
      (item): item is StatItem =>
        isRecord(item) && typeof item.label === "string" && isStatValue(item.value),
    );
  }

  if (isRecord(data)) {
    const source = isRecord(data.stats) ? data.stats : data;
    return Object.entries(source).flatMap(([label, value]) =>
      isStatValue(value)
        ? [{
            label,
            value: value as StatItem["value"],
          }]
        : [],
    );
  }

  return fallback ?? [];
}

export default function StatGridBlock(props: BlockProps<StatGridConfig>) {
  const { config, dataSource, mode } = props;
  const { title = "Stats" } = config;
  const selfFetched = useBlockData<StatItem[]>(
    dataSource,
    config,
    "stat-grid",
  );
  const data = (props.data as StatItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const stats = normalizeStatItems(data, config.stats);

  const gridCols = (() => {
    const n = stats.length;
    if (n === 2 || n === 4) return "grid-cols-2 sm:grid-cols-2";
    if (n === 3 || n === 6) return "grid-cols-2 md:grid-cols-3";
    if (n >= 5) return "grid-cols-2 sm:grid-cols-3 lg:grid-cols-[repeat(auto-fit,minmax(140px,1fr))]";
    return "grid-cols-2 md:grid-cols-3";
  })();

  return (
    <BlockShell title={title} icon={BarChart2} color="blue" staleError={error}>
      <div className={`p-4 grid ${gridCols} gap-3`}>
        {loading &&
          ["stat-grid-skeleton-a", "stat-grid-skeleton-b", "stat-grid-skeleton-c"].map((key) => (
            <div
              key={key}
              className="text-center p-2 rounded-lg bg-[var(--bg-hover)]/30 transition-colors"
            >
              <div className="h-5 w-10 mx-auto rounded bg-[var(--bg-hover)] animate-pulse mb-1" />
              <div className="h-3 w-12 mx-auto rounded bg-[var(--bg-hover)] animate-pulse" />
            </div>
          ))}

        {!loading && stats.length === 0 && !error && (
          <p className="col-span-3 text-xs text-[var(--text-muted)] italic text-center">
            No stats
          </p>
        )}
        {!loading && stats.length === 0 && error && (
          <div className="col-span-3 text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          keyedRenderItems(stats, (stat) => stat.label).map(({ item: s, key }) => {
            const value = formatStatValue(s.value, s.label);
            const label = formatStatLabel(s.label);
            const longValue = value.length > 16;
            const title = s.value == null ? value : String(s.value);

            return (
              <div
                key={key}
                className="min-w-0 text-center p-2 rounded-lg bg-[var(--bg-hover)]/30 transition-colors hover:bg-[var(--bg-hover)]/60"
              >
                <div
                  title={title}
                  className={cn(
                    "font-bold text-[var(--text-primary)] tabular-nums",
                    longValue
                      ? "break-words text-sm leading-snug"
                      : "text-xl",
                  )}
                >
                  {value}
                </div>
                <div className="break-words text-xs text-[var(--text-muted)]">
                  {label}
                </div>
              </div>
            );
          })}
      </div>
    </BlockShell>
  );
}
