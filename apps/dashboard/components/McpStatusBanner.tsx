"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { AlertTriangle, RefreshCw, X, Loader2 } from "lucide-react";
import {
  decideMcpBannerState,
  type McpBannerState,
  FAILURE_THRESHOLD,
} from "@/components/mcpBannerState";

/**
 * Global MCP server health banner.
 *
 * Probes /api/mcp/tool with the lightweight "health" tool on mount and
 * at a regular interval. The MCP bridge spawns a Python backend that takes
 * tens of seconds to cold-start, so during boot the probe fails — that is
 * surfaced as a calm "MCP starting…" state, NOT the red "down" alarm. The
 * red alarm is reserved for a genuine outage (startup that never succeeds
 * past the grace window, or a drop after a prior successful connect). See
 * mcpBannerState.ts for the decision logic and its tests.
 *
 * Auto-dismisses once the server recovers.
 */

const PROBE_INTERVAL_MS = 15_000;
const PROBE_TIMEOUT_MS = 12_000;

export default function McpStatusBanner() {
  const [state, setState] = useState<McpBannerState>("checking");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [dismissed, setDismissed] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const failuresRef = useRef(0);
  const hasConnectedRef = useRef(false);
  const mountTimeRef = useRef<number>(0);

  const applyOutcome = useCallback((outcome: "ok" | "failure", msg: string) => {
    if (outcome === "ok") {
      failuresRef.current = 0;
      hasConnectedRef.current = true;
    } else {
      failuresRef.current += 1;
    }

    const next = decideMcpBannerState({
      outcome,
      consecutiveFailures: failuresRef.current,
      hasConnectedEver: hasConnectedRef.current,
      elapsedMs: Date.now() - mountTimeRef.current,
      failureThreshold: FAILURE_THRESHOLD,
    });

    setState(next);
    if (next === "ok") {
      setDismissed(false);
      setErrorMsg("");
    } else if (next === "down") {
      setErrorMsg(msg);
    }
  }, []);

  const probe = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

      const res = await fetch("/api/mcp/tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "health", args: {} }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (res.ok) {
        applyOutcome("ok", "");
        return;
      }

      const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      const msg = body.error || `MCP server returned ${res.status}`;

      // Only treat server-level failures as outages, not individual tool errors.
      if (
        res.status >= 500 ||
        (res.status === 400 &&
          (msg.includes("failed to initialize") ||
            msg.includes("not connected") ||
            msg.includes("disconnected")))
      ) {
        applyOutcome("failure", msg);
      } else {
        // Tool-level error but server is reachable.
        applyOutcome("ok", "");
      }
    } catch {
      applyOutcome("failure", "MCP server unreachable");
    }
  }, [applyOutcome]);

  useEffect(() => {
    // Capture mount time here (not in a ref initializer) so render stays pure.
    mountTimeRef.current = Date.now();

    // Initial probe after a short delay (let the page hydrate first)
    const initial = setTimeout(probe, 2_000);

    intervalRef.current = setInterval(probe, PROBE_INTERVAL_MS);

    return () => {
      clearTimeout(initial);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [probe]);

  // Calm startup state: the MCP backend is still booting, not down.
  if (state === "starting") {
    return (
      <div className="fixed top-0 left-0 right-0 z-[70] flex items-center gap-2 px-4 py-2.5 bg-amber-500/95 text-white text-sm font-medium backdrop-blur-sm shadow-lg">
        <Loader2 className="size-4 flex-shrink-0 animate-spin" />
        <span className="truncate">
          Augur MCP is starting up: data will appear in a moment…
        </span>
      </div>
    );
  }

  if (state !== "down" || dismissed) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[70] flex items-center justify-between gap-3 px-4 py-2.5 bg-red-500/95 text-white text-sm font-medium backdrop-blur-sm shadow-lg">
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle className="size-4 flex-shrink-0" />
        <span className="truncate">
          MCP server is down: dashboard data unavailable.
          {errorMsg && (
            <span className="ml-1 font-normal opacity-80">({errorMsg})</span>
          )}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button type="button"
          onClick={() => {
            setState("checking");
            probe();
          }}
          className="flex items-center gap-1 px-2 py-1 rounded bg-white/20 hover:bg-white/30 transition-colors text-xs"
        >
          <RefreshCw className="size-3" />
          Retry
        </button>
        <button type="button"
          onClick={() => setDismissed(true)}
          className="p-1 rounded hover:bg-white/20 transition-colors"
          title="Dismiss (will reappear on next check if still down)"
          aria-label="Dismiss MCP status banner"
        >
          <X className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
