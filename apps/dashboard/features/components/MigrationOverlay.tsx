"use client";

import React from "react";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
import { useMcpHealth } from "@/hooks/useMcpHealth";
import { resolveVisibleSurfacePolicy } from "@/lib/visible-surface-policy";
import { RefreshCcw, AlertTriangle, ScreenShare } from "lucide-react";

function MigrationOverlayInner() {
  // Only enable fast polling when migration/stale config is actively detected.
  // The initial fetch (on mount) always runs regardless of enablePolling.
  // This prevents the heavy /api/mcp/summary endpoint from being hit every 5s at idle.
  const [migrationActive, setMigrationActive] = React.useState(false);
  const { data, refresh } = useMcpHealth({
    enablePolling: migrationActive,
    includeConfigs: true,
    showToasts: false,
    pollInterval: 5000,
  });

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      setMigrationActive(!!data?.migrationInProgress || !!data?.staleMcpConfig);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [data?.migrationInProgress, data?.staleMcpConfig]);

  const { mutate: healSystem, loading: isHealing } = useMcpMutation<
    { success?: boolean; error?: string }
  >("repair-mcp-configs", {
    onSuccess: (result) => {
      if (result.success) {
        refresh();
      } else {
        alert("Failed to heal system: " + (result.error || "Unknown error"));
      }
    },
  });

  const handleHeal = async () => {
    try {
      await healSystem();
    } catch {
      alert("Failed to call healing API");
    }
  };

  if (!data?.migrationInProgress && !data?.staleMcpConfig) {
    return null;
  }

  const isManualMove = data?.staleMcpConfig && !data?.migrationInProgress;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-xl">
      <div className="max-w-md w-full p-8 rounded-2xl border border-cyan-500/30 bg-[var(--bg-card)] shadow-2xl shadow-cyan-500/10 text-center animate-in fade-in zoom-in duration-300">
        <div className="mb-6 flex justify-center">
          <div className="relative">
            <RefreshCcw
              className={`w-16 h-16 text-cyan-400 ${data?.migrationInProgress || isHealing ? "animate-spin-slow" : ""}`}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <ScreenShare className="size-6 text-white" />
            </div>
          </div>
        </div>

        <h2 className="text-2xl font-bold text-white mb-2">
          {isManualMove ? "System Move Detected" : "Augur Migration"}
        </h2>
        <p className="text-[var(--text-secondary)] mb-6">
          {isManualMove
            ? "It looks like the Augur folder was moved manually. Your background services and IDE configurations need to be updated."
            : "System migration in progress. Please wait..."}
        </p>

        <div className="space-y-4 text-left">
          {isManualMove ? (
            <button type="button"
              onClick={handleHeal}
              disabled={isHealing}
              className="w-full py-3 px-4 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-bold transition-all shadow-lg shadow-cyan-500/20 active:scale-[0.98] flex items-center justify-center gap-3"
            >
              {isHealing ? (
                <>
                  <RefreshCcw className="size-5 animate-spin" />
                  Healing System…
                </>
              ) : (
                <>
                  <RefreshCcw className="size-5" />
                  Heal System & Update IDEs
                </>
              )}
            </button>
          ) : (
            <>
              <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex gap-4">
                <AlertTriangle className="size-5 text-cyan-400 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-cyan-200">
                    Action Required
                  </p>
                  <p className="text-xs text-cyan-300/70 mt-0.5">
                    Once the move is complete, you{" "}
                    <strong>MUST restart Claude Desktop</strong> and any other
                    IDEs to pick up the new paths.
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-center gap-3 text-[var(--text-muted)]">
                <div className="size-2 rounded-full bg-cyan-500 animate-pulse" />
                <span className="text-xs uppercase tracking-wider font-semibold">
                  Self-Healing in Progress
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MigrationOverlay() {
  if (resolveVisibleSurfacePolicy() === "no_visible_mutation") {
    return null;
  }

  return <MigrationOverlayInner />;
}
