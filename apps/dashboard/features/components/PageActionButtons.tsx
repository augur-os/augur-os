"use client";

import { useEffect, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { useMcpHealth } from "@/hooks/useMcpHealth";
import { useModeStore } from "@/lib/stores/modeStore";
import { useChatStore } from "@/lib/stores/chatStore";

interface PageActionButtonsProps {
  tab?: string;
  className?: string;
}

function subscribeToHydration(onStoreChange: () => void) {
  queueMicrotask(onStoreChange);
  return () => {};
}

function getClientHydrationSnapshot() {
  return true;
}

function getServerHydrationSnapshot() {
  return false;
}

function getLauncherStatusClasses({
  isHealthy,
  hasProblems,
}: {
  isHealthy: boolean;
  hasProblems: boolean;
}) {
  if (hasProblems) {
    return "bg-[var(--bg-card)]/92 text-red-400 ring-1 ring-red-400/50 shadow-[0_6px_16px_rgba(15,23,42,0.1),0_0_12px_rgba(248,113,113,0.12)]";
  }
  if (isHealthy) {
    return "bg-[var(--bg-card)]/92 text-emerald-500 ring-1 ring-emerald-400/50 shadow-[0_6px_16px_rgba(15,23,42,0.1),0_0_12px_rgba(52,211,153,0.12)]";
  }
  return "bg-[var(--bg-card)]/92 text-[var(--text-primary)] shadow-[0_6px_16px_rgba(15,23,42,0.1)]";
}

function ChatLauncherButton() {
  const chatStore = useChatStore();
  const { data, hasIssues, isLoading } = useMcpHealth({
    enablePolling: true,
    showToasts: false,
  });

  if (chatStore.isOpen) {
    return null;
  }

  const hasProblems =
    hasIssues || Boolean(data?.staleMcpConfig) || Boolean(data?.migrationInProgress);
  const isHealthy = !isLoading && !hasProblems;
  const title = hasProblems ? "Open chat (system issues detected)" : "Open chat";

  return (
    <button
      type="button"
      data-testid="collapsed-chat-launcher"
      data-status={hasProblems ? "error" : isHealthy ? "healthy" : "idle"}
      className={`flex h-12 w-12 items-center justify-center rounded-full border border-[var(--border-color)]/70 backdrop-blur-xl transition-all duration-200 hover:scale-105 active:scale-95 ${getLauncherStatusClasses({
        isHealthy,
        hasProblems,
      })}`}
      onClick={() => chatStore.openChat({ mode: "ide" })}
      aria-label="Open chat"
      title={title}
    >
      <MessageSquare className="size-5" />
      <span className="sr-only">Chat</span>
    </button>
  );
}

export default function PageActionButtons({
  tab: _tab,
  className = "",
}: PageActionButtonsProps) {
  const chatStore = useChatStore();
  const { mode, toggleMode } = useModeStore();
  const isMounted = useSyncExternalStore(
    subscribeToHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );

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

  if (!isMounted || typeof document === "undefined" || chatStore.isOpen) {
    return null;
  }

  const launcher = (
    <div
      className={`floating-action-bar fixed bottom-6 right-6 z-[90] hidden pointer-events-auto !border-0 !bg-transparent !shadow-none transition-all duration-300 ease-out md:flex ${className}`}
    >
      <ChatLauncherButton />
    </div>
  );

  return createPortal(launcher, document.body);
}
