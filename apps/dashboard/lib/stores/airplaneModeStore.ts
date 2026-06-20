"use client";

import { useCallback, useSyncExternalStore } from "react";
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

/**
 * Backwards-compatible hook for code that previously read the localStorage-
 * backed Zustand store. Source of truth is preferences.yaml via the
 * get-local-backend-status MCP tool.
 */
export function useAirplaneModeStore(): {
  airplaneMode: boolean;
  airplaneModeReady: boolean;
  airplaneBackendReady: boolean;
  airplaneLocalModel: string | null;
  airplaneModeError: string | null;
  setAirplaneMode: (enabled: boolean) => Promise<void>;
  toggleAirplaneMode: () => Promise<void>;
} {
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const queryClient = useQueryClient();
  const { data, loading, error } = useMcpQuery<BackendStatus>(
    CACHE_KEY,
    "get-local-backend-status",
    "static",
    { refetchInterval: 5000 },
  );

  const airplaneMode = data?.airplane_mode?.enabled === true;
  const airplaneModeReady = mounted && !loading && data !== null;
  const airplaneBackendReady =
    data?.ollama?.ready === true &&
    data?.ollama?.has_configured_model === true;
  const airplaneLocalModel = data?.ollama?.configured_model?.trim() || null;

  const post = useCallback(
    async (action: "on" | "off" | "toggle") => {
      const response = await fetch("/api/airplane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });

      if (!response.ok) {
        const message = (await response.text()).trim();
        throw new Error(
          message
            ? `Failed to update airplane mode via /api/airplane: ${message}`
            : `Failed to update airplane mode via /api/airplane: HTTP ${response.status}`,
        );
      }

      await queryClient.invalidateQueries({ queryKey: [CACHE_KEY] });
    },
    [queryClient],
  );

  const setAirplaneMode = useCallback(
    async (enabled: boolean) => post(enabled ? "on" : "off"),
    [post],
  );

  const toggleAirplaneMode = useCallback(() => post("toggle"), [post]);

  return {
    airplaneMode,
    airplaneModeReady,
    airplaneBackendReady,
    airplaneLocalModel,
    airplaneModeError: error,
    setAirplaneMode,
    toggleAirplaneMode,
  };
}
