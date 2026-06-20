"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { enqueueBestEffortJson } from "@/lib/bestEffortQueue";

const DEBOUNCE_MS = 5 * 60 * 1000; // 5 minutes

// INTENTIONAL_SKIP(adr-269): fire-and-forget POST telemetry — not a REST GET
function fireAndForget(page: string, action?: string) {
  enqueueBestEffortJson(
    "/api/usage/track",
    {
      page,
      action,
      timestamp: new Date().toISOString(),
    },
    { delayMs: 3000 },
  );
}

/**
 * Tracks page views on navigation. Debounces to max once per page per 5 minutes.
 * Also exports trackAction() for action button click tracking.
 */
export function useUsageTracking() {
  const pathname = usePathname();
  const lastTracked = useRef<{ page: string; time: number }>({
    page: "",
    time: 0,
  });

  useEffect(() => {
    if (!pathname) return;

    const now = Date.now();
    const last = lastTracked.current;

    // Skip if same page tracked within 5 minutes
    if (last.page === pathname && now - last.time < DEBOUNCE_MS) {
      return;
    }

    lastTracked.current = { page: pathname, time: now };
    fireAndForget(pathname);
  }, [pathname]);
}

/**
 * Track an action button click. Not debounced — every action is tracked.
 */
export function trackAction(action: string) {
  const page = typeof window !== "undefined" ? window.location.pathname : "/";
  fireAndForget(page, action);
}
