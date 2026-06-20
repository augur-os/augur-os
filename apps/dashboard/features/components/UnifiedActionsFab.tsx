"use client";

import { MessageSquare, Terminal } from "lucide-react";
import { useChatStore } from "@/lib/stores/chatStore";

/**
 * Minimal FAB - Chat button only.
 * All other dev tools have been moved to PageActionButtons (Dev Tools dropdown).
 * ADR-035: When CLI is running, icon switches to Terminal + ring glow to indicate active session.
 * Differentiated from the action bar "Active" dot by using icon swap + ring instead of a green dot.
 */
export default function UnifiedActionsFab() {
  const chatStore = useChatStore();
  const isCliRunning = chatStore.cliProcess?.status === "running";

  // ADR-035: Hide FAB when FloatingChat is open to avoid overlapping buttons
  if (chatStore.isOpen) return null;

  const openIdeChat = () => {
    chatStore.openChat({ mode: "ide" });
    window.dispatchEvent(new CustomEvent("show-action-bar"));
  };

  return (
    <button type="button"
      onClick={openIdeChat}
      className={`fixed right-16 top-2.5 z-[45] flex h-9 w-9 items-center justify-center rounded-full shadow-lg transition-all hover:scale-105 active:scale-95 md:hidden bg-[var(--accent-info)] text-[var(--accent-foreground,white)] ${
        isCliRunning
          ? "ring-2 ring-emerald-400/60 shadow-emerald-500/30"
          : "shadow-[var(--accent-info)]/20"
      }`}
      aria-label={isCliRunning ? "Open terminal" : "Open chat"}
      title={isCliRunning ? "Terminal (CLI running)" : "Chat (opens IDE chat)"}
    >
      {isCliRunning ? (
        <Terminal className="size-4" />
      ) : (
        <MessageSquare className="size-4" />
      )}
    </button>
  );
}
