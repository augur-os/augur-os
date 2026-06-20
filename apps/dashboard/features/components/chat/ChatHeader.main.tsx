"use client";

import { Badge } from "@/components/ui/Badge";
import { ModeToggle } from "@/features/components/action-bar";
import type { SessionConflictInfo } from "@/features/hooks/useCliChat";
import type {
  CliId,
  FloatingChatCliProcess,
  FloatingChatConfig,
} from "./types";
import {
  ChatRouteControl,
  type ChatRouteStartOptions,
} from "./ChatRouteControl";
import { CliSelector, HeaderControls } from "./ChatHeader.controls";
import { SessionConflictBanner } from "./ChatHeader.banners";

interface FloatingChatHeaderState {
  isOperationMode: boolean;
  showCliSelector: boolean;
  isRunning: boolean;
  isEnlarged: boolean;
  isTerminalHandoffOpening: boolean;
}

export function FloatingChatHeader({
  state,
  selectorRef,
  setShowCliSelector,
  statusColor,
  statusLabel,
  selectedCli,
  configs,
  getCliLabel,
  getCliAvatarColor,
  handleCliSelect,
  cliProcess,
  chatView,
  setChatView,
  toggleEnlarged,
  startCli,
  stopCli,
  onMinimize,
  onClose,
  onClear,
  onDetach,
  onOpenTerminal,
  sessionConflict,
  onSwitchSessionOwner,
  onTakeOverSessionOwner,
}: {
  state: FloatingChatHeaderState;
  selectorRef: React.RefObject<HTMLDivElement | null>;
  setShowCliSelector: (show: boolean) => void;
  statusColor: string;
  statusLabel: string;
  selectedCli: CliId;
  configs: FloatingChatConfig[];
  getCliLabel: (cliId: string) => string;
  getCliAvatarColor: (cliId: string) => string;
  handleCliSelect: (cliId: CliId) => void;
  cliProcess: FloatingChatCliProcess | null;
  chatView: string;
  setChatView: (
    view: "chat" | "terminal" | "action-dialog" | "actions-list",
  ) => void;
  toggleEnlarged: () => void;
  startCli: (
    cliId: CliId,
    options?: ChatRouteStartOptions,
  ) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  onMinimize: () => void;
  onClose: () => void;
  onClear?: () => void;
  onDetach?: () => void;
  onOpenTerminal?: () => Promise<void> | void;
  sessionConflict?: SessionConflictInfo | null;
  onSwitchSessionOwner?: () => void;
  onTakeOverSessionOwner?: () => void;
}) {
  return (
    <div className="relative z-20 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]/95 backdrop-blur-sm">
      <div className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex w-full min-w-0 flex-nowrap items-center gap-1.5 rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-secondary)]/92 px-2 py-1.5 shadow-[0_4px_12px_rgba(15,23,42,0.06)] sm:w-auto">
          <ModeToggle className="mr-0 !border-0 !bg-transparent !shadow-none hover:!bg-[var(--bg-primary)]/70" />
          <CliSelector
            isOperationMode={state.isOperationMode}
            selectorRef={selectorRef}
            showCliSelector={state.showCliSelector}
            setShowCliSelector={setShowCliSelector}
            statusColor={statusColor}
            statusLabel={statusLabel}
            isRunning={state.isRunning}
            selectedCli={selectedCli}
            configs={configs}
            getCliLabel={getCliLabel}
            getCliAvatarColor={getCliAvatarColor}
            onCliSelect={handleCliSelect}
          />
          {!state.isOperationMode && cliProcess?.pid && (
            <Badge variant="outline" className="shrink-0 whitespace-nowrap rounded-full text-[10px]">
              PID {cliProcess.pid}
            </Badge>
          )}
          <ChatRouteControl
            cliId={selectedCli}
            isRunning={state.isRunning}
            startCli={startCli}
            stopCli={stopCli}
            onClear={onClear}
          />
        </div>

        <HeaderControls
          state={{
            isRunning: state.isRunning,
            isEnlarged: state.isEnlarged,
            isOperationMode: state.isOperationMode,
            isTerminalHandoffOpening: state.isTerminalHandoffOpening,
          }}
          selectedCli={selectedCli}
          startCli={startCli}
          stopCli={stopCli}
          chatView={chatView}
          setChatView={setChatView}
          toggleEnlarged={toggleEnlarged}
          onMinimize={onMinimize}
          onClose={onClose}
          onClear={onClear}
          onDetach={onDetach}
          onOpenTerminal={onOpenTerminal}
        />
      </div>
      <SessionConflictBanner
        conflict={sessionConflict}
        onSwitchSessionOwner={onSwitchSessionOwner}
        onTakeOverSessionOwner={onTakeOverSessionOwner}
      />
    </div>
  );
}
