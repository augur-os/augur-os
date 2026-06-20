"use client";

import { usePathname } from "next/navigation";
import { useEffect, useCallback, useRef } from "react";
import { getMCPContextClient } from "@/lib/mcp/MCPContextClient";

function sendFocusStateFallback(body: string) {
  fetch("/api/focus-state", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body,
  }).catch(() => {});
}

/**
 * useMCPContext Hook
 *
 * Automatically switches MCP tool context when user navigates between pages.
 * All pages use switchContext for unified context switching (ADR-254).
 * Visibility guard prevents background tabs from polluting signals.
 *
 * Usage:
 * ```tsx
 * const { handleLinkHover } = useMCPContext();
 *
 * <Link href="/brain" onMouseEnter={() => handleLinkHover('/brain')}>
 *   Brain
 * </Link>
 * ```
 */
export function useMCPContext({
  autoSwitch = true,
}: { autoSwitch?: boolean } = {}) {
  const pathname = usePathname();
  const switchingRef = useRef(false);
  const lastPathnameRef = useRef(pathname);
  const focusStateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const preloadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const preloadedPagesRef = useRef<Set<string> | null>(null);
  if (preloadedPagesRef.current === null) {
    preloadedPagesRef.current = new Set<string>();
  }
  const preloadedPages = preloadedPagesRef.current;
  const clearContextTimers = useCallback(() => {
    if (focusStateTimerRef.current) clearTimeout(focusStateTimerRef.current);
    if (preloadTimerRef.current) clearTimeout(preloadTimerRef.current);
  }, []);

  // Auto-switch context when pathname changes
  useEffect(() => {
    if (!autoSwitch) return;
    // Skip if pathname hasn't actually changed
    if (lastPathnameRef.current === pathname) {
      return;
    }

    if (focusStateTimerRef.current) {
      clearTimeout(focusStateTimerRef.current);
      focusStateTimerRef.current = null;
    }

    // Skip context switching for the MCP config page itself
    // (it should show the current context without changing it)
    if (pathname === "/hands/mcp-config") {
      console.log(
        "[useMCPContext] Skipping context switch for MCP config page",
      );
      lastPathnameRef.current = pathname;
      return;
    }

    // Skip if already switching
    if (switchingRef.current) {
      console.log("[useMCPContext] Switch already in progress, skipping");
      return;
    }

    const contextClient = getMCPContextClient();

    // Skip if already on this page
    if (contextClient.getCurrentPage() === pathname) {
      lastPathnameRef.current = pathname;
      return;
    }

    // Visibility guard: prevent background tabs from polluting signals (ADR-254)
    if (document.visibilityState !== "visible") {
      console.log("[useMCPContext] Skipping context switch — tab not visible");
      return;
    }

    const performSwitch = async () => {
      switchingRef.current = true;
      try {
        console.log(`[useMCPContext] Switching context to: ${pathname}`);
        await contextClient.switchContext(pathname);
        console.log(`[useMCPContext] Context updated successfully`);
        lastPathnameRef.current = pathname;

        // Debounced focus state broadcast — coalesce rapid navigations
        // into a single POST (prevents flooding set_config_tool on fast browsing)
        if (focusStateTimerRef.current) {
          clearTimeout(focusStateTimerRef.current);
        }
        const capturedPathname = pathname;
        focusStateTimerRef.current = setTimeout(() => {
          if (typeof document !== "undefined" && document.visibilityState !== "visible") {
            return;
          }

          const segment = capturedPathname.replace(/^\//, "").split("/")[0] || "home";
          const sessionId =
            typeof sessionStorage !== "undefined"
              ? sessionStorage.getItem("augur_session_id") || "dashboard-main"
              : "dashboard-main";
          const body = JSON.stringify({
            current_page: capturedPathname,
            skill_name: segment,
            bundle: segment,
            session_id: sessionId,
          });
          if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
            const sent = navigator.sendBeacon(
              "/api/focus-state",
              new Blob([body], { type: "application/json" }),
            );
            if (sent) return;
          }
          sendFocusStateFallback(body);
        }, 2000);
      } catch (error) {
        console.error("[useMCPContext] Context switch failed:", error);
      } finally {
        switchingRef.current = false;
      }
    };

    performSwitch();

    return () => {
      if (focusStateTimerRef.current) {
        clearTimeout(focusStateTimerRef.current);
        focusStateTimerRef.current = null;
      }
    };
  }, [pathname, autoSwitch]);

  // Cleanup timers on unmount
  useEffect(() => {
    return clearContextTimers;
  }, [clearContextTimers]);

  // Recover missed context switches when tab becomes visible (ADR-254)
  useEffect(() => {
    const handler = () => {
      if (
        document.visibilityState === "visible" &&
        lastPathnameRef.current !== pathname
      ) {
        lastPathnameRef.current = ""; // Force re-trigger via pathname effect
      }
    };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, [pathname]);

  /**
   * Handle link hover to preload tools
   *
   * @param targetPage - Page path to preload (e.g., "/brain", "/workforce")
   */
  const handleLinkHover = useCallback((targetPage: string) => {
    const contextClient = getMCPContextClient();

    // Skip if already on this page
    if (contextClient.getCurrentPage() === targetPage) {
      return;
    }

    // Skip if context switch is in progress
    if (contextClient.isContextSwitching()) {
      return;
    }

    // Skip if already preloaded this page in this session
    if (preloadedPages.has(targetPage)) {
      return;
    }

    // Debounce preload — only fire after 400ms of sustained hover
    // to prevent MCP flooding from casual mouse movement over nav
    if (preloadTimerRef.current) {
      clearTimeout(preloadTimerRef.current);
    }

    preloadTimerRef.current = setTimeout(() => {
      // Re-check conditions after delay
      if (
        contextClient.getCurrentPage() === targetPage ||
        contextClient.isContextSwitching() ||
        preloadedPages.has(targetPage)
      ) {
        return;
      }

      preloadedPages.add(targetPage);

      const performPreload = async () => {
        try {
          console.log(`[useMCPContext] Preloading context for: ${targetPage}`);
          await contextClient.preloadContext(targetPage);
          console.log(`[useMCPContext] Preload complete for: ${targetPage}`);
        } catch (error) {
          console.warn("[useMCPContext] Preload failed:", error);
          // Remove from set so it can be retried on next hover
          preloadedPages.delete(targetPage);
        }
      };

      performPreload();
    }, 400);
  }, [preloadedPages]);

  return {
    handleLinkHover,
  };
}
