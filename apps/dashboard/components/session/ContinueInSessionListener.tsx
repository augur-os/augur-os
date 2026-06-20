"use client";

import { useEffect } from "react";
import { toast } from "sonner";

import { useChatStore, type CliId } from "@/lib/stores/chatStore";

type ContinueInSessionDetail = {
  sessionId?: string;
  answer?: string;
};

type ContinueSessionResponse = {
  ok?: boolean;
  collision?: boolean;
  message?: string;
  error?: string;
  cliId?: string | null;
  pid?: number | null;
};

const EVENT_NAME = "augur:continue-in-session";

function openIdeChat(session?: Pick<ContinueSessionResponse, "cliId" | "pid">): void {
  const chatState = useChatStore.getState();

  if (session?.cliId) {
    const cliId = session.cliId as CliId;
    chatState.setSelectedCli(cliId);
    chatState.setCliProcess({
      cliId,
      status: "running",
      pid: typeof session.pid === "number" ? session.pid : undefined,
    });
  }
  chatState.setChatView("terminal");
  chatState.openChat({ mode: "ide" });
  chatState.setEnlarged(true);
}

async function continueInSession(
  detail: ContinueInSessionDetail,
  force = false,
): Promise<void> {
  try {
    const response = await fetch("/api/session/continue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: detail.sessionId,
        answer: detail.answer,
        force,
      }),
    });

    const data = (await response.json().catch(() => ({}))) as ContinueSessionResponse;

    if (data.collision && !force) {
      toast.warning(data.message || "Session already active", {
        description: "Choose how to continue.",
        action: {
          label: "View current",
          onClick: () => {
            openIdeChat();
          },
        },
        cancel: {
          label: "Replace with new",
          onClick: () => {
            void continueInSession(detail, true);
          },
        },
      });
      return;
    }

    if (!response.ok || data.error) {
      throw new Error(data.error || `Session continue failed (${response.status})`);
    }

    openIdeChat(data);
  } catch (error) {
    toast.error(
      error instanceof Error ? error.message : "Failed to continue session",
    );
  }
}

export default function ContinueInSessionListener() {
  useEffect(() => {
    const handleContinue = (event: Event) => {
      const detail = (event as CustomEvent<ContinueInSessionDetail>).detail;
      void continueInSession(detail ?? {});
    };

    window.addEventListener(EVENT_NAME, handleContinue);
    return () => window.removeEventListener(EVENT_NAME, handleContinue);
  }, []);

  return null;
}
