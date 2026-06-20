"use client";

import { useEffect } from "react";
import { useMCPContext } from "../hooks/useMCPContext";

const SESSION_STORAGE_KEY = "augur_session_id";

function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "dashboard-main";

  const existing = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;

  const id = `dashboard-${Date.now()}`;
  sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  return id;
}

/**
 * ContextManager Component
 *
 * Invisible component that manages MCP context switching.
 * Placed in root layout to automatically switch tools on navigation.
 *
 * This component:
 * - Monitors pathname changes
 * - Calls MCPBridge.switchContext() automatically
 * - Enables hover preloading on navigation links
 * - Tracks per-session focus state (ADR-254)
 * - Cleans up session file on tab close via beforeunload
 */
export default function ContextManager() {
  // Hook handles context-switching logic
  useMCPContext();

  // Session lifecycle: generate ID + register beforeunload cleanup (ADR-254)
  useEffect(() => {
    const sessionId = getOrCreateSessionId();

    const handleBeforeUnload = () => {
      // Best-effort cleanup via the existing focus-state route.
      // sendBeacon cannot use mcpCall, so we POST a "cleanup" action
      // through the existing /api/focus-state endpoint.
      navigator.sendBeacon(
        "/api/focus-state",
        new Blob(
          [JSON.stringify({
            current_page: "/__cleanup__",
            skill_name: "__cleanup__",
            bundle: "__cleanup__",
            session_id: sessionId,
            source: "beforeunload",
          })],
          { type: "application/json" },
        ),
      );
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  // No UI - just side effects
  return null;
}
