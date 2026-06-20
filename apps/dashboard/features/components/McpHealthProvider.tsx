"use client";

import { useMcpHealth } from "@/hooks/useMcpHealth";

/**
 * Global MCP health monitor that runs in the background.
 * Shows toast notifications when MCP configuration issues are detected.
 *
 * Add this component to your root layout to enable global monitoring.
 */
export default function McpHealthProvider() {
  // Keep MCP failures visible; hiding this signal makes worktree/runtime drift
  // look like an empty dashboard instead of an actionable infrastructure issue.
  useMcpHealth({
    enablePolling: true,
    showToasts: true,
    pollInterval: 120_000, // 2 minutes — was 30s, reduced to avoid MCP flooding
  });

  // This component doesn't render anything visible
  return null;
}
