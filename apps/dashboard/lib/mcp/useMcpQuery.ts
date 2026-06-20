"use client";

/**
 * React Query wrapper around mcpCall() for GET-style data fetching.
 *
 * Replaces useCachedFetch for routes that map to MCP tools.
 * Supports fallback data, presets, and the same API surface as useCachedFetch.
 */

import {
  useQuery,
  keepPreviousData,
} from "@tanstack/react-query";
import { useCallback } from "react";
import { mcpCall } from "./client";

// ── Preset System (mirrors useCachedFetch) ───────────────────────────────

export type PresetName =
  | "device"
  | "realtime"
  | "live"
  | "user-data"
  | "config"
  | "static";

interface PresetConfig {
  staleTime: number;
  refetchOnWindowFocus: boolean;
}

export const PRESETS: Record<PresetName, PresetConfig> = {
  device: { staleTime: 10_000, refetchOnWindowFocus: true },
  realtime: { staleTime: 30_000, refetchOnWindowFocus: true },
  live: { staleTime: 120_000, refetchOnWindowFocus: false },
  "user-data": { staleTime: 300_000, refetchOnWindowFocus: false },
  config: { staleTime: 600_000, refetchOnWindowFocus: false },
  static: { staleTime: Infinity, refetchOnWindowFocus: false },
};

// ── useMcpQuery ──────────────────────────────────────────────────────────

export interface McpQueryOpts<T> {
  /** MCP tool args */
  args?: Record<string, unknown>;
  /** Data returned on error instead of showing error state */
  fallback?: T;
  /** Transform the raw MCP response */
  select?: (raw: unknown) => T;
  /** Disable the query (e.g. when a prerequisite is missing) */
  enabled?: boolean;
  /** Polling interval passed through to React Query. */
  refetchInterval?: number | false;
}

export interface McpQueryResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useMcpQuery<T = unknown>(
  key: string | string[],
  tool: string,
  preset: PresetName,
  opts?: McpQueryOpts<T>,
): McpQueryResult<T> {
  const presetConfig = PRESETS[preset];
  const queryKey: unknown[] = Array.isArray(key) ? [...key] : [key];

  // Include tool + args in cache key for differentiation
  queryKey.push(tool);
  if (opts?.args && Object.keys(opts.args).length > 0) {
    queryKey.push(opts.args);
  }

  const enabled = opts?.enabled === undefined || opts.enabled;

  const { data, status, error, refetch } = useQuery<unknown, Error, T>({
    queryKey,
    queryFn: () =>
      mcpCall<T>(tool, opts?.args ?? {}, {
        fallback: opts?.fallback,
      }),
    staleTime: presetConfig.staleTime,
    refetchOnWindowFocus: presetConfig.refetchOnWindowFocus,
    refetchInterval: opts?.refetchInterval,
    enabled,
    placeholderData: keepPreviousData,
    select: opts?.select,
  });

  const stableRefetch = useCallback(() => {
    refetch();
  }, [refetch]);

  return {
    data: data ?? null,
    loading: status === "pending",
    error: error ? error.message : null,
    refetch: stableRefetch,
  };
}
