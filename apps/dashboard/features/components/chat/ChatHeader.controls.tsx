"use client";

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  ChevronDown,
  Square,
  Play,
  SquareTerminal,
  Minus,
  Maximize2,
  Minimize2,
  X,
  MessageSquare,
  Unplug,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { isMacPlatform } from "@/components/chat/utils";
import type { CliId, FloatingChatConfig } from "./types";
import { type ChatRouteStartOptions } from "./ChatRouteControl";

const CLI_SELECTOR_MENU_WIDTH = 224;
const CLI_SELECTOR_VIEWPORT_MARGIN = 8;

export function CliSelector({
  isOperationMode,
  selectorRef,
  showCliSelector,
  setShowCliSelector,
  statusColor,
  statusLabel,
  isRunning,
  selectedCli,
  configs,
  getCliLabel,
  getCliAvatarColor,
  onCliSelect,
}: {
  isOperationMode: boolean;
  selectorRef: React.RefObject<HTMLDivElement | null>;
  showCliSelector: boolean;
  setShowCliSelector: (show: boolean) => void;
  statusColor: string;
  statusLabel: string;
  isRunning: boolean;
  selectedCli: string;
  configs: FloatingChatConfig[];
  getCliLabel: (cliId: string) => string;
  getCliAvatarColor: (cliId: string) => string;
  onCliSelect: (cliId: CliId) => void;
}) {
  const metaLabel = isRunning ? statusLabel : "Ready";
  const [menuPosition, setMenuPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);

  const updateMenuPosition = useCallback(() => {
    if (typeof window === "undefined") return;

    const anchor = selectorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const maxLeft = Math.max(
      CLI_SELECTOR_VIEWPORT_MARGIN,
      window.innerWidth - CLI_SELECTOR_MENU_WIDTH - CLI_SELECTOR_VIEWPORT_MARGIN,
    );

    setMenuPosition({
      top: rect.bottom + 4,
      left: Math.min(
        Math.max(CLI_SELECTOR_VIEWPORT_MARGIN, rect.left),
        maxLeft,
      ),
    });
  }, [selectorRef]);

  useEffect(() => {
    if (!showCliSelector) return;

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
      setMenuPosition(null);
    };
  }, [showCliSelector, updateMenuPosition]);

  if (isOperationMode) {
    return (
      <div className="relative" ref={selectorRef}>
        <div className="flex items-center gap-2 px-2 py-1">
          <MessageSquare className="size-3.5 text-[var(--text-muted)]" />
          <div className="flex flex-col leading-none">
            <span className="text-sm font-semibold text-[var(--text-primary)]">
              Assistant
            </span>
            <span className="mt-1 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
              {metaLabel}
            </span>
          </div>
        </div>
      </div>
    );
  }

  const shortcutPrefix = isMacPlatform() ? "⌘" : "Ctrl";
  const selectorMenu =
    showCliSelector && menuPosition && typeof document !== "undefined" ? (
      <div
        data-testid="cli-selector-menu"
        className="fixed w-56 bg-[var(--bg-popover)] backdrop-blur-xl border border-[var(--border-color)]/60 rounded-xl shadow-2xl z-[70]"
        style={{ top: menuPosition.top, left: menuPosition.left }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {configs.map((config, idx) => {
          const isActive = config.cli_id === selectedCli;
          return (
            <button
              type="button"
              key={config.cli_id}
              onClick={() => onCliSelect(config.cli_id as CliId)}
              disabled={!config.available}
              aria-label={`Select CLI: ${config.label}`}
              className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors first:rounded-t-xl last:rounded-b-xl ${
                isActive
                  ? "bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
                  : "text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
              } ${!config.available ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <span
                className="size-2 rounded-full"
                style={{
                  backgroundColor: config.available
                    ? getCliAvatarColor(config.cli_id)
                    : "hsl(var(--muted-foreground))",
                }}
              />
              <span>{config.label}</span>
              {idx < 7 && (
                <kbd className="ml-auto text-[9px] px-1 py-0.5 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-muted)]">
                  {shortcutPrefix}
                  {idx + 1}
                </kbd>
              )}
              {isActive && (
                <Badge variant="outline" className="text-[9px]">
                  active
                </Badge>
              )}
            </button>
          );
        })}
      </div>
    ) : null;

  return (
    <div className="relative min-w-0" ref={selectorRef}>
      <button
        type="button"
        onClick={() => setShowCliSelector(!showCliSelector)}
        aria-expanded={showCliSelector}
        aria-label="Select CLI instance"
        title={getCliLabel(selectedCli)}
        className="flex min-w-0 max-w-full items-center gap-1.5 rounded-full px-1.5 py-1.5 text-left transition-colors hover:bg-[var(--bg-primary)]/70"
      >
        <span
          className={`size-2 shrink-0 rounded-full ${statusColor} ${isRunning ? "motion-safe:animate-pulse" : ""}`}
          aria-live="polite"
          aria-label={`CLI status: ${statusLabel}`}
        />
        <div className="flex min-w-0 flex-col leading-none">
          <span className="truncate text-sm font-semibold text-[var(--text-primary)]">
            {getCliLabel(selectedCli)}
          </span>
          <span className="mt-1 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
            {metaLabel}
          </span>
        </div>
        <ChevronDown className="size-3 shrink-0 text-[var(--text-muted)]" />
      </button>

      {selectorMenu ? createPortal(selectorMenu, document.body) : null}
    </div>
  );
}

export function TerminalHandoffButton({
  isRunning,
  selectedCli,
  isOpening,
  onOpenTerminal,
}: {
  isRunning: boolean;
  selectedCli: CliId;
  isOpening: boolean;
  onOpenTerminal?: () => Promise<void> | void;
}) {
  const supported =
    selectedCli === "claude" ||
    selectedCli === "codex" ||
    selectedCli === "gemini";
  const disabled = !isRunning || !supported || isOpening || !onOpenTerminal;
  const title = !supported
    ? "Native terminal handoff is not configured for this client"
    : !isRunning
      ? "Start the CLI before opening a native terminal"
      : isOpening
        ? "Opening native terminal..."
        : "Open in native terminal";

  const openNativeTerminal = useCallback(async () => {
    if (disabled || !onOpenTerminal) return;
    await onOpenTerminal();
  }, [disabled, onOpenTerminal]);

  return (
    <button
      type="button"
      onClick={openNativeTerminal}
      disabled={disabled}
      className="flex size-9 items-center justify-center rounded-full text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-primary)]/70 hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
      title={title}
      aria-label="Open in native terminal"
    >
      <SquareTerminal
        className={`size-3.5 ${isOpening ? "motion-safe:animate-pulse" : ""}`}
      />
    </button>
  );
}

function StartStopButton({
  isRunning,
  selectedCli,
  startCli,
  stopCli,
  onClear,
}: {
  isRunning: boolean;
  selectedCli: CliId;
  startCli: (
    cliId: CliId,
    options?: ChatRouteStartOptions,
  ) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  onClear?: () => void;
}) {
  if (isRunning) {
    return (
      <button type="button"
        onClick={() => {
          stopCli(selectedCli);
          onClear?.();
        }}
        className="flex size-9 items-center justify-center rounded-full text-[var(--text-secondary)] transition-colors hover:bg-red-500/10 hover:text-red-400"
        title="Stop CLI"
        aria-label="Stop CLI process"
      >
        <Square className="size-3.5" />
      </button>
    );
  }

  return (
    <button type="button"
      onClick={() => {
        onClear?.();
        startCli(selectedCli);
      }}
      className="flex size-9 items-center justify-center rounded-full text-[var(--text-secondary)] transition-colors hover:bg-emerald-500/10 hover:text-emerald-400"
      title="Start CLI"
      aria-label="Start CLI process"
    >
      <Play className="size-3.5" />
    </button>
  );
}

/**
 * ADR-535: Chat bubble view (Tier 1) removed — parser heuristics are fragile
 * against evolving CLI output formats. Terminal view (Tier 3) works reliably.
 * Toggle hidden; chat input bar still sends to PTY in terminal mode.
 */
function ViewToggleButton({
  chatView: _chatView,
  setChatView: _setChatView,
  isOperationMode: _isOperationMode,
}: {
  chatView: string;
  setChatView: (
    view: "chat" | "terminal" | "action-dialog" | "actions-list",
  ) => void;
  isOperationMode: boolean;
}) {
  // ADR-535: Chat bubble view disabled — always use terminal
  return null;
}

interface HeaderControlState {
  isRunning: boolean;
  isEnlarged: boolean;
  isOperationMode: boolean;
  isTerminalHandoffOpening: boolean;
}

export function HeaderControls({
  state,
  selectedCli,
  startCli,
  stopCli,
  chatView,
  setChatView,
  toggleEnlarged,
  onMinimize,
  onClose,
  onClear,
  onDetach,
  onOpenTerminal,
}: {
  state: HeaderControlState;
  selectedCli: CliId;
  startCli: (
    cliId: CliId,
    options?: ChatRouteStartOptions,
  ) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  chatView: string;
  setChatView: (
    view: "chat" | "terminal" | "action-dialog" | "actions-list",
  ) => void;
  toggleEnlarged: () => void;
  onMinimize: () => void;
  onClose: () => void;
  onClear?: () => void;
  onDetach?: () => void;
  onOpenTerminal?: () => Promise<void> | void;
}) {
  const [confirmingClose, setConfirmingClose] = useState(false);

  // Auto-dismiss confirmation after 4 seconds
  useEffect(() => {
    if (!confirmingClose) return;
    const timer = setTimeout(() => setConfirmingClose(false), 4000);
    return () => clearTimeout(timer);
  }, [confirmingClose]);

  // ADR-535 Phase 3: Close button ends session when PTY is running
  const handleCloseClick = useCallback(() => {
    if (state.isRunning) {
      // Show confirmation before ending an active session
      setConfirmingClose(true);
    } else {
      // No active session — close immediately
      onClose();
    }
  }, [state.isRunning, onClose]);

  const handleConfirmEnd = useCallback(() => {
    setConfirmingClose(false);
    // Stop PTY, clear conversation, then close
    stopCli(selectedCli);
    onClear?.();
    onClose();
  }, [stopCli, selectedCli, onClear, onClose]);

  // ADR-535 0F: Detach from close confirmation
  const handleDetachFromConfirm = useCallback(() => {
    setConfirmingClose(false);
    onDetach?.();
  }, [onDetach]);

  const handleTerminalHandoff = useCallback(() => {
    void onOpenTerminal?.();
  }, [onOpenTerminal]);

  const sizeTitle = state.isEnlarged ? "Standard size" : "Enlarge";
  const sizeAria = state.isEnlarged
    ? "Shrink to standard size"
    : "Enlarge chat window";
  const iconButtonClass =
    "flex size-9 items-center justify-center rounded-full text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-primary)]/70 hover:text-[var(--text-primary)]";

  return (
    <div className="flex min-w-0 items-center justify-end gap-2">
      {/* ADR-535: Close confirmation replaces the control pill instead of
          sitting beside it. The header is a fixed-width (sm:w-[700px]),
          overflow-hidden panel; adding the strip inline pushed the icon pill
          (End/Cancel/X) past the clipped right edge and made it unreachable. */}
      {confirmingClose ? (
        <div className="flex items-center gap-1.5 rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-secondary)]/92 px-2.5 py-1.5 shadow-[0_4px_12px_rgba(15,23,42,0.06)]">
          <span className="text-[10px] text-[var(--text-muted)] whitespace-nowrap">
            End session?
          </span>
          {onDetach && (
            <button type="button"
              onClick={handleDetachFromConfirm}
              className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors font-medium"
              aria-label="Detach session (keep running in background)"
              title="Close window but keep session running. Reconnect later."
            >
              Detach
            </button>
          )}
          <button type="button"
            onClick={handleConfirmEnd}
            className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 hover:bg-red-500/25 transition-colors font-medium"
            aria-label="Confirm end session"
          >
            End
          </button>
          <button type="button"
            onClick={() => setConfirmingClose(false)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Cancel close"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-secondary)]/92 px-2 py-1.5 shadow-[0_4px_12px_rgba(15,23,42,0.06)]">
        <StartStopButton
          isRunning={state.isRunning}
          selectedCli={selectedCli}
          startCli={startCli}
          stopCli={stopCli}
          onClear={onClear}
        />
        <TerminalHandoffButton
          isRunning={state.isRunning}
          selectedCli={selectedCli}
          isOpening={state.isTerminalHandoffOpening}
          onOpenTerminal={onOpenTerminal ? handleTerminalHandoff : undefined}
        />
        <ViewToggleButton
          chatView={chatView}
          setChatView={setChatView}
          isOperationMode={state.isOperationMode}
        />

        {/* ADR-535 0F: Detach button — only shown when CLI is running */}
        {state.isRunning && onDetach && (
          <button type="button"
            onClick={onDetach}
            className={`${iconButtonClass} hover:bg-blue-500/12 hover:text-blue-400`}
            title="Detach session (keep running in background)"
            aria-label="Detach session"
          >
            <Unplug className="size-3.5" />
          </button>
        )}

        <button type="button"
          onClick={toggleEnlarged}
          className={iconButtonClass}
          title={sizeTitle}
          aria-label={sizeAria}
        >
          {state.isEnlarged ? (
            <Minimize2 className="size-3.5" />
          ) : (
            <Maximize2 className="size-3.5" />
          )}
        </button>

        <button type="button"
          onClick={onMinimize}
          className={iconButtonClass}
          title="Minimize"
          aria-label="Minimize chat window"
        >
          <Minus className="size-3.5" />
        </button>

        <button type="button"
          onClick={handleCloseClick}
          className={`${iconButtonClass} hover:bg-red-500/12 hover:text-red-400`}
          title={state.isRunning ? "End session" : "Close"}
          aria-label={state.isRunning ? "End chat session" : "Close chat window"}
        >
          <X className="size-3.5" />
        </button>
        </div>
      )}
    </div>
  );
}
