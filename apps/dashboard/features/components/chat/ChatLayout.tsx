"use client";

import { FloatingChatMinimizedPill, FloatingChatHeader } from "./ChatHeader";
import type { ChatRouteStartOptions } from "./ChatRouteControl";
import { ContextButton } from "./ContextButton";
import { ActionsButton } from "./ActionsButton";
import { SearchButton } from "./SearchButton";
import { AssistButton } from "./AssistButton";
import {
  TerminalInputSection,
  TerminalBottomSection,
  TerminalFocusStrip,
  WelcomeOverlay,
} from "./ChatInput";
import { ChatViewPanels } from "./ChatViewPanels";
import { PreparedActionDraftCard } from "./PreparedActionDraftCard";
import { FloatingChatWindow } from "./ChatWindow";
import { AgentBubbleStack } from "./AgentBubbleStack";
import type { SessionConflictInfo } from "@/features/hooks/useCliChat";
import type { PreparedActionDraft } from "@/lib/actions/preparedActionDraft";
import type { OneshotResult } from "@/lib/stores/chatStore";
import type {
  CliId,
  McpTool,
  SlashCommand,
  FloatingChatCliProcess,
  FloatingChatConfig,
  FloatingChatMessage,
  FloatingChatAttachedFile,
  SuggestedAction,
} from "./types";

type PanelId = "context" | "actions" | "search" | null;

export function renderFloatingChatLayout({
  isOpen,
  isMinimized,
  setIsMinimized,
  statusColor,
  isRunning,
  statusLabel,
  cliLabel,
  isOperationMode,
  draft,
  oneshotResult,
  preparedActionDraft,
  preparedActionClientLabel,
  preparedActionRemarks,
  preparedActionError,
  preparedActionSending,
  preparedActionCanSend,
  onPreparedActionRemarksChange,
  onPreparedActionSend,
  onPreparedActionCancel,
  chatContainerRef,
  // ADR-271: Unified panel state for mutual exclusion
  activePanel,
  setActivePanel,
  // ADR-271: Context button
  onAttachFile,
  // ADR-271: Actions button data (fetched by parent)
  mcpTools,
  mcpToolsLoading,
  insertToolName,
  slashCommands,
  handleRunCommand,
  handleMagicClick,
  magicLoading,
  pendingInsightCount,
  // ADR-271: Panel refs
  contextPortalRef,
  contextPopoverRef,
  actionsPortalRef,
  actionsPopoverRef,
  searchPortalRef,
  searchPopoverRef,
  pathname,
  setInput,
  textareaRef,
  handleSubmit,
  setShowHelpModal,
  fileInputRef,
  handleFileSelect,
  handlePaste,
  input,
  handleTextareaChange,
  handleTextareaKeyDown,
  selectorRef,
  showCliSelector,
  setShowCliSelector,
  selectedCli,
  configs,
  getCliLabel,
  getCliAvatarColor,
  handleCliSelect,
  cliProcess,
  chatView,
  setChatView,
  isEnlarged,
  toggleEnlarged,
  startCli,
  stopCli,
  closeChat,
  terminalFocused,
  latestSystemMsg,
  hasChatContent,
  attachedFiles,
  removeAttachedFile,
  setTerminalFocused,
  embeddedAction,
  sendMessage,
  sendRawKey,
  uploadFile,
  setTerminalFallbackActive,
  switchCli,
  sendToIde,
  setEmbeddedAction,
  showHelpModal,
  setShowHelpModalState,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  isDragOver,
  isOnline,
  isCliStale,
  terminalContainerRef,
  suggestedActions,
  onSuggestedAction,
  onClear,
  onDetach,
  onOpenTerminal,
  isTerminalHandoffOpening,
  sessionConflict,
  onSwitchSessionOwner,
  onTakeOverSessionOwner,
  onRunLiveResult,
}: {
  isOpen: boolean;
  isMinimized: boolean;
  setIsMinimized: (value: boolean) => void;
  statusColor: string;
  isRunning: boolean;
  statusLabel: string;
  cliLabel: string;
  isOperationMode: boolean;
  draft?: boolean;
  oneshotResult?: OneshotResult | null;
  preparedActionDraft?: PreparedActionDraft | null;
  preparedActionClientLabel?: string;
  preparedActionRemarks?: string;
  preparedActionError?: string | null;
  preparedActionSending?: boolean;
  preparedActionCanSend?: boolean;
  onPreparedActionRemarksChange?: (value: string) => void;
  onPreparedActionSend?: () => void;
  onPreparedActionCancel?: () => void;
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  activePanel: PanelId;
  setActivePanel: (panel: PanelId) => void;
  onAttachFile: (filePath: string) => void;
  mcpTools: McpTool[];
  mcpToolsLoading: boolean;
  insertToolName: (toolName: string) => void;
  slashCommands: SlashCommand[];
  handleRunCommand: (command: SlashCommand) => void;
  handleMagicClick: () => void;
  magicLoading: boolean;
  pendingInsightCount: number;
  contextPortalRef: React.RefObject<HTMLDivElement | null>;
  contextPopoverRef: React.RefObject<HTMLDivElement | null>;
  actionsPortalRef: React.RefObject<HTMLDivElement | null>;
  actionsPopoverRef: React.RefObject<HTMLDivElement | null>;
  searchPortalRef: React.RefObject<HTMLDivElement | null>;
  searchPopoverRef: React.RefObject<HTMLDivElement | null>;
  pathname: string;
  setInput: (value: React.SetStateAction<string>) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  handleSubmit: (e: React.FormEvent) => void;
  setShowHelpModal: (show: boolean) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handlePaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void;
  input: string;
  handleTextareaChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleTextareaKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  selectorRef: React.RefObject<HTMLDivElement | null>;
  showCliSelector: boolean;
  setShowCliSelector: (show: boolean) => void;
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
  isEnlarged: boolean;
  toggleEnlarged: () => void;
  startCli: (
    cliId: CliId,
    options?: ChatRouteStartOptions,
  ) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  closeChat: () => void;
  terminalFocused: boolean;
  latestSystemMsg?: FloatingChatMessage;
  hasChatContent: boolean;
  attachedFiles: FloatingChatAttachedFile[];
  removeAttachedFile: (path: string) => void;
  setTerminalFocused: (focused: boolean) => void;
  embeddedAction: unknown;
  sendMessage: (prompt: string) => void;
  sendRawKey: (input: string) => void;
  uploadFile: (file: File) => void;
  setTerminalFallbackActive: (active: boolean) => void;
  switchCli: (cliId: CliId) => Promise<void> | void;
  sendToIde: (prompt: string) => void;
  setEmbeddedAction: (action: any) => void;
  showHelpModal: boolean;
  setShowHelpModalState: (show: boolean) => void;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => void;
  isDragOver: boolean;
  isOnline: boolean;
  isCliStale: boolean;
  terminalContainerRef: React.Ref<HTMLDivElement>;
  suggestedActions: SuggestedAction[];
  onSuggestedAction: (action: SuggestedAction) => void;
  onClear?: () => void;
  onDetach?: () => void;
  onOpenTerminal?: () => Promise<void> | void;
  isTerminalHandoffOpening?: boolean;
  sessionConflict?: SessionConflictInfo | null;
  onSwitchSessionOwner?: () => void;
  onTakeOverSessionOwner?: () => Promise<void> | void;
  onRunLiveResult?: (result: OneshotResult) => Promise<void> | void;
}) {
  // ADR-271: Toggle helpers for mutual exclusion
  const togglePanel = (panel: "context" | "actions" | "search") => {
    setActivePanel(activePanel === panel ? null : panel);
  };

  // ADR-271: Unified toolbar buttons
  const toolbarButtons = (
    <>
      <ContextButton
        isOperationMode={isOperationMode}
        pathname={pathname}
        isOpen={activePanel === "context"}
        onToggle={() => togglePanel("context")}
        onAttachFile={onAttachFile}
        chatContainerRef={chatContainerRef}
        portalRef={contextPortalRef}
        popoverRef={contextPopoverRef}
      />
      <ActionsButton
        isOperationMode={isOperationMode}
        pathname={pathname}
        isOpen={activePanel === "actions"}
        onToggle={() => togglePanel("actions")}
        mcpTools={mcpTools}
        mcpToolsLoading={mcpToolsLoading}
        onInsertTool={insertToolName}
        commands={slashCommands}
        onRunCommand={handleRunCommand}
        onMagicClick={handleMagicClick}
        magicLoading={magicLoading}
        pendingInsightCount={pendingInsightCount}
        chatContainerRef={chatContainerRef}
        portalRef={actionsPortalRef}
        popoverRef={actionsPopoverRef}
      />
      <SearchButton
        isOperationMode={isOperationMode}
        pathname={pathname}
        isOpen={activePanel === "search"}
        onToggle={() => togglePanel("search")}
        onAttachFile={onAttachFile}
        chatContainerRef={chatContainerRef}
        portalRef={searchPortalRef}
        popoverRef={searchPopoverRef}
      />
      <AssistButton onClick={() => setShowHelpModal(true)} />
    </>
  );

  const inputSection = (
    <TerminalInputSection
      handleSubmit={handleSubmit}
      toolbarButtons={toolbarButtons}
      pathname={pathname}
      fileInputRef={fileInputRef}
      handleFileSelect={handleFileSelect}
      handlePaste={handlePaste}
      textareaRef={textareaRef}
      input={input}
      handleTextareaChange={handleTextareaChange}
      handleTextareaKeyDown={handleTextareaKeyDown}
      isRunning={isRunning}
      isOperationMode={isOperationMode}
      draft={draft}
      attachedFiles={attachedFiles}
      removeAttachedFile={removeAttachedFile}
      isDragOver={isDragOver}
    />
  );

  // A pending prepared action fills the message area as a single focused panel
  // (its card carries its own remarks input + Send/Cancel). The composer toolbar
  // and welcome overlay are suppressed while it's staged so there's one clear
  // thing to review — and the card fills the window rather than floating in it.
  const preparedActionPanel = preparedActionDraft ? (
    // Opaque backdrop: --bg-card is semi-transparent (#ffffffa6), so without an
    // opaque layer the running terminal bleeds through the card. The card sizes
    // to its content and centers here, so a short action reads as a focused
    // modal rather than a half-empty full-bleed panel.
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--bg-primary)] p-4">
      <PreparedActionDraftCard
        draft={preparedActionDraft}
        selectedClientLabel={preparedActionClientLabel ?? ""}
        userRemarks={preparedActionRemarks ?? ""}
        onUserRemarksChange={onPreparedActionRemarksChange ?? (() => {})}
        onSend={onPreparedActionSend ?? (() => {})}
        onCancel={onPreparedActionCancel ?? (() => {})}
        canSend={preparedActionCanSend ?? false}
        isSending={preparedActionSending ?? false}
        error={preparedActionError ?? null}
      />
    </div>
  ) : null;

  if (isOpen && isMinimized) {
    return (
      <>
        <AgentBubbleStack />
        <FloatingChatMinimizedPill
          onRestore={() => setIsMinimized(false)}
          statusColor={statusColor}
          isRunning={isRunning}
          statusLabel={statusLabel}
          cliLabel={cliLabel}
        />
      </>
    );
  }

  if (!isOpen) return <AgentBubbleStack />;

  const header = (
    <FloatingChatHeader
      state={{
        isOperationMode,
        showCliSelector,
        isRunning,
        isEnlarged,
        isTerminalHandoffOpening: isTerminalHandoffOpening === true,
      }}
      selectorRef={selectorRef}
      setShowCliSelector={setShowCliSelector}
      statusColor={statusColor}
      statusLabel={statusLabel}
      selectedCli={selectedCli}
      configs={configs}
      getCliLabel={getCliLabel}
      getCliAvatarColor={getCliAvatarColor}
      handleCliSelect={handleCliSelect}
      cliProcess={cliProcess}
      chatView={chatView}
      setChatView={setChatView}
      toggleEnlarged={toggleEnlarged}
      startCli={startCli}
      stopCli={stopCli}
      onMinimize={() => setIsMinimized(true)}
      onClose={closeChat}
      onClear={onClear}
      onDetach={onDetach}
      onOpenTerminal={onOpenTerminal}
      sessionConflict={sessionConflict}
      onSwitchSessionOwner={onSwitchSessionOwner}
      onTakeOverSessionOwner={onTakeOverSessionOwner}
    />
  );

  const terminalBottom = (
    <TerminalBottomSection
      chatView={chatView}
      terminalFocused={terminalFocused}
      latestSystemMsg={latestSystemMsg}
      inputSection={inputSection}
      isOperationMode={isOperationMode}
    />
  );

  const terminalFocusStrip = (
    <TerminalFocusStrip
      show={chatView === "terminal" && terminalFocused}
      onExit={() => setTerminalFocused(false)}
    />
  );

  const panels = (
    <ChatViewPanels
      chatView={chatView}
      embeddedAction={embeddedAction}
      selectedCli={selectedCli}
      configs={configs}
      isRunning={isRunning}
      cliProcess={cliProcess}
      sendMessage={sendMessage}
      sendRawKey={sendRawKey}
      uploadFile={uploadFile}
      setTerminalFallbackActive={setTerminalFallbackActive}
      setChatView={setChatView}
      startCli={startCli}
      switchCli={switchCli}
      stopCli={stopCli}
      sendToIde={sendToIde}
      setEmbeddedAction={setEmbeddedAction}
      showHelpModal={showHelpModal}
      setShowHelpModal={setShowHelpModalState}
      isOperationMode={isOperationMode}
    />
  );

  // Empty state for the terminal area when the assistant isn't running.
  // Operation mode shows it whenever stopped (chat-bubble surface). Builder
  // mode shows it only when the terminal has no real content, so we never
  // paint over output left from a previous/exited run. A pending prepared
  // action owns the whole window (its card is the single focus) — showing the
  // generic "Ask me anything" overlay alongside it puts two competing CTAs on
  // screen, so suppress it while a draft is staged.
  const welcomeOverlay =
    !isRunning &&
    !preparedActionDraft &&
    (isOperationMode || !hasChatContent) && (
      <WelcomeOverlay
        suggestedActions={suggestedActions}
        onSelectAction={onSuggestedAction}
      />
    );

  return (
      <>
        {/* ADR-160: Agent bubbles stack above the chat window */}
        <AgentBubbleStack />
        {/* Focus scrim: a staged prepared action or a one-shot preview is a
            stop-and-decide moment, so dim the dashboard behind the floating
            window (sits below the z-50 window; clicks are blocked but it does
            not dismiss, to avoid losing typed instructions). */}
        {(preparedActionDraft || oneshotResult) && (
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm animate-in fade-in-0"
            aria-hidden="true"
          />
        )}
        <FloatingChatWindow
          chatContainerRef={chatContainerRef}
        state={{
          isEnlarged,
          isDragOver,
          isOnline,
          isCliStale,
          isRunning,
          terminalFocused,
          chatView,
          isOperationMode,
        }}
        handleDragOver={handleDragOver}
        handleDragLeave={handleDragLeave}
        handleDrop={handleDrop}
        header={header}
        terminalContainerRef={terminalContainerRef}
        setTerminalFocused={setTerminalFocused}
        welcomeOverlay={
          oneshotResult ? (
            <StaticChatResult result={oneshotResult} onRunLive={onRunLiveResult} />
          ) : (
            preparedActionPanel ?? welcomeOverlay
          )
        }
        onReconnectDetached={(cliId) => startCli(cliId as CliId)}
      >
        {oneshotResult || preparedActionDraft ? null : terminalBottom}
        {terminalFocusStrip}
        {panels}
      </FloatingChatWindow>
    </>
  );
}

export function StaticChatResult({
  result,
  onRunLive,
}: {
  result: OneshotResult;
  onRunLive?: (result: OneshotResult) => Promise<void> | void;
}) {
  return (
    <div
      data-testid="chat-static-result"
      className="absolute inset-0 z-20 overflow-auto bg-[var(--bg-primary)] px-6 py-5 text-sm text-[var(--text-primary)]"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-[var(--text-primary)]">
            Preview output
          </div>
          <div className="text-xs text-[var(--text-muted)]">
            Click Run live workflow to execute the real runbook in the selected client.
          </div>
        </div>
        <button
          type="button"
          className="shrink-0 rounded-lg border border-[var(--accent-primary)]/35 bg-[var(--accent-primary)]/10 px-3 py-2 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!onRunLive || !result.prompt.trim()}
          onClick={() => onRunLive?.(result)}
        >
          Run live workflow
        </button>
      </div>
      <div className="mb-4">
        <div className="mb-1 text-[10px] font-semibold uppercase text-[var(--text-muted)]">
          User
        </div>
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2">
          Clicked Run: {result.actionLabel}
        </div>
      </div>
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase text-[var(--text-muted)]">
          Assistant
        </div>
        <pre className="whitespace-pre-wrap rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-3 font-mono text-xs leading-5 text-[var(--text-primary)]">
          {result.resultText}
        </pre>
      </div>
    </div>
  );
}
