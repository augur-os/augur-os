"use client";

import { useState } from "react";
import { TrendingUp } from "lucide-react";
import type { BlockProps, StatCardAction } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { mcpCall } from "@/lib/mcp/client";
import { StatCard } from "@/components/ui/StatCard";
import { BlockShell } from "../BlockShell";

interface StatCardConfig {
  value?: string | number;
  label?: string;
  color?: "red" | "orange" | "yellow" | "green" | "cyan" | "neutral";
  trend?: string;
  emoji?: string;
  /** Optional inline action button (e.g. "Sync now" → rag-sync) */
  action?: StatCardAction;
}

interface StatData {
  value: string | number;
  label?: string;
  trend?: string;
}

type ActionState = "idle" | "running" | "done" | "error";

export default function StatCardBlock(props: BlockProps<StatCardConfig>) {
  const { config, dataSource, mode } = props;
  const { label = "Stat", color = "cyan", emoji, action } = config;
  const selfFetched = useBlockData<StatData>(
    dataSource,
    config,
    "stat-card",
  );
  const data = (props.data as StatData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const value = data?.value ?? config.value ?? "—";
  const trend = data?.trend ?? config.trend;

  const [actionState, setActionState] = useState<ActionState>("idle");

  async function runAction() {
    if (!action || actionState === "running") return;
    setActionState("running");
    try {
      // Long-running tools (rag-sync can take 5-60s) — stay in "running"
      // until the call resolves.
      const result = await mcpCall<Record<string, unknown>>(action.mcp_tool, {});
      // MCP tools report tool-level failure as a 200 payload
      // ({ok: false, error} or {error: "..."}), not an HTTP error.
      if (
        result &&
        typeof result === "object" &&
        (result.ok === false ||
          (typeof result.error === "string" && result.error.length > 0))
      ) {
        setActionState("error");
        return;
      }
      setActionState("done");
      // Prefix-invalidate every block-data query for this tool so both the
      // self-fetched query and any renderer-lifted query refetch freshness.
      selfFetched.invalidate();
    } catch {
      setActionState("error");
    }
  }

  return (
    <BlockShell title={label} icon={TrendingUp} color="cyan" staleError={error}>
      <div className="p-3 flex flex-col items-center justify-center">
        {loading ? (
          <div className="h-12 w-24 rounded bg-[var(--bg-hover)] animate-pulse" />
        ) : !data && config.value === undefined ? (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No stat data available
          </p>
        ) : (
          <StatCard
            value={value}
            label={data?.label ?? label}
            color={color}
            trend={trend}
            emoji={emoji}
          />
        )}
        {action && (
          <button
            type="button"
            onClick={runAction}
            disabled={actionState === "running"}
            className="mt-2 text-xs text-[var(--text-muted)] hover:text-[var(--accent-primary)] transition-colors disabled:opacity-50 disabled:cursor-wait cursor-pointer"
          >
            {actionState === "running"
              ? "Syncing…"
              : actionState === "error"
                ? `${action.label} failed — retry`
                : action.label}
          </button>
        )}
      </div>
    </BlockShell>
  );
}
