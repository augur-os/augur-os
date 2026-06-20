"use client";

import { Activity, Clock, AlertTriangle } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { formatTimeAgo } from "@/lib/timestamps";

interface HealthConfig {
  title?: string;
}

interface HealthData {
  status?: string;
  lastCheck?: string;
  last_check?: string;
  errors24h?: number;
  errors_24h?: number;
  uptime?: string;
}

const STATUS_STYLES: Record<string, { dot: string; color: string; label: string }> = {
  healthy: { dot: "bg-emerald-500", color: "text-emerald-500", label: "Connected" },
  running: { dot: "bg-emerald-500", color: "text-emerald-500", label: "Running" },
  degraded: { dot: "bg-amber-500", color: "text-amber-500", label: "Degraded" },
  error: { dot: "bg-red-500", color: "text-red-500", label: "Error" },
  stopped: { dot: "bg-gray-400", color: "text-gray-400", label: "Stopped" },
  unknown: { dot: "bg-gray-400", color: "text-gray-400", label: "Unknown" },
};

export default function HealthBlock(props: BlockProps<HealthConfig>) {
  const { config, dataSource } = props;
  const { title = "Health" } = config;
  const selfFetched = useBlockData<HealthData>(dataSource, config, "health");
  const raw = (props.data as HealthData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const status = raw?.status ?? "unknown";
  const lastCheck = raw?.lastCheck ?? raw?.last_check;
  const errors24h = raw?.errors24h ?? raw?.errors_24h ?? 0;
  const statusCfg = STATUS_STYLES[status] ?? STATUS_STYLES.unknown;

  return (
    <BlockShell title={title} icon={Activity} color="emerald" staleError={error}>
      <div className="p-4 grid grid-cols-3 gap-3">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div
              key={i}
              className="rounded-xl bg-[var(--bg-hover)]/30 px-4 py-3"
            >
              <div className="h-3 w-12 rounded bg-[var(--bg-hover)] animate-pulse mb-2" />
              <div className="h-5 w-16 rounded bg-[var(--bg-hover)] animate-pulse" />
            </div>
          ))}

        {!loading && !raw && !error && (
          <p className="col-span-3 text-xs text-[var(--text-muted)] italic text-center">
            No health data
          </p>
        )}


        {!loading && raw && (
          <>
            {/* Status */}
            <div className="rounded-xl bg-[var(--bg-hover)]/30 px-4 py-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <Activity className="size-3.5" />
                <span className="text-xs font-medium">Status</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusCfg.dot}`} />
                <span className={`text-sm font-semibold ${statusCfg.color}`}>
                  {statusCfg.label}
                </span>
              </div>
            </div>

            {/* Last Check */}
            <div className="rounded-xl bg-[var(--bg-hover)]/30 px-4 py-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <Clock className="size-3.5" />
                <span className="text-xs font-medium">Last Check</span>
              </div>
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {lastCheck ? formatTimeAgo(lastCheck) : "N/A"}
              </span>
            </div>

            {/* Errors 24h */}
            <div className="rounded-xl bg-[var(--bg-hover)]/30 px-4 py-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-[var(--text-muted)]">
                <AlertTriangle className="size-3.5" />
                <span className="text-xs font-medium">Errors (24h)</span>
              </div>
              <span
                className={`text-sm font-semibold ${
                  errors24h > 0 ? "text-[var(--text-error,#f87171)]" : "text-[var(--text-primary)]"
                }`}
              >
                {errors24h}
              </span>
            </div>
          </>
        )}
      </div>
    </BlockShell>
  );
}
