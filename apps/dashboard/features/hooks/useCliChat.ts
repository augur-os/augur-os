import { useCallback, useEffect, useState, useRef } from "react";
import { usePathname } from "next/navigation";
import {
  useChatStore,
  type CliId,
  type AttachedFile,
} from "@/lib/stores/chatStore";
import { safeJson } from "@/lib/safe-json";
import { resolveContext } from "@/lib/chat/context-envelope";
import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";
import {
  SAVE_DEBOUNCE_MS,
  type CliConfig,
  type ChatMessage,
} from "./useCliChat.types";
import {
  loadStoredMessages,
  saveMessagesToStorage,
  clearStoredMessages,
  buildStartErrorMessage,
  isTransientConfigFetchError,
  isNonRetriableStatus,
  shouldRetry,
} from "./useCliChat.helpers";

export type {
  CliConfig,
  ChatMessage,
  SessionConflictInfo,
} from "./useCliChat.types";
import { type SessionConflictInfo } from "./useCliChat.types";

async function waitForRetry(attempt: number): Promise<void> {
  const delayMs = 1000 * 2 ** attempt;
  await new Promise((resolve) => setTimeout(resolve, delayMs));
}

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  maxRetries = 3,
): Promise<Response> {
  return fetchWithRetryAttempt(url, options, maxRetries, 0, null);
}

async function fetchWithRetryAttempt(
  url: string,
  options: RequestInit,
  maxRetries: number,
  attempt: number,
  lastError: Error | null,
): Promise<Response> {
  if (attempt >= maxRetries) {
    throw lastError ?? new Error("fetchWithRetry failed");
  }

  try {
    const res = await fetch(url, options);
    if (res.ok || isNonRetriableStatus(res.status)) {
      return res;
    }
    const nextError = new Error(`HTTP ${res.status}`);
    if (shouldRetry(attempt, maxRetries)) await waitForRetry(attempt);
    return fetchWithRetryAttempt(url, options, maxRetries, attempt + 1, nextError);
  } catch (err) {
    const nextError = err instanceof Error ? err : new Error(String(err));
    if (shouldRetry(attempt, maxRetries)) await waitForRetry(attempt);
    return fetchWithRetryAttempt(url, options, maxRetries, attempt + 1, nextError);
  }
}

async function fetchCurrentCliConfigs(shouldIgnore?: () => boolean): Promise<{
  configs?: CliConfig[];
  default_cli?: string;
} | null> {
  const res = await fetch("/api/cli/configs");
  const data = await safeJson<{
    configs?: CliConfig[];
    default_cli?: string;
  }>(res);
  return shouldIgnore?.() ? null : data;
}

/**
 * Manages CLI process lifecycle, system messages, and file attachments.
 *
 * NOTE: Terminal output rendering is handled separately by useXtermTerminal
 * which connects directly to the raw SSE endpoint. This hook only manages
 * process control (start/stop/send) and system-level messages.
 */
export function useCliChat() {
  const pathname = usePathname();
  const {
    selectedCli,
    cliProcess,
    attachedFiles,
    sessionId,
    setSelectedCli,
    setCliProcess,
    addAttachedFile,
    removeAttachedFile,
    clearAttachedFiles,
  } = useChatStore();
  const { airplaneMode, airplaneModeReady, airplaneLocalModel } =
    useAirplaneModeStore();

  // ADR-535: Restore messages from localStorage on mount
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadStoredMessages());
  const [configs, setConfigs] = useState<CliConfig[]>([]);
  const [sessionConflict, setSessionConflict] =
    useState<SessionConflictInfo | null>(null);

  const recordSessionConflict = useCallback((data: any) => {
    setSessionConflict({
      sessionId:
        typeof data?.sessionId === "string" ? data.sessionId : undefined,
      owner:
        data?.owner && typeof data.owner === "object"
          ? data.owner
          : undefined,
    });
  }, []);

  // ADR-116 Phase 3B: Rate limiting for sendMessage
  const lastSendRef = useRef<number>(0);

  /**
   * ADR-116 Phase 3B: Persist a message to the session JSONL.
   */
  // INTENTIONAL_SKIP(adr-269): fire-and-forget POST — message persistence, not a REST GET
  const persistMessage = useCallback(
    (message: ChatMessage) => {
      if (!sessionId) return;

      fetch("/api/chat/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          message: {
            id: crypto.randomUUID(),
            role: message.role,
            content: message.content,
            timestamp: message.timestamp,
          },
        }),
      }).catch(() => {}); // Non-critical
    },
    [sessionId],
  );

  /**
   * ADR-116 Phase 3B: Load session from JSONL if it exists.
   */
  const loadSession = useCallback(async (sid: string) => {
    try {
      const res = await fetch(`/api/chat/messages?sessionId=${sid}`);
      const data = await safeJson<any>(res);
      if (data && data.messages?.length > 0) {
        setMessages(data.messages);
      }
    } catch {
      // Non-critical: session recovery failure doesn't prevent new messages
    }
  }, []);

  const fetchConfigs = useCallback(
    async (shouldIgnore?: () => boolean) => {
      try {
        if (shouldIgnore?.()) return;
        const data = await fetchCurrentCliConfigs(shouldIgnore);
        if (!data) return;
        if (data.configs) {
          setConfigs(data.configs);
        }
        if (data.default_cli) {
          setSelectedCli(data.default_cli as CliId);
        }
      } catch (err) {
        if (isTransientConfigFetchError(err)) return;
        console.error("Failed to fetch CLI configs:", err);
      }
    },
    [setSelectedCli],
  );

  // Fetch available CLI configs on mount
  useEffect(() => {
    let ignore = false;
    const timer = window.setTimeout(() => {
      void fetchConfigs(() => ignore);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      ignore = true;
    };
  }, [fetchConfigs]);

  // ADR-116 Phase 3B: Load session on mount if sessionId exists
  useEffect(() => {
    if (sessionId) {
      const timer = window.setTimeout(() => {
        void loadSession(sessionId);
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [sessionId, loadSession]);

  const previousAirplaneRouteRef = useRef<{
    enabled: boolean;
    model: string | null;
  } | null>(null);
  useEffect(() => {
    if (!airplaneModeReady) return;

    const currentRoute = {
      enabled: airplaneMode,
      model: airplaneMode ? airplaneLocalModel : null,
    };
    if (previousAirplaneRouteRef.current === null) {
      previousAirplaneRouteRef.current = currentRoute;
      return;
    }

    const previousRoute = previousAirplaneRouteRef.current;
    if (
      previousRoute.enabled === currentRoute.enabled &&
      previousRoute.model === currentRoute.model
    ) {
      return;
    }
    previousAirplaneRouteRef.current = currentRoute;

    if (!cliProcess || cliProcess.status !== "running") return;

    // Toggling the airplane preference does NOT relaunch an in-progress chat —
    // the running process keeps the backend it was started with. Say the
    // preference changed and that a restart is needed, instead of falsely
    // claiming the session switched.
    const target = airplaneMode
      ? `local model${currentRoute.model ? ` (${currentRoute.model})` : ""}`
      : "cloud";
    const content =
      previousRoute.enabled === currentRoute.enabled && currentRoute.enabled
        ? `Airplane local model preference set to ${currentRoute.model ?? "local model"}. This chat keeps its current backend — restart it (Stop then Start) to apply.`
        : `Airplane mode ${airplaneMode ? "ON" : "OFF"} — new chats will use ${target}. This chat keeps its current backend; restart it (Stop then Start) to apply.`;

    const transitionMsg = {
      role: "system" as const,
      content,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, transitionMsg]);
    persistMessage(transitionMsg);
  }, [
    airplaneMode,
    airplaneModeReady,
    airplaneLocalModel,
    cliProcess,
    persistMessage,
  ]);

  // ---------------------------------------------------------------------------
  // ADR-535: Debounced localStorage auto-save
  // ---------------------------------------------------------------------------

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesRef = useRef(messages);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Debounced save: writes to localStorage 1s after last message change
  useEffect(() => {
    if (messages.length === 0) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(() => {
      saveMessagesToStorage(messagesRef.current, selectedCli);
    }, SAVE_DEBOUNCE_MS);

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [messages, selectedCli]);

  // Immediate save on beforeunload (page refresh/close) and component unmount
  const saveCurrentMessages = useCallback(() => {
    if (messagesRef.current.length > 0) {
      saveMessagesToStorage(messagesRef.current, selectedCli);
    }
  }, [selectedCli]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      // Bypass debounce — save immediately
      saveCurrentMessages();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      // Also save on unmount
      saveCurrentMessages();
    };
  }, [saveCurrentMessages]);

  const startCli = useCallback(
    async (
      cliId: CliId,
      options?: {
        airplaneMode?: boolean;
        themeMode?: "light" | "dark";
        autoContext?: boolean;
        verbosity?: "quiet" | "normal" | "verbose";
        takeOverSessionOwner?: boolean;
        // ADR-748 follow-up: prompt to inject server-side after the CLI is ready
        // (avoids the client readiness race). See app/api/cli/actions.ts.
        oneshotPrompt?: string;
      },
    ) => {
      try {
        setCliProcess({ cliId, status: "waiting" });

        // ADR-161: Resolve context envelope for enriched session + startup prompt
        let envelope:
          | {
              hub?: string;
              skill?: string | null;
              skillSummary?: string | null;
              skillTools?: string[];
              skillActions?: string[];
            }
          | undefined;
        if (options?.autoContext && pathname) {
          try {
            const resolved = await resolveContext(pathname, "standard");
            envelope = {
              hub: resolved.hub,
              skill: resolved.skill,
              skillSummary: resolved.skillSummary,
              skillTools: resolved.skillTools,
              skillActions: resolved.skillActions,
            };
          } catch {
            // Fallback: continue without envelope — server will use legacy prompt
          }
        }

        const useStartupContext = options?.autoContext === true;
        const res = await fetch("/api/cli", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "start",
            cliId,
            ...(useStartupContext ? { current_page: pathname } : {}),
            airplaneMode: options?.airplaneMode,
            themeMode: options?.themeMode,
            autoContext: options?.autoContext,
            verbosity: options?.verbosity,
            takeOverSessionOwner: options?.takeOverSessionOwner,
            oneshotPrompt: options?.oneshotPrompt,
            envelope,
          }),
        });

        const data = await safeJson<any>(res) || { error: "Unknown error" };

        if (!res.ok) {
          setCliProcess({ cliId, status: "error" });
          if (data?.code === "SESSION_OWNED_ELSEWHERE") {
            recordSessionConflict(data);
          } else {
            setSessionConflict(null);
          }
          const errorMsg = {
            role: "system" as const,
            content: buildStartErrorMessage(cliId, data, res.status),
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, errorMsg]);
          persistMessage(errorMsg);
          return false;
        }

        setSessionConflict(null);
        setCliProcess({ cliId, status: "running", pid: data.pid });
        const startMsg = {
          role: "system" as const,
          content: `Started ${cliId} (PID: ${data.pid})`,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, startMsg]);
        persistMessage(startMsg);

        // Keep page metadata tied to explicit startup-context sessions only.
        // Normal chat starts should not create a hidden page-context prompt path.
        try {
          await fetch("/api/chat/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              isActive: true,
              status: "running",
              context: {
                ...(useStartupContext ? { current_page: pathname } : {}),
                cliId,
                pid: data.pid,
              },
            }),
          });
        } catch {
          // Non-critical: session update failure doesn't affect CLI operation
        }
        return true;
      } catch (err) {
        console.error("Failed to start CLI:", err);
        setCliProcess({ cliId, status: "error" });
        return false;
      }
    },
    [setCliProcess, pathname, persistMessage, recordSessionConflict],
  );

  const stopCli = useCallback(
    async (cliId: CliId) => {
      try {
        await fetch("/api/cli", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "stop", cliId }),
        });

        setCliProcess(null);
        setSessionConflict(null);
        const stopMsg = {
          role: "system" as const,
          content: `Stopped ${cliId}`,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, stopMsg]);
        persistMessage(stopMsg);

        // Clear chat session page context
        try {
          await fetch("/api/chat/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              isActive: false,
              status: "idle",
              context: {},
            }),
          });
        } catch {
          // Non-critical
        }
      } catch (err) {
        console.error("Failed to stop CLI:", err);
      }
    },
    [setCliProcess, persistMessage],
  );

  const switchCli = useCallback(
    async (newCliId: CliId) => {
      // Stop current CLI if running
      if (cliProcess && cliProcess.status === "running") {
        await stopCli(cliProcess.cliId);
      }

      setSelectedCli(newCliId);
      const switchMsg = {
        role: "system" as const,
        content: `Switched to ${newCliId}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, switchMsg]);
      persistMessage(switchMsg);

      // Start the new CLI
      await startCli(newCliId);
    },
    [cliProcess, stopCli, setSelectedCli, startCli, persistMessage],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      // ADR-116 Phase 3B: Rate limiting
      const now = Date.now();
      if (now - lastSendRef.current < 200) {
        return false;
      }
      lastSendRef.current = now;

      if (!cliProcess || cliProcess.status !== "running") {
        const errorMsg = {
          role: "system" as const,
          content: "No CLI running. Select a CLI and start it first.",
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        persistMessage(errorMsg);
        return false;
      }

      // Build input with file attachments
      let input = text;
      if (attachedFiles.length > 0) {
        const filePaths = attachedFiles
          .map((f) => `File attached at ${f.stagedPath}`)
          .join("\n");
        input = `${text}\n\n${filePaths}`;
      }

      // Show attachment info if any
      if (attachedFiles.length > 0) {
        const names = attachedFiles.map((f) => f.originalName).join(", ");
        const attachMsg = {
          role: "system" as const,
          content: `Attached: ${names}`,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, attachMsg]);
        persistMessage(attachMsg);
      }

      // ADR-116 Phase 3B: Persist user message
      const userMsg = { role: "user" as const, content: text, timestamp: now };
      persistMessage(userMsg);

      // Send to CLI stdin
      try {
        const res = await fetchWithRetry(
          "/api/cli",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: "send",
              cliId: cliProcess.cliId,
              input,
            }),
          },
          3,
        );

        if (!res.ok) {
          const data = await safeJson<any>(res) || { error: "Unknown error" };
          const sendErrorMsg = {
            role: "system" as const,
            content: `Send failed: ${data.error}`,
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, sendErrorMsg]);
          persistMessage(sendErrorMsg);
          clearAttachedFiles();
          return false;
        }
      } catch (err) {
        console.error("Failed to send message:", err);
        clearAttachedFiles();
        return false;
      }

      // Clear attachments after sending
      clearAttachedFiles();
      return true;
    },
    [cliProcess, attachedFiles, clearAttachedFiles, persistMessage],
  );

  const uploadFile = useCallback(
    async (file: File) => {
      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("/api/cli/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const data = await safeJson<any>(res) || { error: "Unknown error" };
          const uploadErrorMsg = {
            role: "system" as const,
            content: `Upload failed: ${data.error}`,
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, uploadErrorMsg]);
          persistMessage(uploadErrorMsg);
          return;
        }

        const data = await safeJson<any>(res);
        if (!data) throw new Error("Invalid response from upload API");
        const attached: AttachedFile = {
          originalName: data.originalName,
          stagedPath: data.stagedPath,
          size: data.size,
          mimeType: data.mimeType,
          timestamp: Date.now(),
        };

        addAttachedFile(attached);
      } catch (err) {
        console.error("Failed to upload file:", err);
      }
    },
    [addAttachedFile, persistMessage],
  );

  const sendRawKey = useCallback(
    async (data: string) => {
      if (!cliProcess || cliProcess.status !== "running") return;

      try {
        await fetch("/api/cli", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "sendRaw",
            cliId: cliProcess.cliId,
            data,
          }),
        });
      } catch (err) {
        console.error("Failed to send raw key:", err);
      }
    },
    [cliProcess],
  );

  /**
   * ADR-157 Decision 4: Send a system command to the CLI without showing in chat history.
   * Used for lifecycle events like auto-refocus and context-save.
   */
  const sendSystemCommand = useCallback(
    async (command: string) => {
      if (!cliProcess || cliProcess.status !== "running") return;

      try {
        await fetchWithRetry(
          "/api/cli",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: "system",
              cliId: cliProcess.cliId,
              input: command,
            }),
          },
          2,
        );
      } catch (err) {
        console.error("Failed to send system command:", err);
      }
    },
    [cliProcess],
  );

  const fetchStatus = useCallback(async (cliId: CliId) => {
    try {
      const res = await fetch(`/api/cli?cliId=${cliId}`);
      const data = await safeJson<any>(res);
      return data || { cliId, status: "idle" };
    } catch {
      return { cliId, status: "idle" };
    }
  }, []);

  // ADR-535: Clear both in-memory and persisted messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    clearStoredMessages();
  }, []);

  const clearSessionConflict = useCallback(() => {
    setSessionConflict(null);
  }, []);

  const takeOverSessionConflict = useCallback(async () => {
    const conflictCli =
      typeof sessionConflict?.owner?.cli_id === "string" &&
      sessionConflict.owner.cli_id.trim().length > 0
        ? (sessionConflict.owner.cli_id as CliId)
        : selectedCli;
    await startCli(conflictCli, { takeOverSessionOwner: true });
  }, [sessionConflict, selectedCli, startCli]);

  return {
    // State
    messages,
    configs,
    selectedCli,
    cliProcess,
    attachedFiles,
    sessionConflict,

    // Actions
    startCli,
    stopCli,
    switchCli,
    sendMessage,
    sendRawKey,
    sendSystemCommand,
    uploadFile,
    removeAttachedFile,
    clearAttachedFiles,
    fetchStatus,
    fetchConfigs,
    setMessages,
    clearMessages,
    clearSessionConflict,
    takeOverSessionConflict,
    recordSessionConflict,
  };
}
