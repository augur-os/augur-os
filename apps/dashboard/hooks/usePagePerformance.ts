import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { enqueueBestEffortJson } from "@/lib/bestEffortQueue";

interface LayoutShiftPerformanceEntry extends PerformanceEntry {
  hadRecentInput: boolean;
  value: number;
}

export function usePagePerformance() {
  const pathname = usePathname();

  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined") return;

    // --- 1. Load Time (Existing) ---
    const reportLoadTime = () => {
      // Use Navigation Timing API Level 2 if available
      const perfEntries = performance.getEntriesByType("navigation");
      let duration = 0;
      let isHardLoad = false;

      if (perfEntries.length > 0) {
        const navigationEntry = perfEntries[0] as PerformanceNavigationTiming;
        duration = navigationEntry.loadEventEnd - navigationEntry.startTime;
        isHardLoad = true;
      } else {
        // Fallback to Timing Level 1
        duration =
          performance.timing.loadEventEnd - performance.timing.navigationStart;
        isHardLoad = true;
      }

      if (isHardLoad && duration > 0 && duration < 60000) {
        sendMetric({
          path: window.location.pathname,
          metric: "load",
          duration: duration / 1000,
          timestamp: new Date().toISOString(),
        });
      }
    };

    if (document.readyState === "complete") {
      setTimeout(reportLoadTime, 0);
    } else {
      window.addEventListener("load", reportLoadTime);
    }

    // --- 2. Error Tracking ---
    const reportError = (event: ErrorEvent) => {
      sendMetric({
        path: window.location.pathname,
        metric: "error",
        duration: 1, // Count as 1 error
        timestamp: new Date().toISOString(),
      });
    };
    window.addEventListener("error", reportError);

    // --- 3. Cumulative Layout Shift (CLS) ---
    let clsValue = 0;
    let clsObserver: PerformanceObserver | undefined;
    try {
      if (PerformanceObserver.supportedEntryTypes.includes("layout-shift")) {
        clsObserver = new PerformanceObserver((entryList) => {
          for (const rawEntry of entryList.getEntries()) {
            const entry = rawEntry as LayoutShiftPerformanceEntry;
            if (!entry.hadRecentInput) {
              clsValue += entry.value;
            }
          }
        });
        clsObserver.observe({ type: "layout-shift", buffered: true });
      }
    } catch (e) {
      console.warn("CLS observer failed", e);
    }

    // --- 4. Time on Page ---
    let startTime = Date.now();
    let totalTime = 0;
    let isActive = true;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        if (isActive) {
          totalTime += Date.now() - startTime;
          isActive = false;
        }
      } else {
        startTime = Date.now();
        isActive = true;
      }
    };

    const reportPageStats = () => {
      // Calculate final time
      if (isActive) {
        totalTime += Date.now() - startTime;
      }

      // Report Time on Page
      if (totalTime > 100) {
        // Ignore < 100ms
        sendMetric({
          path: pathname, // Use the captured pathname from render time
          metric: "time_on_page",
          duration: totalTime / 1000,
          timestamp: new Date().toISOString(),
        });
      }

      // Report CLS
      if (clsValue > 0) {
        sendMetric({
          path: pathname,
          metric: "cls",
          duration: clsValue,
          timestamp: new Date().toISOString(),
        });
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    // Report on unmount / navigation
    return () => {
      window.removeEventListener("load", reportLoadTime);
      window.removeEventListener("error", reportError);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (clsObserver) clsObserver.disconnect();
      reportPageStats();
    };
  }, [pathname]);
}

async function sendMetric(data: {
  path: string;
  metric: string;
  duration: number;
  timestamp: string;
}) {
  try {
    enqueueBestEffortJson("/api/telemetry/performance", data, { delayMs: 2500 });
  } catch (error) {
    // Telemetry is best-effort and should not surface as a user-visible runtime error.
    if (process.env.NODE_ENV === "development") {
      console.debug("Failed to send performance metric", error);
    }
  }
}
