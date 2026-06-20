import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { enqueueBestEffortJson } from "@/lib/bestEffortQueue";

export function useInteractionTracker() {
  const pathname = usePathname();

  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined") return;

    let interactionCount = 0;

    const handleClick = (e: MouseEvent) => {
      // Only count clicks on interactive elements or substantial elements
      const target = e.target as HTMLElement;
      const isInteractive = target.closest(
        'button, a, input, select, textarea, [role="button"]',
      );

      if (isInteractive) {
        interactionCount++;
      }
    };

    window.addEventListener("click", handleClick);

    const reportInteractions = () => {
      if (interactionCount > 0) {
        sendMetric({
          path: pathname,
          metric: "interaction",
          duration: interactionCount, // Using duration field for count
          timestamp: new Date().toISOString(),
        });
      }
    };

    return () => {
      window.removeEventListener("click", handleClick);
      reportInteractions();
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
    console.error("Failed to send interaction metric", error);
  }
}
