"use client";

import { useEffect, useState, useCallback, useEffectEvent, useMemo } from "react";
import type { ReactNode } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { useMcpPoll } from "@/lib/mcp/useMcpPoll";
import { isFallbackResponse } from "@/lib/mcp/types";
import { mcpCall } from "@/lib/mcp/client";
import { SkillWizard } from "./SkillWizard";
import { RemovalWizard } from "./RemovalWizard";

interface PluginEvent {
  type: "skill_added" | "skill_removed" | "bundle_added" | "bundle_removed";
  bundle: string;
  skill?: string;
  timestamp: string;
  acknowledged: boolean;
}

interface ToastItem {
  id: string;
  event: PluginEvent;
  title: string;
  body: string;
  variant: "success" | "warning" | "info";
}

interface ActiveWizard {
  type: "skill_added" | "removal";
  event: PluginEvent;
}

interface PluginEventNotifierProps {
  /** Polling interval in milliseconds. Default: 60000 */
  pollingIntervalMs?: number;
}

const PLUGIN_EVENT_VARIANT_STYLES: Record<ToastItem["variant"], string> = {
  success: "border-green-500/30 bg-green-500/10",
  warning: "border-amber-500/30 bg-amber-500/10",
  info: "border-blue-500/30 bg-blue-500/10",
};

const PLUGIN_EVENT_VARIANT_ICONS: Record<ToastItem["variant"], ReactNode> = {
  success: <Plus className="size-4 text-green-400 flex-shrink-0" />,
  warning: <Trash2 className="size-4 text-amber-400 flex-shrink-0" />,
  info: <Plus className="size-4 text-blue-400 flex-shrink-0" />,
};

/**
 * PluginEventNotifier — polls /api/plugin-events every 60s and shows toast
 * notifications for unacknowledged plugin events (ADR-122).
 *
 * Toast click opens SkillWizard (skill_added/bundle_added) or
 * RemovalWizard (skill_removed/bundle_removed).
 *
 * Mount in root layout so it runs globally across all pages.
 */
export function PluginEventNotifier({
  pollingIntervalMs = 60_000,
}: PluginEventNotifierProps) {
  const [dismissedToastIds, setDismissedToastIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [activeWizard, setActiveWizard] = useState<ActiveWizard | null>(null);

  const dismissToast = useCallback((id: string) => {
    setDismissedToastIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);
  const dismissToastFromTimer = useEffectEvent((id: string) => {
    setDismissedToastIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  });

  const acknowledgeEvent = useCallback(async (event: PluginEvent) => {
    try {
      await mcpCall("plugin-events-acknowledge", { timestamp: event.timestamp });
    } catch {
      // Non-fatal
    }
  }, []);

  // Poll for plugin events via useMcpPoll
  const { data: pollData } = useMcpPoll<{ events: PluginEvent[] }>(
    "plugin-events",
    "plugin-events-list",
    pollingIntervalMs,
    { preset: "device" },
  );

  const toasts = useMemo(() => {
    if (!pollData?.events || isFallbackResponse(pollData)) {
      return [];
    }

    return pollData.events.flatMap((event): ToastItem[] => {
      const id = `${event.type}-${event.timestamp}`;
      if (event.acknowledged || dismissedToastIds.has(id)) return [];

      const skillName = event.skill ?? event.bundle;
      if (event.type === "skill_added") {
        return [{
          id,
          event,
          title: `New skill detected: ${skillName}`,
          body: `in ${event.bundle} — click to set up`,
          variant: "success",
        }];
      }
      if (event.type === "skill_removed") {
        return [{
          id,
          event,
          title: `Skill removed: ${skillName}`,
          body: `from ${event.bundle} — click to clean up`,
          variant: "warning",
        }];
      }
      if (event.type === "bundle_added") {
        return [{
          id,
          event,
          title: `New bundle detected: ${event.bundle}`,
          body: "Click to set up",
          variant: "info",
        }];
      }
      if (event.type === "bundle_removed") {
        return [{
          id,
          event,
          title: `Bundle removed: ${event.bundle}`,
          body: "Click to clean up",
          variant: "warning",
        }];
      }
      return [];
    });
  }, [dismissedToastIds, pollData]);

  // Auto-dismiss every toast on its own 8s timer so older toasts don't pile up.
  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((toast) =>
      setTimeout(() => dismissToastFromTimer(toast.id), 8_000),
    );
    return () => {
      for (const timer of timers) {
        clearTimeout(timer);
      }
    };
  }, [toasts]);

  function openWizard(toast: ToastItem) {
    dismissToast(toast.id);
    const type =
      toast.event.type === "skill_added" || toast.event.type === "bundle_added"
        ? "skill_added"
        : "removal";
    setActiveWizard({ type, event: toast.event });
  }

  async function handleWizardResolved() {
    if (activeWizard) {
      await acknowledgeEvent(activeWizard.event);
      setActiveWizard(null);
    }
  }

  const renderToast = (toast: ToastItem) => (
    <div
      key={toast.id}
      className={`
        pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl
        border backdrop-blur-md shadow-lg
        animate-in slide-in-from-right-4 duration-200
        ${PLUGIN_EVENT_VARIANT_STYLES[toast.variant]}
      `}
    >
      {PLUGIN_EVENT_VARIANT_ICONS[toast.variant]}

      <button type="button"
        onClick={() => openWizard(toast)}
        className="flex-1 text-left min-w-0"
      >
        <p className="text-sm font-medium text-[var(--text-primary)] truncate">
          {toast.title}
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">
          {toast.body}
        </p>
      </button>

      <button type="button"
        onClick={() => {
          acknowledgeEvent(toast.event);
          dismissToast(toast.id);
        }}
        className="flex-shrink-0 p-1 rounded hover:bg-[var(--bg-hover)] transition-colors"
        aria-label="Dismiss"
      >
        <X className="size-3.5 text-[var(--text-muted)]" />
      </button>
    </div>
  );

  return (
    <>
      {toasts.length > 0 && (
        <>
          <div
            data-testid="plugin-event-toast-stack-mobile"
            className="relative z-40 mt-14 flex flex-col gap-2 px-4 pt-3 pb-2 pointer-events-none md:hidden"
          >
            {toasts.map(renderToast)}
          </div>
          <div
            data-testid="plugin-event-toast-stack"
            className="hidden md:flex fixed bottom-6 right-6 z-50 w-full max-w-sm flex-col gap-2 pointer-events-none"
          >
            {toasts.map(renderToast)}
          </div>
        </>
      )}

      {/* Skill Wizard (for skill_added / bundle_added) */}
      {activeWizard?.type === "skill_added" && (
        <SkillWizard
          bundle={activeWizard.event.bundle}
          skill={activeWizard.event.skill ?? activeWizard.event.bundle}
          open
          onOpenChange={(open) => {
            if (!open) {
              acknowledgeEvent(activeWizard.event);
              setActiveWizard(null);
            }
          }}
          onSetupComplete={handleWizardResolved}
        />
      )}

      {/* Removal Wizard (for skill_removed / bundle_removed) */}
      {activeWizard?.type === "removal" && (
        <RemovalWizard
          bundle={activeWizard.event.bundle}
          skill={activeWizard.event.skill ?? activeWizard.event.bundle}
          canRestore
          alreadyRemoved
          open
          onOpenChange={(open) => {
            if (!open) {
              acknowledgeEvent(activeWizard.event);
              setActiveWizard(null);
            }
          }}
          onCleanupComplete={handleWizardResolved}
          onRestoreComplete={handleWizardResolved}
        />
      )}
    </>
  );
}
