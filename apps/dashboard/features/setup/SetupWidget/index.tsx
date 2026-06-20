"use client";

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { mcpCall } from "@/lib/mcp/client";
import { useSetupStatus } from "../hooks";
import type { ItemStatus } from "../types";
import { Chip } from "./Chip";
import { CompactBar } from "./CompactBar";
import { FullCard } from "./FullCard";

interface SetupWidgetProps {
  variant?: "sidebar" | "settings" | "page";
}

export function SetupWidget({ variant = "sidebar" }: SetupWidgetProps) {
  const { data, loading, error, refresh } = useSetupStatus();
  const [expanded, setExpanded] = useState(variant !== "sidebar");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPortalTarget(document.body);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleAction = useCallback(async (item: ItemStatus) => {
    setMessage(null);
    if (item.action.type === "route" && item.action.route) {
      window.location.assign(item.action.route);
      return;
    }
    if (item.action.type === "command" && item.action.command) {
      await navigator.clipboard.writeText(item.action.command);
      setMessage(`Copied ${item.action.command}`);
      return;
    }
    if (item.action.type === "mcp" && item.action.mcp_tool) {
      setBusy(true);
      try {
        await mcpCall(item.action.mcp_tool, {});
        await refresh();
      } finally {
        setBusy(false);
      }
    }
  }, [refresh]);

  const handleSkip = useCallback(async (item: ItemStatus, skipped: boolean) => {
    setBusy(true);
    setMessage(null);
    try {
      await mcpCall("set-setup-skipped", { item_id: item.id, skipped });
      await refresh();
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  if (loading && !data) {
    return (
      <div className="rounded-lg border border-[var(--border-color)] p-3 text-xs text-[var(--text-secondary)]">
        Loading setup…
      </div>
    );
  }

  if (error || !data) {
    return (
      <button
        type="button"
        onClick={() => void refresh()}
        className="w-full rounded-lg border border-amber-500/60 bg-amber-500/10 p-3 text-left text-xs text-amber-700"
      >
        Setup status unavailable
      </button>
    );
  }

  if ((data.state === "chip" || data.state === "alert") && !expanded && variant === "sidebar") {
    return <Chip status={data} onOpen={() => setExpanded(true)} />;
  }

  if (data.state === "bar" && !expanded && variant === "sidebar") {
    return <CompactBar status={data} onOpen={() => setExpanded(true)} />;
  }

  const card = (
    <>
      <FullCard
        status={data}
        variant={variant}
        busy={busy || loading}
        onAction={handleAction}
        onSkip={handleSkip}
        onRefresh={() => void refresh()}
        onCollapse={data.state === "card" ? undefined : () => setExpanded(false)}
      />
      {message && (
        <div className="text-xs text-[var(--text-secondary)]" role="status">
          {message}
        </div>
      )}
    </>
  );

  if (variant === "sidebar") {
    const flyout = (
      <div
        data-testid="setup-sidebar-flyout"
        className="fixed inset-x-3 bottom-3 top-16 z-[9999] space-y-2 overflow-y-auto rounded-lg bg-[var(--bg-primary)] p-2 shadow-2xl ring-1 ring-[var(--border-color)] md:bottom-6 md:left-[16rem] md:right-auto md:top-6 md:w-[30rem] md:max-w-[calc(100vw-17rem)]"
      >
        {card}
      </div>
    );

    return portalTarget ? createPortal(flyout, portalTarget) : flyout;
  }

  return (
    <div className="space-y-3">
      {card}
    </div>
  );
}
