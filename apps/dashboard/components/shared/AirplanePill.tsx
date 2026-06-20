"use client";

import { useCallback, useState } from "react";
import { AlertTriangle, Cloud, Loader2, Plane } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

const CACHE_KEY = "airplane-status";

interface BackendStatus {
  airplane_mode?: {
    enabled?: boolean;
  };
  ollama?: {
    ready?: boolean;
    has_configured_model?: boolean;
    configured_model?: string;
  };
}

function parseErrorPayload(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      typeof (parsed as { error?: unknown }).error === "string"
    ) {
      return (parsed as { error: string }).error;
    }
  } catch {
    return trimmed;
  }

  return trimmed;
}

export default function AirplanePill() {
  const [pending, setPending] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data, loading, error, refetch } = useMcpQuery<BackendStatus>(
    CACHE_KEY,
    "get-local-backend-status",
    "static",
    { refetchInterval: 5000 },
  );

  const statusReady = !loading && data !== null;
  const enabled = statusReady && data?.airplane_mode?.enabled === true;
  const localReady =
    data?.ollama?.ready === true &&
    data?.ollama?.has_configured_model === true;
  const model = data?.ollama?.configured_model?.trim() || "local model";

  const retryStatus = useCallback(async () => {
    setToggleError(null);
    try {
      await queryClient.invalidateQueries({ queryKey: [CACHE_KEY] });
      refetch();
    } catch (retryError) {
      setToggleError(
        retryError instanceof Error
          ? retryError.message
          : "Failed to retry airplane status",
      );
    }
  }, [queryClient, refetch]);

  const onClick = useCallback(async () => {
    if (!statusReady || pending) return;

    setPending(true);
    setToggleError(null);
    try {
      const response = await fetch("/api/airplane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "toggle" }),
      });

      if (!response.ok) {
        const message = parseErrorPayload(await response.text());
        throw new Error(message || `HTTP ${response.status}`);
      }

      await queryClient.invalidateQueries({ queryKey: [CACHE_KEY] });
    } catch (error) {
      setToggleError(
        error instanceof Error
          ? error.message
          : "Failed to update airplane mode",
      );
    } finally {
      setPending(false);
    }
  }, [pending, queryClient, statusReady]);

  // Only surface the error box when we have no last-known-good status. The
  // backend status is polled every 5s; a single transient "Failed to fetch"
  // should not flicker a red error over an otherwise-working pill — react-query
  // retains the prior `data`, so we keep showing it and ride out the blip.
  if (error && !data) {
    return (
      <div className="flex max-w-full flex-col gap-1">
        <button
          type="button"
          onClick={retryStatus}
          aria-label="Retry airplane mode status read"
          className="inline-flex h-9 max-w-full items-center justify-center gap-2 rounded-full border border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/10 px-3 text-xs font-medium text-[var(--accent-danger)] transition-colors hover:bg-[var(--accent-danger)]/15"
        >
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="shrink-0">Airplane</span>
          <span className="min-w-0 truncate">status error</span>
        </button>
        <p
          role="alert"
          className="max-w-full px-1 text-[11px] leading-snug text-[var(--accent-danger)]"
        >
          Cannot read airplane status: {error}
        </p>
      </div>
    );
  }

  if (!statusReady) {
    return (
      <button
        type="button"
        disabled
        aria-label="Checking airplane mode status"
        className="inline-flex h-9 max-w-full items-center justify-center gap-2 rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-xs font-medium text-[var(--text-muted)] opacity-80"
      >
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        <span className="truncate">Airplane</span>
      </button>
    );
  }

  const Icon = enabled ? (localReady ? Plane : AlertTriangle) : Cloud;
  const label = !enabled
    ? "OFF"
    : localReady
      ? model
      : "setup needed";
  const toneClass = !enabled
    ? "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]"
    : localReady
      ? "border-[var(--accent-warning)]/40 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)] hover:bg-[var(--accent-warning)]/15"
      : "border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)] hover:bg-[var(--accent-danger)]/15";

  return (
    <div className="flex max-w-full flex-col gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        aria-label={`Airplane mode is ${enabled ? "on" : "off"}. Click to toggle.`}
        className={`inline-flex h-9 max-w-full items-center justify-center gap-2 rounded-full border px-3 text-xs font-medium transition-colors disabled:cursor-wait disabled:opacity-70 ${toneClass}`}
      >
        {pending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Icon className="size-3.5 shrink-0" aria-hidden="true" />
        )}
        <span className="shrink-0">Airplane</span>
        <span className="min-w-0 truncate">{label}</span>
      </button>
      {toggleError ? (
        <p
          role="alert"
          className="max-w-full px-1 text-[11px] leading-snug text-[var(--accent-danger)]"
        >
          {toggleError}
        </p>
      ) : null}
    </div>
  );
}
