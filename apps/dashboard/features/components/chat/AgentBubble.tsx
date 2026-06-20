/**
 * AgentBubble — ADR-160
 *
 * A lightweight CLI bubble that represents one active agent task.
 * Starts minimized (pill), expands to mini-terminal on double-click.
 * Auto-evaporates on completion, glows red on attention/error.
 */
"use client";

import { useReducer, useEffect, useRef, useCallback } from "react";
import { Loader2, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import { useModeStore } from "@/lib/stores/modeStore";
import { useTheme } from "@/hooks/useTheme";
import {
  useAgentBubbleStore,
  type AgentBubbleState,
} from "@/lib/stores/agentBubbleStore";
import { useAgentBubblePty } from "@/features/hooks/useAgentBubblePty";

function formatElapsed(startedAt: number): string {
  const elapsed = Math.floor((Date.now() - startedAt) / 1000);
  if (elapsed < 60) return `${elapsed}s`;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${mins}m ${secs}s`;
}

const TERMINAL_BG = "var(--bg-secondary)";

interface AgentBubbleUiState {
  elapsed: string;
  evaporating: boolean;
  focusMode: boolean;
}

type AgentBubbleUiAction =
  | { type: "set-elapsed"; elapsed: string }
  | { type: "set-evaporating"; evaporating: boolean }
  | { type: "set-focus-mode"; focusMode: boolean };

function agentBubbleUiReducer(
  state: AgentBubbleUiState,
  action: AgentBubbleUiAction,
): AgentBubbleUiState {
  switch (action.type) {
    case "set-elapsed":
      return { ...state, elapsed: action.elapsed };
    case "set-evaporating":
      return { ...state, evaporating: action.evaporating };
    case "set-focus-mode":
      return { ...state, focusMode: action.focusMode };
    default:
      return state;
  }
}

export function AgentBubble({ bubble }: { bubble: AgentBubbleState }) {
  const { mode: dashboardMode } = useModeStore();
  const { effectiveMode } = useTheme();
  const isOperationMode = dashboardMode === "operation";
  const { toggleExpanded, removeBubble, updateBubble } = useAgentBubbleStore();

  const [{ elapsed, evaporating, focusMode }, dispatchUi] = useReducer(
    agentBubbleUiReducer,
    { elapsed: "0s", evaporating: false, focusMode: false },
  );
  const containerRef = useRef<HTMLDivElement>(null);

  // Elapsed timer
  useEffect(() => {
    if (bubble.status === "complete" || bubble.status === "error") return;
    const interval = setInterval(() => {
      dispatchUi({
        type: "set-elapsed",
        elapsed: formatElapsed(bubble.startedAt),
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [bubble.startedAt, bubble.status]);

  // Auto-evaporate on completion/error after delay
  useEffect(() => {
    if (bubble.status !== "complete" && bubble.status !== "error") return;
    const delay = bubble.status === "complete" ? 2000 : 5000;
    const timer = setTimeout(() => {
      dispatchUi({ type: "set-evaporating", evaporating: true });
      // Remove after animation completes
      setTimeout(() => removeBubble(bubble.id), 300);
    }, delay);
    return () => clearTimeout(timer);
  }, [bubble.status, bubble.id, removeBubble]);

  // Send raw key to PTY
  // INTENTIONAL_SKIP(adr-269): POST mutation — user-triggered CLI command, not a REST GET
  const handleTerminalData = useCallback(
    (data: string) => {
      fetch("/api/cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "sendRaw",
          cliId: `agent-bubble-${bubble.id}`,
          data,
        }),
      }).catch(() => {});
    },
    [bubble.id],
  );

  // Handle CLI exit
  const handleExit = useCallback(() => {
    // Status already updated by the PTY hook
  }, []);

  const { terminalContainerRef } = useAgentBubblePty({
    bubbleId: bubble.id,
    cliId: `agent-bubble-${bubble.id}`,
    isRunning: bubble.status === "running" || bubble.status === "attention",
    isExpanded: bubble.isExpanded,
    focusMode,
    onTerminalData: handleTerminalData,
    onExit: handleExit,
    mode: effectiveMode,
  });

  // Double-click to expand/enable input
  const handleDoubleClick = () => {
    if (!bubble.isExpanded) {
      toggleExpanded(bubble.id);
    } else if (isOperationMode) {
      dispatchUi({ type: "set-focus-mode", focusMode: true });
    }
  };

  // Click outside to minimize
  useEffect(() => {
    if (!bubble.isExpanded) return;
    const handleClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        toggleExpanded(bubble.id);
        dispatchUi({ type: "set-focus-mode", focusMode: false });
      }
    };
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClick);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [bubble.isExpanded, bubble.id, toggleExpanded]);

  // Escape to minimize
  useEffect(() => {
    if (!bubble.isExpanded) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        toggleExpanded(bubble.id);
        dispatchUi({ type: "set-focus-mode", focusMode: false });
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [bubble.isExpanded, bubble.id, toggleExpanded]);

  // Kill button for stuck agents
  // INTENTIONAL_SKIP(adr-269): POST mutation — user-triggered CLI kill, not a REST GET
  const handleKill = (e: React.MouseEvent) => {
    e.stopPropagation();
    fetch("/api/cli", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "stop",
        cliId: `agent-bubble-${bubble.id}`,
      }),
    }).catch(() => {});
    updateBubble(bubble.id, { status: "error", completedAt: Date.now() });
  };

  // Dismiss button — works in any state
  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (bubble.status === "running" || bubble.status === "attention") {
      // INTENTIONAL_SKIP(adr-269): POST mutation — user-triggered CLI stop, not a REST GET
      // Kill first, then remove
      fetch("/api/cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "stop",
          cliId: `agent-bubble-${bubble.id}`,
        }),
      }).catch(() => {});
    }
    dispatchUi({ type: "set-evaporating", evaporating: true });
    setTimeout(() => removeBubble(bubble.id), 300);
  };

  const statusIcon = () => {
    switch (bubble.status) {
      case "running":
        return <Loader2 className="size-3.5 animate-spin text-blue-400" />;
      case "attention":
        return <AlertCircle className="size-3.5 text-red-400" />;
      case "complete":
        return <CheckCircle2 className="size-3.5 text-emerald-400" />;
      case "error":
        return <XCircle className="size-3.5 text-red-400" />;
    }
  };

  const isAttention =
    bubble.status === "attention" || bubble.status === "error";

  // Expanded: full terminal card. Minimized: compact floating pill.
  if (bubble.isExpanded) {
    return (
      <div
        ref={containerRef}
        onDoubleClick={handleDoubleClick}
        className={`
          w-[780px] rounded-xl border overflow-hidden transition-all duration-300 shadow-xl
          ${evaporating ? "opacity-0 scale-95" : "opacity-100 scale-100"}
          ${isAttention ? "agent-bubble-glow-red" : ""}
          bg-[var(--bg-primary)] border-[var(--border-color)]
        `}
        style={{ height: "340px" }}
      >
        {/* Header bar */}
        <div className="flex items-center justify-between px-3 h-[36px] select-none border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
          <div className="flex items-center gap-2 min-w-0">
            {statusIcon()}
            <span className="text-[11px] font-medium text-[var(--text-primary)] truncate max-w-[320px]">
              {bubble.actionLabel}
            </span>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <span className="text-[11px] text-[var(--text-muted)] tabular-nums">
              {elapsed}
            </span>
            {(bubble.status === "attention" || bubble.status === "running") && (
              <button type="button"
                onClick={handleKill}
                className="text-xs px-1.5 py-0.5 rounded text-red-400 hover:bg-red-400/10 transition-colors"
                title="Kill agent"
                aria-label={`Kill agent: ${bubble.actionLabel}`}
              >
                Kill
              </button>
            )}
            <button type="button"
              onClick={handleDismiss}
              className="text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors p-0.5"
              title="Dismiss"
              aria-label={`Dismiss agent: ${bubble.actionLabel}`}
            >
              <XCircle className="size-3" />
            </button>
          </div>
        </div>
        {/* Terminal — background must match xterm theme exactly */}
        <div
          ref={terminalContainerRef}
          className="overflow-hidden rounded-md"
          style={{
            height: "calc(100% - 36px)",
            backgroundColor: TERMINAL_BG,
            margin: "4px 8px 8px",
            padding: "6px",
          }}
        />
      </div>
    );
  }

  // Minimized: compact floating pill
  return (
    <div
      ref={containerRef}
      onDoubleClick={handleDoubleClick}
      className={`
        inline-flex items-center gap-2 pl-3 pr-1.5 h-9 rounded-full border shadow-lg
        transition-all duration-300 cursor-pointer select-none max-w-[360px]
        ${evaporating ? "opacity-0 scale-90" : "opacity-100 scale-100"}
        ${
          isAttention
            ? "bg-[var(--accent-danger)]/10 border-[var(--accent-danger)]/30 agent-bubble-glow-red"
            : bubble.status === "complete"
              ? "bg-[var(--accent-success)]/10 border-[var(--accent-success)]/30"
              : "bg-[var(--bg-card)] border-[var(--border-color)] hover:border-[var(--text-muted)]"
        }
      `}
    >
      {statusIcon()}
      <span className="text-[11px] font-medium text-[var(--text-primary)] truncate">
        {bubble.actionLabel}
      </span>
      <span className="text-[10px] text-[var(--text-muted)] tabular-nums flex-shrink-0 ml-1">
        {elapsed}
      </span>
      <button type="button"
        onClick={handleDismiss}
        className="text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors p-0.5 flex-shrink-0"
        title="Dismiss"
        aria-label={`Dismiss agent: ${bubble.actionLabel}`}
      >
        <XCircle className="size-3" />
      </button>
    </div>
  );
}
