"use client";

import { useState, useEffect, useCallback } from "react";
import { mcpCall } from "@/lib/mcp/client";
import type { PathConfig } from "@/components/storage/types";

export type {
  CleanupResult,
  PathCategory,
  PathConfig,
  RagIndex,
  Recommendation,
  SizeAlert,
} from "@/components/storage/types";

// === Hook ===

export function usePathConfig() {
  const [config, setConfig] = useState<PathConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async (refresh: boolean = false) => {
    setLoading(true);
    try {
      const args: Record<string, unknown> = {};
      if (refresh) args.refresh = true;
      const data = await mcpCall<PathConfig>("get-path-config", args);

      if (data.success) {
        setConfig(data);
        setError(null);
      } else {
        setError("Failed to load configuration");
      }
    } catch (e) {
      console.error("Failed to fetch path config:", e);
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchConfig();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchConfig]);

  return {
    config,
    loading,
    error,
    refresh: useCallback(() => fetchConfig(true), [fetchConfig]),
  };
}
