import { mcpCall } from "@/lib/mcp/client";

export interface HealEvent {
  source: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  message: string;
  context?: Record<string, unknown>;
}

export interface ClientErrorEvent {
  level: "error" | "warning";
  message: string;
  source: string;
  url: string;
  stack?: string;
  component?: string;
  timestamp?: string;
  fingerprint?: string;
  count?: number;
}

/**
 * Emit a self-heal event to the daemon via MCP.
 * Fire-and-forget: this function MUST never throw.
 * Called from error paths where reliability is critical.
 */
export function emitHealEvent(event: HealEvent): void {
  try {
    mcpCall("set-config", {
      scope: "self-heal-event",
      source: event.source,
      category: event.category,
      severity: event.severity,
      message: event.message,
      context: event.context,
    }).catch(() => {}); // swallow network errors
  } catch {
    // intentionally empty — fire and forget
  }
}

/**
 * Normalize a browser/client-side failure into the self-heal event pipeline.
 * This is the canonical path for React render crashes, console errors,
 * window.onerror, and unhandled rejections.
 */
export function emitClientError(event: ClientErrorEvent): void {
  emitHealEvent({
    source: event.source,
    category: "client-error",
    severity: event.level === "error" ? "high" : "medium",
    message: event.message?.slice(0, 500) || "Unknown client error",
    context: {
      level: event.level,
      url: event.url,
      stack: event.stack?.slice(0, 1000),
      component: event.component?.slice(0, 1000),
      timestamp: event.timestamp ?? new Date().toISOString(),
      fingerprint: event.fingerprint,
      count: event.count ?? 1,
    },
  });
}
