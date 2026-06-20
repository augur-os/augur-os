"use client";

import { type ReactNode } from "react";
import { FileText } from "lucide-react";
import { ConnectionBanner, DetachedSessionsBanner } from "./ChatHeader";

export interface FloatingChatWindowState {
  isEnlarged: boolean;
  isDragOver: boolean;
  isOnline: boolean;
  isCliStale: boolean;
  isRunning: boolean;
  terminalFocused: boolean;
  chatView: string;
  isOperationMode: boolean;
}

export function FloatingChatWindow({
  chatContainerRef,
  state,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  header,
  terminalContainerRef,
  setTerminalFocused,
  children,
  welcomeOverlay,
  onReconnectDetached,
}: {
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  state: FloatingChatWindowState;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => void;
  header: ReactNode;
  terminalContainerRef: React.Ref<HTMLDivElement>;
  setTerminalFocused: (focused: boolean) => void;
  children: ReactNode;
  welcomeOverlay?: ReactNode;
  onReconnectDetached?: (cliId: string) => void;
}) {
  return (
    <div
      ref={chatContainerRef}
      data-testid="floating-chat-window"
      className={`fixed bottom-3 left-3 right-3 w-auto ${
        state.isEnlarged
          ? "h-[calc(100vh-1.5rem)] sm:h-[960px]"
          : "h-[min(600px,calc(100vh-1.5rem))] sm:h-[600px]"
      } max-h-[calc(100vh-1.5rem)] sm:bottom-6 sm:left-auto sm:right-6 sm:w-[700px] sm:max-h-[calc(100vh-3rem)] flex flex-col bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-2xl overflow-hidden z-50 transition-all duration-300`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {state.isDragOver && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--accent-primary)]/10 border-2 border-dashed border-[var(--accent-primary)] rounded-xl">
          <div className="text-center">
            <FileText className="size-8 mx-auto mb-2 text-[var(--accent-primary)]" />
            <p className="text-sm font-medium text-[var(--text-primary)]">
              Drop file to attach
            </p>
          </div>
        </div>
      )}
      <ConnectionBanner
        isOnline={state.isOnline}
        isCliStale={state.isCliStale}
        isRunning={state.isRunning}
      />
      {!state.isRunning && onReconnectDetached && (
        <DetachedSessionsBanner onReconnect={onReconnectDetached} />
      )}
      {header}
      <div
        ref={terminalContainerRef}
        role="application"
        aria-label="Terminal output"
        onClick={() => {
          if (state.isRunning && !state.terminalFocused && !state.isOperationMode) {
            setTerminalFocused(true);
          }
        }}
        onKeyDown={(event) => {
          if (
            (event.key === "Enter" || event.key === " ") &&
            state.isRunning &&
            !state.terminalFocused
          ) {
            event.preventDefault();
            setTerminalFocused(true);
          }
        }}
        onDoubleClick={() => {
          if (state.isRunning && !state.terminalFocused && state.isOperationMode) {
            setTerminalFocused(true);
          }
        }}
        className={`flex-1 min-h-0 overflow-hidden relative ${state.terminalFocused ? "ring-2 ring-[var(--accent-primary)]" : ""}`}
        style={{
          backgroundColor: "var(--bg-primary)",
          borderRadius: "6px",
          margin: "4px 8px",
          padding: "6px",
          display: state.chatView === "terminal" ? "block" : "none",
          cursor: state.isRunning ? "text" : "default",
        }}
      >
        {state.isOperationMode && state.isRunning && (
          <div
            className="absolute top-0 left-0 right-0 h-8 pointer-events-none z-10"
            style={{
              background:
                "linear-gradient(to bottom, var(--bg-primary) 0%, transparent 100%)",
              opacity: 0.7,
            }}
          />
        )}
        {welcomeOverlay}
      </div>

      {children}
    </div>
  );
}
