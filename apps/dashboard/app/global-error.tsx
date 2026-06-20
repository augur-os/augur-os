"use client";

import { useEffect, useReducer } from "react";
import { Button } from "@/components/ui/Button";
import { AlertCircle, RefreshCw } from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";

type ReportStatus = "idle" | "sending" | "sent" | "failed";

function reportStatusReducer(_status: ReportStatus, nextStatus: ReportStatus): ReportStatus {
  return nextStatus;
}

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [reportStatus, setReportStatus] = useReducer(reportStatusReducer, "idle");

  useEffect(() => {
    // Log the error to console
    console.error("Global UI Error caught by boundary:", error);

    // Report to backend bug tracker
    const reportBug = async () => {
      try {
        setReportStatus("sending");
        await mcpCall("sync-bugs", {
          title: `Global UI Error: ${error.message}`,
          description: `Global Error Boundary caught an exception (Root Layout).\n\nDigest: ${error.digest || "N/A"}\n\n${error.stack || "No stack trace available"}`,
          source: "dashboard_ui_global",
          priority: "P0",
          stack_trace: error.stack,
          metadata: {
            digest: error.digest,
            href: window.location.href,
            userAgent: window.navigator.userAgent,
          },
        });
        setReportStatus("sent");
      } catch (err) {
        console.error("Failed to report bug:", err);
        setReportStatus("failed");
      }
    };
    reportBug();
  }, [error]);

  return (
    <html lang="en">
      <body className="font-sans">
        <div
          className="flex flex-col items-center justify-center min-h-screen p-8 text-center gap-y-6"
          style={{ backgroundColor: "#0a0a0a", color: "#e5e7eb" }}
        >
          <div className="p-4 rounded-full motion-safe:animate-pulse bg-[var(--accent-danger)]/10">
            <AlertCircle className="size-16 text-[var(--accent-danger)]" />
          </div>

          <div className="space-y-4 max-w-lg">
            <h1 className="text-4xl font-extrabold tracking-tight">
              Critical System Error
            </h1>
            <p className="text-xl text-[var(--text-secondary)]">
              Augur encountered a critical failure. We&apos;ve dispatched a P0
              bug report to the system.
            </p>
            <div className="text-xs font-mono bg-black/30 p-4 rounded text-left overflow-auto max-h-48 w-full mt-6 border border-white/10 shadow-inner">
              <span className="text-[var(--accent-danger)] font-bold">Error:</span>{" "}
              {error.message}
              {error.digest && (
                <div className="text-[var(--text-muted)] mt-2">Digest: {error.digest}</div>
              )}
              {reportStatus === "sent" && (
                <div className="mt-4 pt-4 border-t border-white/10 text-[var(--accent-success)] font-bold">
                  ✓ Incident Recorded in Bug Tracker
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4 pt-8">
            <Button
              onClick={() => reset()}
              variant="solid"
              size="lg"
              className="gap-2 shadow-lg hover:shadow-xl transition-all"
            >
              <RefreshCw className="size-5" />
              Reload System
            </Button>
          </div>
        </div>
      </body>
    </html>
  );
}
