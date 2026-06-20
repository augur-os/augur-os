"use client";

import { useEffect, useReducer } from "react";
import { Button } from "@/components/ui/Button";
import { AlertCircle, RefreshCw } from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";

type ReportStatus = "idle" | "sending" | "sent" | "failed";

function reportStatusReducer(_status: ReportStatus, nextStatus: ReportStatus): ReportStatus {
  return nextStatus;
}

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [reportStatus, setReportStatus] = useReducer(reportStatusReducer, "idle");

  useEffect(() => {
    // Log the error to console
    console.error("UI Error caught by boundary:", error);

    // Report to backend bug tracker
    const reportBug = async () => {
      try {
        setReportStatus("sending");
        await mcpCall("sync-bugs", {
          title: `UI Error: ${error.message}`,
          description: `React Error Boundary caught an exception.\n\nDigest: ${error.digest || "N/A"}\n\n${error.stack || "No stack trace available"}`,
          source: "dashboard_ui",
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
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center gap-y-6 bg-background rounded-lg border border-border/50 m-4">
      <div className="p-4 bg-destructive/10 rounded-full">
        <AlertCircle className="size-12 text-destructive" />
      </div>

      <div className="space-y-2 max-w-md">
        <h2 className="text-2xl font-bold tracking-tight">
          Something went wrong!
        </h2>
        <p className="text-muted-foreground">
          We&apos;ve automatically reported this issue to the engineering team.
        </p>
        <div className="text-xs font-mono bg-muted p-2 rounded text-left overflow-auto max-h-32 w-full mt-4 border border-border">
          {error.message}
          {error.digest && (
            <div className="text-muted-foreground mt-1">
              Digest: {error.digest}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-4">
        <Button onClick={() => reset()} variant="solid" className="gap-2">
          <RefreshCw className="size-4" />
          Try Again
        </Button>
        <Button onClick={() => (window.location.href = "/")} variant="outline">
          Go Home
        </Button>
      </div>

      {reportStatus === "sent" && (
        <p className="text-xs text-[var(--accent-success)] font-medium animate-in fade-in">
          Error report filed successfully
        </p>
      )}
    </div>
  );
}
