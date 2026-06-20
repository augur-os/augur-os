import { create } from "zustand";
import type { PreparedActionDraft } from "@/lib/actions/preparedActionDraft";
import { mcpCall } from "@/lib/mcp/client";

export type ChatMode = "ide" | "remote" | "local" | "auto";

export type CliId =
  | "claude"
  | "codex"
  | "cursor-cli"
  | "kimi"
  | "gemini"
  | "ollama"
  | "opencode"
  | "copilot-cli"
  | "claude-kimi";

/** Typed context for chat sessions — replaces `any` */
export interface ChatContext {
  page?: string;
  skill?: string;
  hub?: string;
  actionId?: string;
  actionName?: string;
  filePath?: string;
  selection?: string;
  [key: string]: unknown;
}

export interface AttachedFile {
  originalName: string;
  stagedPath: string;
  size: number;
  mimeType: string;
  timestamp: number;
}

export interface CliProcessState {
  cliId: CliId;
  status: "idle" | "running" | "waiting" | "error" | "exited";
  pid?: number;
}

// ADR-035/036/047/535: Chat view mode.
// 'chat' is a legacy persisted value; active sessions normalize to terminal.
export type ChatView = "terminal" | "chat" | "action-dialog" | "actions-list";

// ADR-035: Embedded action data (passed from action buttons)
export interface EmbeddedAction {
  id: string;
  name: string;
  description?: string;
  prompt: string;
  recommendedAgent?: string;
}

// ADR-130 Phase 2: Oneshot result message for read-only display in FloatingChat
export interface OneshotResult {
  actionId: string;
  actionLabel: string;
  resultText: string;
  timestamp: Date;
  /** Original prompt — becomes context if user starts a follow-up */
  prompt: string;
}

export interface ChatState {
  isOpen: boolean;
  mode: ChatMode;
  context: ChatContext;
  agent: string;
  initialPrompt: string;
  // Draft hand-off: when true, the chat opens with initialPrompt seeded into an
  // editable input WITHOUT auto-starting a CLI; the user reviews/edits and sends.
  draft: boolean;
  isWaiting: boolean;

  // CLI state (ADR-034)
  selectedCli: CliId;
  cliProcess: CliProcessState | null;
  attachedFiles: AttachedFile[];

  // ADR-035: Enlarge toggle
  isEnlarged: boolean;

  // ADR-035: View mode and embedded action
  chatView: ChatView;
  embeddedAction: EmbeddedAction | null;
  preparedActionDraft: PreparedActionDraft | null;

  // Terminal focus mode (direct keyboard input to PTY)
  terminalFocused: boolean;

  // ADR-047: Terminal fallback (auto-switch to terminal for TUI content)
  terminalFallbackActive: boolean;

  // ADR-116 Phase 3B: Session persistence
  sessionId: string | null;

  // ADR-130 Phase 2: Oneshot result for inline display / FloatingChat hand-off
  oneshotResult: OneshotResult | null;

  openChat: (params: {
    mode: ChatMode;
    context?: ChatContext;
    agent?: string;
    initialPrompt?: string;
    draft?: boolean;
    isWaiting?: boolean;
  }) => void;
  closeChat: () => void;
  setWaiting: (waiting: boolean) => void;
  setSessionId: (id: string | null) => void;

  // CLI actions (ADR-034)
  setSelectedCli: (cli: CliId) => void;
  setCliProcess: (state: CliProcessState | null) => void;
  addAttachedFile: (file: AttachedFile) => void;
  removeAttachedFile: (stagedPath: string) => void;
  clearAttachedFiles: () => void;

  // ADR-035 actions
  toggleEnlarged: () => void;
  setEnlarged: (enlarged: boolean) => void;
  setChatView: (view: ChatView) => void;
  setEmbeddedAction: (action: EmbeddedAction | null) => void;
  openChatWithPreparedActionDraft: (
    draft: PreparedActionDraft,
    context?: ChatContext,
  ) => void;
  clearPreparedActionDraft: () => void;
  setTerminalFocused: (focused: boolean) => void;

  // ADR-047 actions
  setTerminalFallbackActive: (active: boolean) => void;

  // ADR-144: Clear initial prompt after first send
  clearInitialPrompt: () => void;

  // ADR-130 Phase 2 actions
  setOneshotResult: (result: OneshotResult | null) => void;
  openChatWithOneshotResult: (result: OneshotResult) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  isOpen: false,
  mode: "ide",
  context: {},
  agent: "default",
  initialPrompt: "",
  draft: false,
  isWaiting: false,

  // CLI defaults (ADR-034)
  selectedCli: "claude",
  cliProcess: null,
  attachedFiles: [],

  // ADR-035 defaults
  isEnlarged: false,
  chatView: "terminal",
  embeddedAction: null,
  preparedActionDraft: null,
  terminalFocused: false,
  terminalFallbackActive: false,

  // ADR-116 Phase 3B defaults
  sessionId: null,

  // ADR-130 Phase 2 defaults
  oneshotResult: null,

  openChat: ({
    mode,
    context = {},
    agent = "default",
    initialPrompt = "",
    draft = false,
  }) => {
    const newSessionId = crypto.randomUUID();
    set({
      isOpen: true,
      mode,
      context,
      agent,
      initialPrompt,
      draft,
      isWaiting: false,
      sessionId: newSessionId,
      preparedActionDraft: null,
      oneshotResult: null,
    });

    mcpCall("update-chat-session", {
      isActive: true,
      mode,
      context,
      status: "idle",
      startTime: new Date().toISOString(),
    }).catch((err: unknown) => console.error("Failed to persist session", err));
  },

  closeChat: () =>
    set({
      isOpen: false,
      draft: false,
      chatView: "terminal",
      embeddedAction: null,
      preparedActionDraft: null,
      oneshotResult: null,
      terminalFocused: false,
      terminalFallbackActive: false,
      sessionId: null,
    }),

  setWaiting: (waiting) => set({ isWaiting: waiting }),

  setSessionId: (id) => set({ sessionId: id }),

  // CLI actions (ADR-034)
  setSelectedCli: (cli) => set({ selectedCli: cli }),

  setCliProcess: (state) => set({ cliProcess: state }),

  addAttachedFile: (file) =>
    set((prev) => ({ attachedFiles: [...prev.attachedFiles, file] })),

  removeAttachedFile: (stagedPath) =>
    set((prev) => ({
      attachedFiles: prev.attachedFiles.filter(
        (f) => f.stagedPath !== stagedPath,
      ),
    })),

  clearAttachedFiles: () => set({ attachedFiles: [] }),

  // ADR-035 actions
  toggleEnlarged: () => set((prev) => ({ isEnlarged: !prev.isEnlarged })),
  setEnlarged: (enlarged) => set({ isEnlarged: enlarged }),

  setChatView: (view) => set({ chatView: view }),

  setEmbeddedAction: (action) => set({ embeddedAction: action }),

  openChatWithPreparedActionDraft: (preparedActionDraft, context = {}) => {
    const newSessionId = crypto.randomUUID();
    const nextContext: ChatContext = {
      actionId: preparedActionDraft.id,
      actionName: preparedActionDraft.label,
      page: context.page ?? preparedActionDraft.page,
      ...context,
    };

    set({
      isOpen: true,
      mode: "ide",
      context: nextContext,
      agent: preparedActionDraft.recommendedAgent ?? "default",
      initialPrompt: "",
      draft: false,
      isWaiting: false,
      sessionId: newSessionId,
      chatView: "terminal",
      embeddedAction: null,
      preparedActionDraft,
      oneshotResult: null,
      terminalFocused: false,
      terminalFallbackActive: false,
    });

    mcpCall("update-chat-session", {
      isActive: true,
      mode: "ide",
      context: nextContext,
      status: "idle",
      startTime: new Date().toISOString(),
    }).catch((err: unknown) => console.error("Failed to persist session", err));
  },

  clearPreparedActionDraft: () => set({ preparedActionDraft: null }),

  setTerminalFocused: (focused) => set({ terminalFocused: focused }),

  // ADR-047 actions
  setTerminalFallbackActive: (active) =>
    set({ terminalFallbackActive: active }),

  // ADR-144: Clear initial prompt after first send
  clearInitialPrompt: () => set({ initialPrompt: "" }),

  // ADR-130 Phase 2 actions
  setOneshotResult: (result) => set({ oneshotResult: result }),

  openChatWithOneshotResult: (result) => {
    const newSessionId = crypto.randomUUID();
    set({
      isOpen: true,
      mode: "ide",
      context: { actionId: result.actionId, actionName: result.actionLabel },
      agent: "default",
      initialPrompt: "",
      draft: false,
      isWaiting: false,
      sessionId: newSessionId,
      // ADR-535: Always use terminal view — chat bubble view removed
      chatView: "terminal",
      oneshotResult: result,
      embeddedAction: null,
      preparedActionDraft: null,
    });
  },
}));
