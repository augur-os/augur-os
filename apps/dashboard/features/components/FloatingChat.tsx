// TODO_CLEANUP: This controller is still large — keep extracting behavior into focused hooks.
"use client";

import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  useReducer,
} from "react";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles, Search, Activity } from "lucide-react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { isFallbackResponse } from "@/lib/mcp/types";
import {
  useChatStore,
  type CliId,
  type OneshotResult,
} from "@/lib/stores/chatStore";
import { useModeStore } from "@/lib/stores/modeStore";
import { useCliChat } from "@/features/hooks/useCliChat";
import { useXtermTerminal } from "@/features/hooks/useXtermTerminal";
import { useIdeBridge } from "@/features/hooks/useIdeBridge";
import { useSessionLifecycle } from "@/features/hooks/useSessionLifecycle";
import { useOnlineStatus } from "@/features/hooks/useOnlineStatus";
import { useCliHealthPoller } from "@/features/hooks/useCliHealthPoller";
import { useTheme } from "@/hooks/useTheme";
import {
  getPtyStreamParser,
  resetPtyStreamParser,
} from "@/lib/chat/ptyStreamParser";
import { mcpCall } from "@/lib/mcp/client";
import { safeJson } from "@/lib/safe-json";
import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";
import { composePreparedActionPrompt } from "@/lib/actions/preparedActionDraft";
import { renderFloatingChatLayout as FloatingChatLayout } from "@/features/components/chat/ChatLayout";
import {
  getActiveCliId,
  getCliStatusLabel,
  buildMagicPrompt,
} from "@/components/chat/utils";
import type {
  McpTool,
  SlashCommand,
  FloatingChatCliProcess,
  FloatingChatConfig,
  FloatingChatMessage,
  FloatingChatAttachedFile,
  MagicContextPayload,
  SuggestedAction,
} from "@/features/components/chat/types";

const COMPOSER_MIN_HEIGHT = 48;
const COMPOSER_MAX_HEIGHT = 200;
const CLI_COLORS: Record<string, string> = {
  claude: "var(--accent-secondary)",
  "cursor-cli": "var(--accent-info)",
  copilot: "var(--accent-success)",
  windsurf: "var(--accent-warning)",
  codex: "var(--accent-danger)",
  kimi: "var(--accent-primary)",
  gemini: "var(--accent-primary)",
};

function getCliAvatarColor(cliId: string): string {
  return CLI_COLORS[cliId] || "var(--text-muted)";
}

interface CliStatusResponse {
  status?: string;
  pid?: number;
}

const TERMINAL_HANDOFF_ACTIVE_STATUSES = new Set(["running", "detached"]);

function getClipboardFiles(clipboardData: DataTransfer): File[] {
  const files = Array.from(clipboardData.files ?? []);
  if (files.length > 0) {
    return files;
  }

  return Array.from(clipboardData.items ?? [])
    .filter((item) => item.kind === "file")
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
}

interface PreparedActionState {
  remarks: string;
  error: string | null;
  sending: boolean;
}

type PreparedActionAction =
  | { type: "reset" }
  | { type: "remarks"; value: string }
  | { type: "error"; value: string | null }
  | { type: "sending"; value: boolean };

const INITIAL_PREPARED_ACTION_STATE: PreparedActionState = {
  remarks: "",
  error: null,
  sending: false,
};

function preparedActionReducer(
  state: PreparedActionState,
  action: PreparedActionAction,
): PreparedActionState {
  switch (action.type) {
    case "reset":
      return INITIAL_PREPARED_ACTION_STATE;
    case "remarks":
      return { ...state, remarks: action.value };
    case "error":
      return { ...state, error: action.value };
    case "sending":
      return { ...state, sending: action.value };
  }
}

function resizeComposerTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.max(
    COMPOSER_MIN_HEIGHT,
    Math.min(textarea.scrollHeight, COMPOSER_MAX_HEIGHT),
  )}px`;
}

function resetComposerTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) return;
  textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
}

function demoResetReasonForResult(result: OneshotResult): string {
  const match = result.prompt.match(/\breason\s+(before-[A-Za-z0-9_-]+)/);
  if (match?.[1]) {
    return match[1];
  }
  return `before-${result.actionId || "demo-live-workflow"}`;
}

function useFloatingChatController() {
  const {
    isOpen,
    mode: chatMode,
    closeChat,
    isEnlarged,
    toggleEnlarged,
    setEnlarged,
    chatView,
    setChatView,
    embeddedAction,
    setEmbeddedAction,
    terminalFocused,
    setTerminalFocused,
    setCliProcess,
    terminalFallbackActive,
    setTerminalFallbackActive,
    initialPrompt,
    clearInitialPrompt,
    draft,
    oneshotResult,
    setOneshotResult,
    preparedActionDraft,
    clearPreparedActionDraft,
  } = useChatStore();
  const { mode: dashboardMode } = useModeStore();
  const { effectiveMode } = useTheme();
  const { sendPrompt: sendToIde } = useIdeBridge();
  const {
    messages,
    configs,
    selectedCli,
    cliProcess,
    attachedFiles,
    startCli,
    stopCli,
    switchCli,
    sendMessage,
    sendRawKey,
    sendSystemCommand,
    uploadFile,
    removeAttachedFile,
    setMessages,
    clearMessages,
    sessionConflict,
    recordSessionConflict,
    takeOverSessionConflict,
  } = useCliChat();

  const pathname = usePathname();

  const [input, setInput] = useState("");
  const [isMinimized, setIsMinimized] = useState(false);
  const [showCliSelector, setShowCliSelector] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [preparedActionState, dispatchPreparedAction] = useReducer(
    preparedActionReducer,
    INITIAL_PREPARED_ACTION_STATE,
  );
  const preparedActionRemarks = preparedActionState.remarks;
  const preparedActionError = preparedActionState.error;
  const preparedActionSending = preparedActionState.sending;
  const setPreparedActionRemarks = useCallback((value: string) => {
    dispatchPreparedAction({ type: "remarks", value });
  }, []);
  const setPreparedActionError = useCallback((value: string | null) => {
    dispatchPreparedAction({ type: "error", value });
  }, []);
  const setPreparedActionSending = useCallback((value: boolean) => {
    dispatchPreparedAction({ type: "sending", value });
  }, []);

  // Draft hand-off (Browse AI action → ADR-748 follow-up): seed the editable
  // input with the prefilled prompt once, WITHOUT auto-starting a CLI. The user
  // reviews/edits and sends; handleSubmit starts the CLI on send when draft.
  useEffect(() => {
    let animationFrameId: number | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    if (isOpen && draft && initialPrompt) {
      setInput(initialPrompt);
      clearInitialPrompt();
      const resize = () => {
        resizeComposerTextarea(textareaRef.current);
      };
      if (typeof window.requestAnimationFrame === "function") {
        animationFrameId = window.requestAnimationFrame(resize);
      } else {
        timeoutId = setTimeout(resize, 0);
      }
    }

    return () => {
      if (
        animationFrameId !== null &&
        typeof window.cancelAnimationFrame === "function"
      ) {
        window.cancelAnimationFrame(animationFrameId);
      }
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [isOpen, draft, initialPrompt, clearInitialPrompt]);

  useEffect(() => {
    dispatchPreparedAction({ type: "reset" });
  }, [preparedActionDraft?.id]);

  // ADR-271: Unified panel state for mutual exclusion
  const [activePanel, setActivePanel] = useState<"context" | "actions" | "search" | null>(null);
  // mcpTools derived from useMcpQuery below (no intermediate state)
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [pendingInsightCountOverride, setPendingInsightCountOverride] =
    useState<number | null>(null);
  const [magicLoading, setMagicLoading] = useState(false);
  const [terminalHandoffOpening, setTerminalHandoffOpening] = useState(false);
  // True once the xterm buffer has received real output; reset whenever the
  // terminal is cleared. Gates the builder-mode empty state.
  const [terminalHasContent, setTerminalHasContent] = useState(false);
  // suggestedActions derived from mcpToolsData below (no intermediate state)
  // slashCommands derived from useMcpQuery below (no intermediate state)

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const selectorRef = useRef<HTMLDivElement>(null);
  // ADR-271: Refs for new unified toolbar buttons
  const contextPortalRef = useRef<HTMLDivElement>(null);
  const contextPopoverRef = useRef<HTMLDivElement>(null);
  const actionsPortalRef = useRef<HTMLDivElement>(null);
  const actionsPopoverRef = useRef<HTMLDivElement>(null);
  const searchPortalRef = useRef<HTMLDivElement>(null);
  const searchPopoverRef = useRef<HTMLDivElement>(null);
  const setChatViewAndReveal = useCallback(
    (view: "chat" | "terminal" | "action-dialog" | "actions-list") => {
      if (view !== "terminal") {
        setIsMinimized(false);
      }
      setChatView(view);
    },
    [setChatView],
  );
  const setEmbeddedActionAndReveal = useCallback(
    (action: typeof embeddedAction) => {
      if (action !== null) {
        setIsMinimized(false);
      }
      setEmbeddedAction(action);
    },
    [setEmbeddedAction],
  );

  useEffect(() => {
    if (!isOpen) return;

    if (chatView === "action-dialog") {
      setIsMinimized(false);
      setChatView("terminal");
      if (embeddedAction !== null) {
        setEmbeddedAction(null);
      }
      return;
    }

    if (chatView === "chat") {
      setChatView("terminal");
    }
  }, [isOpen, chatView, embeddedAction, setChatView, setEmbeddedAction]);

  const isRunning = cliProcess?.status === "running";
  const { airplaneMode } = useAirplaneModeStore();

  // Keep startup prompt context opt-in. Normal chat starts should not inject
  // page context; action prompts and explicit context tools provide their own.
  type StartCliOptions = NonNullable<Parameters<typeof startCli>[1]>;
  const startCliWrapped = useCallback(
    (cliId: CliId, overrides: Partial<StartCliOptions> = {}) =>
      startCli(cliId, {
        airplaneMode,
        themeMode: effectiveMode,
        autoContext: overrides.autoContext ?? false,
        verbosity: overrides.verbosity ?? (dashboardMode === "operation" ? "quiet" : "normal"),
        ...overrides,
      }),
    [startCli, airplaneMode, effectiveMode, dashboardMode],
  );

  // ADR-047 Phase 5: Mode-aware label renaming
  const isOperationMode = dashboardMode === "operation";

  // ADR-104: Always use terminal view in operation mode, auto-start CLI
  // ADR-047: Terminal in dev mode, auto-start CLI in operation mode
  // ADR-535 0E: Check for detached sessions before starting fresh
  const hasInitializedView = useRef(false);
  const isEmbeddedActionDialog =
    chatView === "action-dialog" && embeddedAction !== null;
  const hasPreparedActionDraft = preparedActionDraft !== null;
  const hasEditablePromptDraft = draft && initialPrompt.trim().length > 0;
  const shouldCheckInitialCliSession =
    isOpen &&
    dashboardMode === "operation" &&
    !isEmbeddedActionDialog &&
    !hasPreparedActionDraft &&
    !hasEditablePromptDraft &&
    !hasInitializedView.current;

  const { data: initialCliSession, error: initialCliSessionError } =
    useQuery<CliStatusResponse>({
      queryKey: ["cli-session-status", selectedCli],
      queryFn: async () => {
        const response = await fetch(`/api/cli?cliId=${selectedCli}`);
        return response.ok ? response.json() : { status: "unknown" };
      },
      enabled: shouldCheckInitialCliSession,
      staleTime: 0,
      refetchOnWindowFocus: false,
      retry: false,
    });

  useEffect(() => {
    if (!isOpen) {
      hasInitializedView.current = false;
      return;
    }

    if (!hasInitializedView.current) {
      hasInitializedView.current = true;
      if (dashboardMode === "operation") {
        if (
          isEmbeddedActionDialog ||
          hasPreparedActionDraft ||
          hasEditablePromptDraft
        ) {
          return;
        }
        if (!initialCliSession && !initialCliSessionError) {
          hasInitializedView.current = false;
          return;
        }
        if (initialCliSessionError) {
          startCliWrapped(selectedCli);
          return;
        }
        if (
          initialCliSession.status === "running" ||
          initialCliSession.status === "detached"
        ) {
          // Session exists on server — mark as running so xterm connects/reconnects
          setCliProcess({
            cliId: selectedCli,
            status: "running",
            pid: initialCliSession.pid,
          });
        } else {
          // No session or exited — start fresh
          startCliWrapped(selectedCli);
        }
      }
    }
  }, [
    isOpen,
    dashboardMode,
    isEmbeddedActionDialog,
    hasPreparedActionDraft,
    hasEditablePromptDraft,
    initialCliSession,
    initialCliSessionError,
    cliProcess,
    selectedCli,
    startCliWrapped,
    setCliProcess,
  ]);

  // Auto-size chat window: enlarged in dev mode, compact in operation mode
  const prevModeRef = useRef(dashboardMode);
  useEffect(() => {
    if (prevModeRef.current === dashboardMode) return;
    prevModeRef.current = dashboardMode;
    setEnlarged(dashboardMode === "development");
  }, [dashboardMode, setEnlarged]);

  // ADR-157: Continuous session lifecycle (auto-refocus, idle save, close save)
  const { saveBeforeClose } = useSessionLifecycle({
    sendSystemCommand,
    isRunning,
    isOperationMode,
  });

  // ADR-271: Close active panel on click outside
  useEffect(() => {
    if (!activePanel) return;
    const refs: Record<string, { popover: React.RefObject<HTMLDivElement | null>; portal: React.RefObject<HTMLDivElement | null> }> = {
      context: { popover: contextPopoverRef, portal: contextPortalRef },
      actions: { popover: actionsPopoverRef, portal: actionsPortalRef },
      search: { popover: searchPopoverRef, portal: searchPortalRef },
    };
    const { popover, portal } = refs[activePanel];
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      const inPopover = popover.current?.contains(target);
      const inPortal = portal.current?.contains(target);
      if (!inPopover && !inPortal) {
        setActivePanel(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [activePanel]);

  // ADR-116: Online status and CLI health detection
  const isOnline = useOnlineStatus();
  const activeCliId = getActiveCliId(isRunning, cliProcess?.cliId);
  const isCliStale = useCliHealthPoller(activeCliId, 30000);

  // ADR-078: Fetch pending insight count for Magic button badge
  const { data: insightsData } = useMcpQuery<{ count: number }>(
    ["insights-pending"],
    "insights-pending",
    "static",
    {
      // count_only: the badge reads `count` alone — the full pending list can
      // exceed 1MB per response and its parse serialized the MCP server.
      args: { count_only: true },
      enabled: !!pathname,
      fallback: { count: 0, insights: [] } as any,
    },
  );
  const pendingInsightCount =
    pendingInsightCountOverride ?? (isFallbackResponse(insightsData) ? 0 : (insightsData?.count || 0));

  // ADR-116: Auto-fetch MCP tools on mount and page change so the Actions
  // button is visible in operation mode (previously only fetched on click,
  // which was impossible when the button was hidden due to empty tools).
  const mcpMode = isOperationMode ? "operation" : "development";
  const { data: mcpToolsData, loading: mcpToolsLoading } = useMcpQuery<{
    tools: Array<{ name: string; description?: string; displayName?: string; meta?: { icon?: string } }>;
  }>(
    ["mcp-tools", mcpMode],
    "list-mcp-tools",
    "static",
    {
      args: { action: "summary", include_disabled: true, mode: mcpMode },
      enabled: !!pathname,
    },
  );
  const mcpTools: McpTool[] = useMemo(
    () =>
      (mcpToolsData?.tools ?? []).map((t) => ({
        name: t.name,
        description: t.description || t.displayName,
      })),
    [mcpToolsData],
  );

  // Fetch slash commands for dev mode Commands button
  const hub = pathname?.split("/")[1] || "";
  const { data: commandsData } = useMcpQuery<{ commands: SlashCommand[] }>(
    ["slash-commands", hub],
    "get-settings",
    "config",
    {
      args: { scope: "workflows", hub },
      enabled: !!hub && !isOperationMode,
    },
  );
  const slashCommands: SlashCommand[] = useMemo(
    () => commandsData?.commands ?? [],
    [commandsData],
  );

  // ADR-535 Phase 3: Hardcoded first-run actions that work as natural language prompts
  const suggestedActions: SuggestedAction[] = useMemo(() => {
    if (!isOperationMode) return [];
    return [
      { label: "What can you do?", toolName: "__prompt__what_can_you_do", icon: Sparkles },
      { label: "Search my knowledge", toolName: "__prompt__search_knowledge", icon: Search },
      { label: "Show system health", toolName: "__prompt__system_health", icon: Activity },
    ];
  }, [isOperationMode]);

  // Forward terminal keyboard input to PTY in focus mode
  const handleTerminalData = useCallback(
    (data: string) => {
      sendRawKey(data);
    },
    [sendRawKey],
  );

  // Handle CLI process exit detected via SSE stream
  const handleCliExit = useCallback(
    (code: number | null) => {
      // Feed exit to the PTY parser so parser state closes with the session.
      getPtyStreamParser().processExit(code ?? 0);
      setCliProcess({ cliId: cliProcess?.cliId ?? "claude", status: "exited" });
      setTerminalFocused(false);
      // Map common exit/signal codes to calm, human-readable status. The Unix
      // convention is 128 + signal number, so 129/130/137/143 are ordinary
      // session-end signals — not errors. Keep the raw code only for genuinely
      // unexpected exits where it aids debugging.
      const exitMessage =
        code === null || code === 0
          ? "CLI session ended."
          : code === 130
            ? "CLI session stopped (interrupted)."
            : code === 129
              ? "CLI session ended (connection closed)."
              : code === 143
                ? "CLI session stopped."
                : code === 137
                  ? "CLI session stopped (killed)."
                  : `CLI session ended unexpectedly (exit code ${code}).`;
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: exitMessage,
          timestamp: Date.now(),
        },
      ]);
      // Clear chat session page context
      mcpCall("update-chat-session", { isActive: false, status: "idle", context: {} }).catch(() => {});
    },
    [cliProcess?.cliId, setCliProcess, setTerminalFocused, setMessages],
  );

  // ADR-535 0F: Detach session — close UI without killing PTY
  const handleDetach = useCallback(async () => {
    if (!cliProcess || cliProcess.status !== "running") return;

    try {
      const res = await fetch("/api/cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "detach", cliId: cliProcess.cliId }),
      });

      if (res.ok) {
        setCliProcess(null);
        setMessages((prev) => [
          ...prev,
          {
            role: "system",
            content: "Session detached. You can reconnect later.",
            timestamp: Date.now(),
          },
        ]);
        closeChat();
      }
    } catch (err) {
      console.error("Failed to detach session:", err);
    }
  }, [cliProcess, setCliProcess, setMessages, closeChat]);

  // Feed raw PTY output to the chat parser beside the xterm SSE stream.
  const handleRawOutput = useCallback((data: string) => {
    // Track whether the terminal has any real output so the empty-state overlay
    // is only shown over a genuinely blank terminal — never painting over a
    // stopped/exited session's final output (rule 1: don't hide data).
    if (data && data.trim().length > 0) {
      setTerminalHasContent(true);
    }
    getPtyStreamParser().feed(data);
  }, []);

  // ADR-271: Append text to textarea, close panel, refocus
  const appendToInput = useCallback((text: string) => {
    setInput((prev) => {
      const prefix = prev.length > 0 && !prev.endsWith(" ") ? " " : "";
      return prev + prefix + text;
    });
    setActivePanel(null);
    textareaRef.current?.focus();
  }, []);

  const insertToolName = appendToInput;
  const onAttachFile = appendToInput;

  const { terminalContainerRef, clearTerminal, containerRef } =
    useXtermTerminal({
      cliId: activeCliId,
      isRunning,
      focusMode: terminalFocused,
      onTerminalData: handleTerminalData,
      onExit: handleCliExit,
      onRawOutput: handleRawOutput,
      mode: effectiveMode,
    });

  // Clear terminal and reset parser when CLI changes (and only when it changes)
  const prevCliRef = useRef(selectedCli);
  useEffect(() => {
    if (prevCliRef.current !== selectedCli) {
      clearTerminal();
      setTerminalHasContent(false);
      resetPtyStreamParser();
      prevCliRef.current = selectedCli;
    }
  }, [selectedCli, clearTerminal]);

  const handleClearConversation = useCallback(() => {
    clearTerminal();
    setTerminalHasContent(false);
    clearMessages(); // ADR-535: also clear localStorage
  }, [clearTerminal, clearMessages]);

  // Exit focus mode when CLI stops
  useEffect(() => {
    if (!isRunning && terminalFocused) {
      setTerminalFocused(false);
    }
  }, [isRunning, terminalFocused, setTerminalFocused]);

  // Escape key exits focus mode
  useEffect(() => {
    if (!terminalFocused) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setTerminalFocused(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [terminalFocused, setTerminalFocused]);

  // Click outside terminal exits focus mode
  useEffect(() => {
    if (!terminalFocused) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setTerminalFocused(false);
      }
    };

    // Delay to avoid immediately catching the activating click
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [terminalFocused, setTerminalFocused, containerRef]);

  // Auto-focus chat textarea when panel opens, and redirect stray printable
  // keystrokes so global shortcuts (h/c/s/etc.) don't fire when the user
  // starts typing before clicking the input.
  // ADR-535 0L: Also re-focuses after exiting terminal focus mode (terminalFocused deps change).
  useEffect(() => {
    if (!isOpen || isMinimized || terminalFocused) return;

    // Focus textarea immediately on open (or when returning from terminal focus)
    // setTimeout(0) ensures xterm has released focus before we claim it
    setTimeout(() => textareaRef.current?.focus(), 0);

    // Capture-phase handler intercepts printable keys before the
    // bubble-phase useKeyboardShortcuts handler can match them.
    const redirectKeystroke = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      // Already in a text input — don't interfere
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      )
        return;
      // Modifier combos should still work as shortcuts
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      // Only redirect printable characters (single-char keys)
      if (e.key.length !== 1) return;

      e.preventDefault();
      e.stopPropagation();
      textareaRef.current?.focus();
      setInput((prev) => prev + e.key);
    };

    // Refocus textarea when user switches back to this browser tab
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        textareaRef.current?.focus();
      }
    };

    window.addEventListener("keydown", redirectKeystroke, true);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("keydown", redirectKeystroke, true);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [isOpen, isMinimized, terminalFocused]);

  // Close selector on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        selectorRef.current &&
        !selectorRef.current.contains(e.target as Node)
      ) {
        setShowCliSelector(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Submit composer text. On cold-start (no running CLI) hand the prompt to the
  // server via oneshotPrompt so it is injected once the CLI is ready — this
  // avoids the client-side readiness race that fired a spurious "No CLI
  // running" notice and silently dropped the user's first message (the
  // "starts on send" promise). See app/api/cli/actions.ts (ADR-104).
  const submitText = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text) return;

      setInput("");
      resetComposerTextarea(textareaRef.current);

      if (!isRunning) {
        await startCliWrapped(selectedCli, { oneshotPrompt: text });
      } else {
        sendMessage(text);
      }

      // ADR-535 0L: Re-focus textarea after send (setTimeout handles React re-render timing)
      setTimeout(() => textareaRef.current?.focus(), 0);
    },
    [isRunning, startCliWrapped, selectedCli, sendMessage],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      await submitText(input);
    },
    [input, submitText],
  );

  const handleRunLiveResult = useCallback(
    async (result: OneshotResult) => {
      const prompt = result.prompt.trim();
      if (!prompt) return;

      const reason = demoResetReasonForResult(result);
      try {
        const reset = await mcpCall<{ success?: boolean; error?: string }>(
          "demo-run-reset",
          { reason },
        );
        if (reset?.success === false) {
          toast.error(reset.error || "Demo reset failed");
          return;
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Demo reset failed";
        toast.error(message);
        return;
      }

      setOneshotResult(null);
      await submitText(prompt);
    },
    [setOneshotResult, submitText],
  );

  // Auto-grow textarea as user types, while keeping action drafts readable.
  const handleTextareaChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);
      resizeComposerTextarea(e.target);
    },
    [],
  );

  // Enter sends the message (standard chat convention); Shift+Enter inserts a
  // newline. Cmd/Ctrl+Enter also sends, for muscle memory. Routes through
  // submitText so the first message cold-starts the CLI without dropping it.
  // Plain-Enter previously did nothing — a Browse/command draft prompt would sit
  // in the composer and Enter just added a newline, so the message never sent.
  const handleTextareaKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Don't intercept Enter while an IME composition is active (CJK/multilingual
      // input) — committing the composition would be swallowed as a send.
      if (e.nativeEvent.isComposing) return;
      if (e.key !== "Enter" || e.shiftKey) return;
      e.preventDefault();
      void submitText(input);
    },
    [input, submitText],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files) return;
      for (const file of Array.from(files)) {
        uploadFile(file);
      }
      e.target.value = "";
    },
    [uploadFile],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const files = getClipboardFiles(e.clipboardData);
      if (files.length === 0) {
        return;
      }

      e.preventDefault();
      for (const file of files) {
        uploadFile(file);
      }
    },
    [uploadFile],
  );

  // ADR-535 Phase 3: Handle suggested action — send label as natural language prompt
  const handleSuggestedAction = useCallback(
    async (action: SuggestedAction) => {
      // Send the human-readable label directly as a prompt. Cold-start uses
      // oneshotPrompt (server-side injection) to avoid the readiness race that
      // dropped the message and surfaced a spurious "No CLI running" notice.
      if (!isRunning) {
        await startCliWrapped(selectedCli, { oneshotPrompt: action.label });
      } else {
        sendMessage(action.label);
      }
      // ADR-535 0L: Re-focus textarea after suggested action
      setTimeout(() => textareaRef.current?.focus(), 0);
    },
    [isRunning, startCliWrapped, selectedCli, sendMessage],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = e.dataTransfer.files;
      for (const file of Array.from(files)) {
        uploadFile(file);
      }
    },
    [uploadFile],
  );

  const handleCliSelect = useCallback(
    (cliId: CliId) => {
      setShowCliSelector(false);
      if (cliId !== selectedCli) {
        switchCli(cliId);
      }
    },
    [selectedCli, switchCli],
  );

  // ADR-116 Phase 2B: Keyboard shortcuts for dev mode (Cmd+1 through Cmd+7)
  useEffect(() => {
    if (dashboardMode !== "development" || !isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        const num = parseInt(e.key, 10);
        if (num >= 1 && num <= 7) {
          e.preventDefault();
          const cliAtIndex = configs[num - 1];
          if (cliAtIndex && cliAtIndex.available) {
            handleCliSelect(cliAtIndex.cli_id as CliId);
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [dashboardMode, isOpen, configs, handleCliSelect]);

  const getStatusColor = () => {
    if (!cliProcess) return "bg-gray-500";
    switch (cliProcess.status) {
      case "running":
        return "bg-emerald-500";
      case "waiting":
        return "bg-yellow-500";
      case "error":
        return "bg-red-500";
      case "exited":
        return "bg-gray-500";
      default:
        return "bg-gray-500";
    }
  };

  const getCliLabel = (cliId: string) => {
    const config = configs.find((c) => c.cli_id === cliId);
    return config?.label || cliId;
  };

  const preparedActionTargetCli = isRunning && cliProcess ? cliProcess.cliId : selectedCli;
  const preparedActionTargetConfig = configs.find((config) => config.cli_id === preparedActionTargetCli);
  const preparedActionClientLabel =
    preparedActionTargetConfig?.label || getCliLabel(preparedActionTargetCli);
  const preparedActionCanSend =
    preparedActionDraft !== null &&
    preparedActionTargetConfig?.available !== false &&
    preparedActionTargetConfig?.enabled !== false &&
    !preparedActionSending;
  const preparedActionStatusError =
    preparedActionDraft && !preparedActionCanSend && !preparedActionSending
      ? "Select an enabled chat client."
      : preparedActionError;

  const handlePreparedActionSend = useCallback(async () => {
    if (!preparedActionDraft || preparedActionSending) return;

    const targetCli = isRunning && cliProcess ? cliProcess.cliId : selectedCli;
    const targetConfig = configs.find((config) => config.cli_id === targetCli);
    if (targetConfig?.available === false || targetConfig?.enabled === false) {
      setPreparedActionError("Select an enabled chat client.");
      return;
    }

    const prompt = composePreparedActionPrompt(
      preparedActionDraft,
      preparedActionRemarks,
    );

    setPreparedActionSending(true);
    setPreparedActionError(null);
    try {
      let sent = false;
      if (isRunning) {
        sent = (await sendMessage(prompt)) !== false;
      } else {
        sent =
          (await startCliWrapped(targetCli, { oneshotPrompt: prompt })) !==
          false;
      }
      if (!sent) {
        setPreparedActionError(
          isRunning
            ? "Failed to send prepared action."
            : `Failed to start ${preparedActionClientLabel}.`,
        );
        return;
      }
      clearPreparedActionDraft();
      setPreparedActionRemarks("");
    } catch (error) {
      setPreparedActionError(
        error instanceof Error ? error.message : "Failed to send prepared action.",
      );
    } finally {
      setPreparedActionSending(false);
    }
  }, [
    clearPreparedActionDraft,
    configs,
    isRunning,
    preparedActionClientLabel,
    preparedActionDraft,
    preparedActionRemarks,
    preparedActionSending,
    selectedCli,
    cliProcess,
    sendMessage,
    startCliWrapped,
    setPreparedActionError,
    setPreparedActionRemarks,
    setPreparedActionSending,
  ]);

  const handlePreparedActionCancel = useCallback(() => {
    clearPreparedActionDraft();
    setPreparedActionRemarks("");
    setPreparedActionError(null);
  }, [clearPreparedActionDraft, setPreparedActionError, setPreparedActionRemarks]);

  const handleMagicClick = useCallback(async () => {
    setMagicLoading(true);
    setMessages((prev) => [
      ...prev,
      {
        role: "system",
        content: `\u{1F50D} Analyzing ${pathname}...`,
        timestamp: Date.now(),
      },
    ]);

    try {
      const res = await fetch(`/api/insights/context?page=${pathname}`);
      const ctx = (res.ok ? await res.json() : {}) as MagicContextPayload;
      const magicPrompt = buildMagicPrompt(pathname, ctx);
      // Cold-start the CLI via oneshotPrompt so the analysis prompt is not
      // dropped when no CLI is running yet.
      if (!isRunning) {
        await startCliWrapped(selectedCli, { oneshotPrompt: magicPrompt });
      } else {
        sendMessage(magicPrompt);
      }
      setPendingInsightCountOverride(0);
    } catch (e) {
      console.error("Magic button error:", e);
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: "\u274C Failed to analyze page",
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setMagicLoading(false);
    }
  }, [pathname, sendMessage, setMessages, isRunning, startCliWrapped, selectedCli]);

  const handleRunCommand = useCallback(
    (command: SlashCommand) => {
      const scopeCtx =
        pathname && pathname !== "/"
          ? `\n\n**Page Scope**: ${pathname}\nApply this command only to files and components related to this page and its subpages.`
          : "";
      const prompt = `/${command.name}${scopeCtx}`;
      sendToIde(prompt);
    },
    [pathname, sendToIde],
  );

  const handleOpenTerminal = useCallback(async () => {
    if (terminalHandoffOpening) return;
    setTerminalHandoffOpening(true);
    try {
      const handoffCliId = (cliProcess?.cliId ?? selectedCli) as CliId;
      const statusResponse = await fetch(
        `/api/cli?cliId=${encodeURIComponent(handoffCliId)}`,
      );
      const statusData =
        (await safeJson<CliStatusResponse>(statusResponse)) || {};
      if (
        !statusResponse.ok ||
        !TERMINAL_HANDOFF_ACTIVE_STATUSES.has(statusData.status ?? "")
      ) {
        const message =
          "CLI session is not running. Start it before opening a native terminal.";
        setCliProcess({
          cliId: handoffCliId,
          status: statusData.status === "exited" ? "exited" : "error",
          pid: statusData.pid ?? cliProcess?.pid,
        });
        setTerminalFocused(false);
        toast.error(message);
        setMessages((prev) => [
          ...prev,
          { role: "system", content: message, timestamp: Date.now() },
        ]);
        return;
      }

      const response = await fetch("/api/session/open-terminal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          currentPage: pathname || "dashboard",
          dashboardMode,
          themeMode: effectiveMode,
        }),
      });
      const data =
        (await safeJson<{
          code?: string;
          error?: string;
          owner?: Record<string, unknown>;
          sessionId?: string;
          shortcut?: string;
        }>(response)) || {};
      if (!response.ok || data.error) {
        const message =
          data.error || `Terminal handoff failed (${response.status})`;
        if (data.code === "SESSION_OWNED_ELSEWHERE") {
          recordSessionConflict(data);
        }
        toast.error(message);
        setMessages((prev) => [
          ...prev,
          { role: "system", content: message, timestamp: Date.now() },
        ]);
        return;
      }
      setCliProcess({
        cliId: handoffCliId,
        status: "exited",
        pid: cliProcess?.pid,
      });
      setTerminalFocused(false);
      // The PTY exited and the session moved to the native terminal — return
      // the embedded chat to a clean state instead of leaving the stale
      // "exit / Resume this session with: ..." buffer painted. Mirrors the
      // CLI-switch clean-up above (clearTerminal + resetPtyStreamParser).
      clearTerminal();
      setTerminalHasContent(false);
      resetPtyStreamParser();
      toast.success(`Opened ${data.shortcut || selectedCli} in native terminal.`);
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: `Opened ${data.shortcut || selectedCli} in native terminal.`,
          timestamp: Date.now(),
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Terminal handoff failed.";
      toast.error(message);
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: message,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setTerminalHandoffOpening(false);
    }
  }, [
    terminalHandoffOpening,
    pathname,
    dashboardMode,
    effectiveMode,
    cliProcess?.cliId,
    cliProcess?.pid,
    selectedCli,
    setCliProcess,
    setMessages,
    setTerminalFocused,
    clearTerminal,
    recordSessionConflict,
  ]);

  const handleSwitchSessionOwner = useCallback(() => {
    const owner = sessionConflict?.owner;
    if (owner?.surface === "dashboard-pty") {
      setChatViewAndReveal("terminal");
      toast.info("Switched to the dashboard terminal for this session.");
      return;
    }
    const pid = typeof owner?.pid === "number" ? ` PID ${owner.pid}` : "";
    const host =
      typeof owner?.host === "string" && owner.host.length > 0
        ? ` on ${owner.host}`
        : "";
    toast.info(`Session is already open in the native terminal${pid}${host}.`);
  }, [sessionConflict, setChatViewAndReveal]);

  const handleTakeOverSessionOwner = useCallback(async () => {
    await takeOverSessionConflict();
  }, [takeOverSessionConflict]);

  const statusColor = getStatusColor();
  const statusLabel = getCliStatusLabel(
    cliProcess as FloatingChatCliProcess | null,
  );
  const cliLabel = getCliLabel(selectedCli);
  const latestSystemMsg = messages
    .filter(
      (m) =>
        m.role === "system" &&
        // Lifecycle status lines ("Started claude (PID …)", "Stopped claude")
        // are already reflected in the header status dot/label; rendering them
        // as a persistent strip above the composer just adds orphaned clutter.
        !/^(Started|Stopped)\s/.test(m.content),
    )
    .slice(-1)[0];
  const layoutChatView =
    chatView === "action-dialog" || chatView === "chat" ? "terminal" : chatView;

  return {
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
    preparedActionError: preparedActionStatusError,
    preparedActionSending,
    preparedActionCanSend,
    onPreparedActionRemarksChange: setPreparedActionRemarks,
    onPreparedActionSend: handlePreparedActionSend,
    onPreparedActionCancel: handlePreparedActionCancel,
    chatContainerRef,
    // ADR-271: Unified panel state
    activePanel,
    setActivePanel,
    onAttachFile,
    mcpTools,
    mcpToolsLoading,
    insertToolName,
    slashCommands,
    handleRunCommand,
    handleMagicClick,
    magicLoading,
    pendingInsightCount,
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
    configs: configs as FloatingChatConfig[],
    getCliLabel,
    getCliAvatarColor,
    handleCliSelect,
    cliProcess: cliProcess as FloatingChatCliProcess | null,
    chatView: layoutChatView,
    setChatView: setChatViewAndReveal,
    isEnlarged,
    toggleEnlarged,
    startCli: async (cliId: CliId, overrides?: Partial<StartCliOptions>) => {
      await startCliWrapped(cliId, overrides);
    },
    stopCli,
    closeChat: () => {
      // ADR-157: Save context before closing
      saveBeforeClose();
      closeChat();
    },
    terminalFocused,
    latestSystemMsg: latestSystemMsg as FloatingChatMessage | undefined,
    // Drives the builder-mode empty state. Lifecycle "Started/Stopped" system
    // messages don't count as content (they're re-emitted on every load), so
    // the terminal is "empty" only when xterm has no output and there's no real
    // user/assistant exchange — then it's safe to show the welcome overlay.
    hasChatContent:
      terminalHasContent ||
      messages.some((m) => m.role === "user" || m.role === "assistant"),
    attachedFiles: attachedFiles as FloatingChatAttachedFile[],
    removeAttachedFile,
    setTerminalFocused,
    embeddedAction,
    sendMessage,
    sendRawKey,
    uploadFile,
    setTerminalFallbackActive,
    switchCli,
    sendToIde,
    setEmbeddedAction: setEmbeddedActionAndReveal,
    showHelpModal,
    setShowHelpModalState: setShowHelpModal,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    isDragOver,
    isOnline,
    isCliStale,
    terminalContainerRef,
    suggestedActions,
    onSuggestedAction: handleSuggestedAction,
    onClear: handleClearConversation,
    onDetach: handleDetach,
    onOpenTerminal: handleOpenTerminal,
    isTerminalHandoffOpening: terminalHandoffOpening,
    sessionConflict,
    onSwitchSessionOwner: handleSwitchSessionOwner,
    onTakeOverSessionOwner: handleTakeOverSessionOwner,
    onRunLiveResult: handleRunLiveResult,
  } satisfies Parameters<typeof FloatingChatLayout>[0];
}

export default function FloatingChat() {
  const layoutProps = useFloatingChatController();

  return <FloatingChatLayout {...layoutProps} />;
}
