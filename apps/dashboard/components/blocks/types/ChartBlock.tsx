"use client";

import { BarChart3 } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { RechartsRenderer } from "@/components/plugin/sections/RechartsRenderer";
import type { ChartDefinition } from "@/components/plugin/sections/types";
import { keyedRenderItems } from "@/lib/stable-render-key";

interface ChartConfig {
  title?: string;
  /** ADR-274 D9 chart configuration — if present, uses RechartsRenderer */
  chart?: ChartDefinition;
  /** Legacy fields for backward compatibility with simple bar charts */
  chartType?: string;
}

interface ChartPoint {
  label?: string;
  value: number;
}

export default function ChartBlock(props: BlockProps<ChartConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Chart", chart } = config;
  const selfFetched = useBlockData<Record<string, unknown>[]>(
    dataSource,
    config,
    "chart",
  );
  const data = (props.data as Record<string, unknown>[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const items = Array.isArray(data) ? data : [];

  // If ADR-274 chart config is present, use RechartsRenderer
  if (chart && chart.x_field && chart.y_field) {
    return (
      <BlockShell
        title={title}
        icon={BarChart3}
        color="blue"
        onExpand={onExpand}
        staleError={error}
      >
        <div className="p-4">
          {loading && (
            <div
              className="rounded-lg bg-[var(--bg-hover)] animate-pulse"
              style={{ height: chart.height ?? 200 }}
            />
          )}

          {!loading && items.length === 0 && !error && (
            <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
              No chart data
            </p>
          )}
          {!loading && items.length === 0 && error && (
            <div className="text-center py-6">
              <p className="text-xs text-red-400/80">Failed to load data</p>
              <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
            </div>
          )}
          {!loading && items.length > 0 && (
            <RechartsRenderer data={items} chart={chart} />
          )}
        </div>
      </BlockShell>
    );
  }

  // Legacy fallback: simple bar chart rendering for blocks without chart config
  const points = items as unknown as ChartPoint[];
  const validPoints = points.filter(
    (p) => typeof p === "object" && p !== null && "value" in p,
  );
  const maxVal =
    validPoints.length > 0
      ? Math.max(...validPoints.map((p) => p.value), 1)
      : 1;

  return (
    <BlockShell
      title={title}
      icon={BarChart3}
      color="blue"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 flex items-end gap-1.5 h-full min-h-[80px]">
        {loading &&
          [45, 70, 55, 80, 40, 65].map((h) => (
            <div
              key={`chart-skeleton-${h}`}
              className="flex-1 rounded-t bg-[var(--bg-hover)] animate-pulse"
              style={{ height: `${h}%` }}
            />
          ))}

        {!loading && validPoints.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic w-full text-center">
            No chart data
          </p>
        )}
        {!loading && validPoints.length === 0 && error && (
          <div className="w-full text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          keyedRenderItems(validPoints).map(({ item: point, key }) => (
            <div key={key} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-gradient-to-t from-[var(--accent-primary)] to-[var(--accent-primary)]/70 transition-all"
                style={{
                  height: `${(point.value / maxVal) * 100}%`,
                  minHeight: 4,
                }}
                title={`${point.label || ""}: ${point.value}`}
              />
              {point.label && (
                <span className="text-[10px] text-[var(--text-muted)] truncate w-full text-center">
                  {point.label}
                </span>
              )}
            </div>
          ))}
      </div>
    </BlockShell>
  );
}
