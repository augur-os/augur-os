import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { safeJson } from "@/lib/safe-json";

export interface IdeStatus {
  active_ide: string | null;
  available_ides: string[];
}

export interface IdeHistoryItem {
  timestamp: string;
  prompt: string;
  ide: string;
  success: boolean;
  error?: string;
}

type UseIdeBridgeOptions = {
  pollStatus?: boolean;
  pollIntervalMs?: number;
};

function isTransientFetchError(error: unknown): boolean {
  if (!error) return false;
  if (error instanceof DOMException && error.name === "AbortError") return true;
  if (error instanceof TypeError && /Failed to fetch/i.test(error.message))
    return true;
  return /AbortError|Failed to fetch/i.test(String(error));
}

export function useIdeBridge({
  pollStatus = false,
  pollIntervalMs = 30000,
}: UseIdeBridgeOptions = {}) {
  const [status, setStatus] = useState<IdeStatus>({
    active_ide: null,
    available_ides: [],
  });
  const [history, setHistory] = useState<IdeHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await fetch("/api/ide/status", { cache: "no-store", signal });
      const data = await safeJson<{
        success?: boolean;
        active_ide?: string;
        available_ides?: string[];
      }>(res);
      if (!data) return;
      if (data.success) {
        setStatus({
          active_ide: data.active_ide ?? null,
          available_ides: data.available_ides || [],
        });
      }
    } catch (e) {
      if (isTransientFetchError(e)) return;
      console.error("Failed to fetch IDE status", e);
    }
  }, []);

  // INTENTIONAL_SKIP(adr-269): interval-based IDE status poll — custom polling with setInterval, not a simple mount-time GET
  useEffect(() => {
    const controller = new AbortController();
    if (!pollStatus) {
      return () => {
        controller.abort();
      };
    }

    const timer = window.setTimeout(() => {
      void fetchStatus(controller.signal);
    }, 0);
    const interval = setInterval(() => fetchStatus(controller.signal), pollIntervalMs);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      clearInterval(interval);
    };
  }, [fetchStatus, pollStatus, pollIntervalMs]);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/ide/history", { cache: "no-store" });
      const data = await safeJson<{
        success?: boolean;
        history?: IdeHistoryItem[];
      }>(res);
      if (!data) return;
      if (data.success) {
        setHistory(data.history ?? []);
      }
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
  };

  // INTENTIONAL_SKIP(adr-269): POST mutation — sends prompt to IDE, not a REST GET
  const sendPrompt = async (prompt: string, ide?: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/ide/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, ide }),
      });
      const data = await res.json();

      if (data.success) {
        toast.success(`Sent to ${data.ide || "IDE"}`);
      } else {
        toast.error(`Failed: ${data.error}`);
      }
      return data;
    } catch (e) {
      toast.error("Failed to communicate with IDE Bridge");
      return { success: false, error: String(e) };
    } finally {
      setLoading(false);
      // Refresh history if we verify it later
    }
  };

  return {
    status,
    history,
    loading,
    fetchStatus,
    fetchHistory,
    sendPrompt,
  };
}
