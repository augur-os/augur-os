"use client";

import ActionsListView from "@/features/components/ActionsListView";
import HelpRequestModal from "@/features/components/HelpRequestModal";
import type {
  CliId,
  FloatingChatCliProcess,
  FloatingChatConfig,
} from "./types";

interface StartCliOptions {
  airplaneMode?: boolean;
  themeMode?: "light" | "dark";
  autoContext?: boolean;
  verbosity?: "quiet" | "normal" | "verbose";
}

export function ChatViewPanels({
  chatView,
  setChatView,
  showHelpModal,
  setShowHelpModal,
}: {
  chatView: string;
  embeddedAction: unknown;
  selectedCli: CliId;
  configs: FloatingChatConfig[];
  isRunning: boolean;
  cliProcess: FloatingChatCliProcess | null;
  sendMessage: (prompt: string) => void;
  sendRawKey: (input: string) => void;
  uploadFile: (file: File) => void;
  setTerminalFallbackActive: (active: boolean) => void;
  setChatView: (
    view: "chat" | "terminal" | "action-dialog" | "actions-list",
  ) => void;
  startCli: (cliId: CliId, options?: StartCliOptions) => Promise<void> | void;
  switchCli: (cliId: CliId) => Promise<void> | void;
  stopCli: (cliId: CliId) => Promise<void> | void;
  sendToIde: (prompt: string) => void;
  setEmbeddedAction: (action: any) => void;
  showHelpModal: boolean;
  setShowHelpModal: (show: boolean) => void;
  isOperationMode: boolean;
}) {
  return (
    <>
      {chatView === "actions-list" && (
        <ActionsListView onBack={() => setChatView("terminal")} />
      )}
      {showHelpModal && (
        <HelpRequestModal onClose={() => setShowHelpModal(false)} />
      )}
    </>
  );
}
