"use client";

/**
 * Polling variant of useMcpQuery — wraps mcpCall() with refetchInterval.
 *
 * Replaces useCachedPoll for routes that map to MCP tools.
 * Used primarily by home-automation pages for periodic device status updates.
 *
 * Includes a global concurrent poll limit (MAX_CONCURRENT_POLLS) to prevent
 * pages with many blocks from spawning excessive parallel polling queries.
 * Polls beyond the limit still fetch once on mount but don't set refetchInterval.
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { mcpCall } from "./client";
import { type PresetName, PRESETS } from "./useMcpQuery";

// ── Global poll concurrency limit ────────────────────────────────────────

const MAX_CONCURRENT_POLLS = 5;
let activePollCount = 0;

// ── Types ────────────────────────────────────────────────────────────────

export interface McpPollOpts<T> {
  /** MCP tool args */
  args?: Record<string, unknown>;
  /** Preset for staleTime / refetchOnWindowFocus (default: "device") */
  preset?: PresetName;
  /** Transform the raw MCP response */
  select?: (raw: unknown) => T;
  /** Disable the query (e.g. when a prerequisite is missing) */
  enabled?: boolean;
}

export interface McpPollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

// ── useMcpPoll ───────────────────────────────────────────────────────────

export function useMcpPoll<T = unknown>(
  key: string | string[],
  tool: string,
  intervalMs: number,
  opts?: McpPollOpts<T>,
): McpPollResult<T> {
  const preset = opts?.preset ?? "device";
  const presetConfig = PRESETS[preset];
  const queryKey: unknown[] = Array.isArray(key) ? [...key] : [key];

  // Include tool + args in cache key for differentiation
  queryKey.push(tool);
  if (opts?.args && Object.keys(opts.args).length > 0) {
    queryKey.push(opts.args);
  }

  const enabled = opts?.enabled !== false;

  // ── Concurrency gate ────────────────────────────────────────────────
  // The state value drives the refetchInterval decision.
  const [canPoll, setCanPoll] = useState(false);
  useEffect(() => {
    if (!enabled) return;

    let didAcquireSlot = false;
    const timer = window.setTimeout(() => {
      if (activePollCount < MAX_CONCURRENT_POLLS) {
        activePollCount++;
        didAcquireSlot = true;
        setCanPoll(true);
      } else {
        didAcquireSlot = false;
        setCanPoll(false);
      }
    }, 0);

    return () => {
      window.clearTimeout(timer);
      if (didAcquireSlot) {
        activePollCount--;
      }
    };
  }, [enabled]);

  const { data, isLoading, error, refetch } = useQuery<unknown, Error, T>({
    queryKey,
    queryFn: () => mcpCall<T>(tool, opts?.args ?? {}),
    staleTime: presetConfig.staleTime,
    refetchOnWindowFocus: presetConfig.refetchOnWindowFocus,
    refetchInterval: canPoll ? intervalMs : false,
    enabled,
    placeholderData: keepPreviousData,
    select: opts?.select,
  });

  const stableRefetch = useCallback(() => {
    void refetch();
  }, [refetch]);

  return {
    data: data ?? null,
    loading: isLoading,
    error: error ? error.message : null,
    refetch: stableRefetch,
  };
}
