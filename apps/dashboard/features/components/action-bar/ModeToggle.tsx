"use client";

import { useEffect } from "react";
import { toast } from "sonner";
import { useModeStore } from "@/lib/stores/modeStore";
import { useMcpHealth } from "@/hooks/useMcpHealth";

interface ModeToggleProps {
  /** Additional CSS classes */
  className?: string;
  /** Whether to show the right border divider (used in full action bar) */
  showDivider?: boolean;
}

/**
 * Mode toggle button with animated dot indicator and ⌘⇧D keyboard shortcut.
 *
 * Extracted from PageActionButtons (ADR-036) for reuse in both
 * the full action bar (AI Builder mode) and the FloatingChat header (User mode).
 */
export function ModeToggle({
  className = "",
  showDivider = false,
}: ModeToggleProps) {
  const { mode, toggleMode } = useModeStore();
  const { data: mcpData } = useMcpHealth({
    enablePolling: true,
    showToasts: false,
  });

  const isDev = mode === "development";
  // Green when augur MCP server processes are running, red otherwise
  const mcpRunning = (mcpData?.runtime?.processMatches ?? []).some(
    (p: { command: string }) =>
      p.command.includes("augur_mcp") ||
      p.command.includes("augur_framework") ||
      p.command.includes("augur_core"),
  );

  // Keyboard shortcut ⌘⇧D / Ctrl+Shift+D
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "d") {
        e.preventDefault();
        toggleMode();
        toast.success(mode === "operation" ? "AI Builder mode" : "User mode");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mode, toggleMode]);

  return (
    <button type="button"
      className={`flex items-center gap-2 rounded-full border border-[var(--border-color)]/70 bg-[var(--bg-primary)]/60 px-2.5 py-1.5 cursor-pointer transition-all duration-200 hover:bg-[var(--bg-primary)] ${
        showDivider ? "pr-3" : ""
      } ${className}`}
      onClick={() => {
        toggleMode();
        toast.success(isDev ? "User mode" : "AI Builder mode");
      }}
      title={
        isDev
          ? "AI Builder mode - Click to switch to User mode (⌘⇧D)"
          : "User mode - Click to switch to AI Builder mode (⌘⇧D)"
      }
      aria-label={isDev ? "Switch to User mode" : "Switch to AI Builder mode"}
    >
      <div className="relative flex size-2.5">
        <span
          className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
            isDev ? "bg-orange-400" : mcpRunning ? "bg-green-400" : "bg-red-400"
          }`}
        />
        <span
          className={`relative inline-flex rounded-full size-2.5 ${
            isDev ? "bg-orange-500" : mcpRunning ? "bg-green-500" : "bg-red-500"
          }`}
        />
      </div>
      <span
        className={`text-[10px] font-mono font-medium tracking-wider ${
          isDev ? "text-orange-400" : "text-green-400"
        }`}
      >
        {isDev ? "BUILDER" : "USER"}
      </span>
    </button>
  );
}
