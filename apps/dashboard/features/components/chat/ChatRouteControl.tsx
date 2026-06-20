"use client";

import { useCallback, useMemo, useState } from "react";
import { Cloud, RotateCcw, Settings, WifiOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";
import type { CliId } from "./types";

export interface ChatRouteStartOptions {
  airplaneMode?: boolean;
}

interface ChatRouteControlProps {
  cliId: CliId;
  isRunning: boolean;
  startCli: (
    cliId: CliId,
    options?: ChatRouteStartOptions,
  ) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  onClear?: () => void;
}

interface OllamaIntegrationsResponse {
  integrations?: string[];
}

interface SessionBackendStatus {
  status?: string;
  sessionAirplaneMode?: boolean;
  sessionLocalModel?: string | null;
}

function integrationIdForCli(cliId: CliId): string {
  return cliId === "copilot-cli" ? "copilot" : cliId;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function ChatRouteControl({
  cliId,
  isRunning,
  startCli,
  stopCli,
  onClear,
}: ChatRouteControlProps) {
  const {
    airplaneMode,
    airplaneModeReady,
    airplaneBackendReady,
    airplaneLocalModel,
    airplaneModeError,
    setAirplaneMode,
  } = useAirplaneModeStore();
  const {
    data: integrationsData,
    loading: integrationsLoading,
    error: integrationsError,
  } = useMcpQuery<OllamaIntegrationsResponse>(
    "ollama-integrations",
    "list-ollama-integrations",
    "static",
    { refetchInterval: 60000 },
  );
  const { data: sessionBackend } = useQuery({
    queryKey: ["cli-session-backend", cliId],
    queryFn: async (): Promise<SessionBackendStatus | null> => {
      const response = await fetch(`/api/cli?cliId=${encodeURIComponent(cliId)}`);
      if (!response.ok) return null;
      return (await response.json()) as SessionBackendStatus;
    },
    refetchInterval: 4000,
    staleTime: 2000,
  });
  const [open, setOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const targetAirplaneMode = !airplaneMode;
  const targetRouteLabel = targetAirplaneMode ? "offline" : "cloud";
  const buttonLabel = targetAirplaneMode ? "Use offline" : "Use cloud";
  const preferenceRouteLabel = airplaneMode ? "offline" : "cloud";
  const localModel = airplaneLocalModel?.trim() || "configured local model";
  const directOllama = cliId === "ollama";
  const integrationId = integrationIdForCli(cliId);

  const unavailableReason = useMemo(() => {
    if (airplaneModeError) {
      return `Cannot read chat route preference: ${airplaneModeError}`;
    }
    if (!targetAirplaneMode) return null;
    if (!airplaneBackendReady || !airplaneLocalModel?.trim()) {
      return "Local backend setup is required before chats can use offline routing.";
    }
    if (directOllama) return null;
    if (integrationsLoading) {
      return "Local integration support is still loading.";
    }
    if (integrationsError) {
      return integrationsError;
    }
    if (!Array.isArray(integrationsData?.integrations)) {
      return "Local integration support is unavailable.";
    }
    if (!integrationsData.integrations.includes(integrationId)) {
      return `${cliId} is not configured for offline routing.`;
    }
    return null;
  }, [
    airplaneBackendReady,
    airplaneLocalModel,
    airplaneModeError,
    cliId,
    directOllama,
    integrationId,
    integrationsData,
    integrationsError,
    integrationsLoading,
    targetAirplaneMode,
  ]);

  const actionEnabled = unavailableReason === null;
  const liveSessionAirplaneMode =
    sessionBackend?.status === "running" &&
    typeof sessionBackend.sessionAirplaneMode === "boolean"
      ? sessionBackend.sessionAirplaneMode
      : null;
  const liveRouteLabel =
    liveSessionAirplaneMode !== null
      ? liveSessionAirplaneMode
        ? `offline (${sessionBackend?.sessionLocalModel?.trim() || "local model"})`
        : "cloud"
      : null;
  const chatRouteSummary = liveRouteLabel
    ? liveRouteLabel
    : isRunning
      ? "route status unavailable"
      : "no running session";
  const liveRouteDiffers =
    liveSessionAirplaneMode !== null &&
    (liveSessionAirplaneMode !== airplaneMode ||
      (airplaneMode &&
        liveSessionAirplaneMode &&
        (sessionBackend?.sessionLocalModel?.trim() || null) !==
          (airplaneLocalModel?.trim() || null)));

  const handleOpenChange = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setActionError(null);
    }
  }, []);

  const openDialog = useCallback(() => {
    setActionError(null);
    setOpen(true);
  }, []);

  const switchForNewChats = useCallback(async () => {
    if (!actionEnabled || updating) return;
    setUpdating(true);
    setActionError(null);
    try {
      await setAirplaneMode(targetAirplaneMode);
      setOpen(false);
    } catch (error) {
      setActionError(
        errorMessage(error, "Failed to update the chat route preference."),
      );
    } finally {
      setUpdating(false);
    }
  }, [actionEnabled, setAirplaneMode, targetAirplaneMode, updating]);

  const switchAndRestart = useCallback(async () => {
    if (!actionEnabled || updating) return;
    setUpdating(true);
    setActionError(null);
    try {
      await setAirplaneMode(targetAirplaneMode);
      await stopCli(cliId);
      onClear?.();
      await startCli(cliId, { airplaneMode: targetAirplaneMode });
      setOpen(false);
    } catch (error) {
      setActionError(
        errorMessage(error, "Failed to restart chat with the selected route."),
      );
    } finally {
      setUpdating(false);
    }
  }, [
    actionEnabled,
    cliId,
    onClear,
    setAirplaneMode,
    startCli,
    stopCli,
    targetAirplaneMode,
    updating,
  ]);

  if (!airplaneModeReady && !airplaneModeError) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <button
        type="button"
        onClick={openDialog}
        className="inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2 text-[11px] font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-primary)]/70 hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
        aria-label={`${buttonLabel} for chat routing`}
        title={`Switch chat route to ${targetRouteLabel}`}
      >
        {targetAirplaneMode ? (
          <WifiOff className="size-3.5" aria-hidden="true" />
        ) : (
          <Cloud className="size-3.5" aria-hidden="true" />
        )}
        <span>{buttonLabel}</span>
      </button>

      <DialogContent className="max-w-lg" portal>
        <DialogHeader>
          <DialogTitle>Switch chat route</DialogTitle>
          <DialogDescription>
            {targetAirplaneMode
              ? `New chats will use the configured local model (${localModel}).`
              : "New chats will use cloud routing."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 p-6">
          <div className="rounded-lg border border-[var(--border-color)]/70 bg-[var(--bg-secondary)]/70 px-3 py-2 text-xs text-[var(--text-muted)]">
            <p className="font-medium text-[var(--text-primary)]">
              Preference: {preferenceRouteLabel}
            </p>
            <p className="mt-1">
              This chat: {chatRouteSummary}
              {liveRouteDiffers ? " (differs until restart)" : ""}
            </p>
          </div>

          {unavailableReason ? (
            <div
              role="alert"
              className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300"
            >
              {unavailableReason}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              Switch the default route for future chats, or restart this chat to
              apply the route immediately.
            </p>
          )}

          {actionError && (
            <div
              role="alert"
              className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-300"
            >
              {actionError}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          {actionEnabled ? (
            <>
              <a
                href="/settings/ai"
                className="inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-primary)]"
              >
                <Settings className="size-3.5" aria-hidden="true" />
                Open Settings
              </a>
              {isRunning && (
                <button
                  type="button"
                  onClick={() => {
                    void switchAndRestart();
                  }}
                  disabled={updating}
                  className="inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RotateCcw className="size-3.5" aria-hidden="true" />
                  Switch + restart
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  void switchForNewChats();
                }}
                disabled={updating}
                className="inline-flex h-9 items-center justify-center whitespace-nowrap rounded-md bg-[var(--accent-primary)] px-3 text-sm font-medium text-[var(--accent-foreground)] transition-colors hover:bg-[var(--accent-primary)]/90 disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  backgroundColor: "var(--accent-primary)",
                  color: "var(--accent-foreground)",
                }}
              >
                Switch for new chats
              </button>
            </>
          ) : (
            <a
              href="/settings/ai"
              className="inline-flex h-9 items-center justify-center gap-1.5 whitespace-nowrap rounded-md bg-[var(--accent-primary)] px-3 text-sm font-medium text-[var(--accent-foreground)] transition-colors hover:bg-[var(--accent-primary)]/90"
              style={{
                backgroundColor: "var(--accent-primary)",
                color: "var(--accent-foreground)",
              }}
            >
              <Settings className="size-3.5" aria-hidden="true" />
              Open Settings
            </a>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
