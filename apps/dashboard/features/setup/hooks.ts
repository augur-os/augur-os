"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { mcpCall } from "@/lib/mcp/client";
import type { SetupStatus } from "./types";

const CLIENT_TTL_MS = 60_000;

let cache: { ts: number; value: SetupStatus } | null = null;

export interface UseSetupStatusResult {
  data: SetupStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

async function fetchSetupStatus(skipCache: boolean): Promise<SetupStatus> {
  const now = Date.now();
  if (!skipCache && cache && now - cache.ts < CLIENT_TTL_MS) {
    if (cache.value.state !== "alert") {
      return cache.value;
    }
    skipCache = true;
  }
  const value = await mcpCall<SetupStatus>("get-setup-status", {
    skip_cache: skipCache,
  });
  if (!skipCache && value.state === "alert") {
    const refreshed = await mcpCall<SetupStatus>("get-setup-status", {
      skip_cache: true,
    });
    cache = { ts: Date.now(), value: refreshed };
    return refreshed;
  }
  cache = { ts: now, value };
  return value;
}

export function useSetupStatus(): UseSetupStatusResult {
  const [data, setData] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(async (skipCache: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchSetupStatus(skipCache);
      if (mounted.current) {
        setData(next);
      }
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof Error ? err.message : "Failed to load setup status");
        setData(null);
      }
    } finally {
      if (mounted.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const timer = window.setTimeout(() => {
      void load(false);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      mounted.current = false;
    };
  }, [load]);

  const refresh = useCallback(async () => {
    cache = null;
    await load(true);
  }, [load]);

  return { data, loading, error, refresh };
}
