"use client";

import { useQuery } from "@tanstack/react-query";

/**
 * ADR-116: CLI health poller hook.
 * Pings the CLI status endpoint at the given interval.
 * Returns true if the CLI appears stale (not responding).
 */
export function useCliHealthPoller(
  cliId: string | null,
  intervalMs = 30000,
): boolean {
  const query = useQuery({
    queryKey: ["cli-health", cliId],
    enabled: Boolean(cliId),
    refetchInterval: intervalMs,
    retry: false,
    queryFn: async () => {
      const res = await fetch(`/api/cli?cliId=${cliId}`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) {
        throw new Error(`CLI health check failed with ${res.status}`);
      }
      const data = await res.json();
      if (data.status !== "running") {
        throw new Error("CLI is not running");
      }
      return true;
    },
  });

  return Boolean(cliId && query.failureCount >= 2);
}
