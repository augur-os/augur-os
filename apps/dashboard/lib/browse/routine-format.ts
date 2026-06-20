export interface RoutineCadence {
  type: "interval" | "cron" | "event" | "manual" | "logon" | string;
  spec: string;
  spec_raw?: string;
  next_run_estimated?: string | null;
  interval_seconds?: number;
}

export function formatCadence(cadence: RoutineCadence | null | undefined): string {
  if (!cadence) return "—";
  if (cadence.type === "logon") return "on logon";
  return cadence.spec || cadence.spec_raw || cadence.type || "—";
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "never";
  const diff = Date.now() - timestamp;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function humanizeTokens(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (numeric >= 1_000_000) return `${(numeric / 1_000_000).toFixed(1)}M`;
  if (numeric >= 1_000) return `${Math.round(numeric / 1_000)}K`;
  return String(Math.round(numeric));
}

export function formatNextRun(iso: string | null | undefined): string {
  if (!iso) return "—";
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "—";
  const diff = timestamp - Date.now();
  if (diff <= 0) return "due";
  if (diff < 3_600_000) return `in ${Math.ceil(diff / 60_000)}m`;
  if (diff < 86_400_000) return `in ${Math.ceil(diff / 3_600_000)}h`;
  return `in ${Math.ceil(diff / 86_400_000)}d`;
}
