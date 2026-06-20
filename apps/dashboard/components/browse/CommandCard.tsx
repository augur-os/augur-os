"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play } from "lucide-react";

import ResultCard from "@/components/browse/ResultCard";
import { Button } from "@/components/ui/Button";
import type { PromptResult, SkillCommand } from "@/lib/browse/types";

interface CommandCardProps {
  command: SkillCommand;
  onResult?: (result: PromptResult) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDonePayload(
  value: unknown,
): value is {
  type: "done";
  answer: string;
  sessionId?: string;
  cliId?: string;
  durationMs?: number;
} {
  return (
    isRecord(value) &&
    value.type === "done" &&
    typeof value.answer === "string"
  );
}

function isErrorPayload(
  value: unknown,
): value is {
  type: "error";
  error?: string;
} {
  return isRecord(value) && value.type === "error";
}

async function readCurrentJson<T>(
  response: Response,
  isCurrentRun: () => boolean,
): Promise<T | null> {
  const payload = (await response.json()) as T;
  return isCurrentRun() ? payload : null;
}

export function CommandCard(props: CommandCardProps) {
  return <CommandCardInner key={props.command.id} {...props} />;
}

function CommandCardInner({ command, onResult }: CommandCardProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PromptResult | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  const commandBody = useMemo(() => command.command, [command.command]);
  const canRun = !isRunning && commandBody.trim().length > 0;

  useEffect(
    () => () => {
      runIdRef.current += 1;

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    },
    [],
  );

  const cleanupStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setIsRunning(false);
  }, []);

  const dispatchContinueInSession = useCallback((sessionId: string) => {
    window.dispatchEvent(
      new CustomEvent("augur:continue-in-session", {
        detail: {
          sessionId,
          answer: result?.answer ?? "",
        },
      }),
    );
  }, [result?.answer]);

  const handleMessage = useCallback(
    (event: MessageEvent<string>) => {
      let payload: unknown;

      try {
        payload = JSON.parse(event.data) as unknown;
      } catch {
        setError("Failed to read exec stream.");
        cleanupStream();
        return;
      }

      if (isErrorPayload(payload)) {
        setError(
          typeof payload.error === "string" && payload.error.trim()
            ? payload.error
            : "Command execution failed.",
        );
        cleanupStream();
        return;
      }

      if (!isDonePayload(payload)) {
        return;
      }

      const nextResult: PromptResult = {
        promptId: command.id,
        input: commandBody,
        answer: payload.answer,
        sessionId: payload.sessionId ?? "",
        cliId: payload.cliId ?? "unknown",
        durationMs: payload.durationMs ?? 0,
        timestamp: new Date(),
      };

      setResult(nextResult);
      setError(null);
      setIsRunning(false);
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      onResult?.(nextResult);
    },
    [cleanupStream, command.id, commandBody, onResult],
  );

  const handleStreamError = useCallback(() => {
    setError("Command execution failed.");
    cleanupStream();
  }, [cleanupStream]);

  const handleRun = useCallback(async () => {
    if (!canRun) {
      return;
    }

    const runId = runIdRef.current + 1;
    runIdRef.current = runId;

    cleanupStream();
    setError(null);
    setResult(null);
    setIsRunning(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("/api/cli/exec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: commandBody }),
        signal: controller.signal,
      });

      const isCurrentRun = () =>
        runIdRef.current === runId && !controller.signal.aborted;

      if (!isCurrentRun()) {
        return;
      }

      if (!response.ok) {
        let message = `Command execution failed (${response.status}).`;
        try {
          const payload = await readCurrentJson<{ error?: string }>(
            response,
            isCurrentRun,
          );
          if (!payload) {
            return;
          }
          if (payload?.error) {
            message = payload.error;
          }
        } catch {
          // Keep the status-based message.
        }

        setError(message);
        cleanupStream();
        return;
      }

      if (!isCurrentRun()) {
        return;
      }
      const payload = await readCurrentJson<{ execId?: string }>(
        response,
        isCurrentRun,
      );
      if (!payload) {
        return;
      }

      if (!payload.execId) {
        setError("Command execution did not return an exec id.");
        cleanupStream();
        return;
      }

      const eventSource = new EventSource(
        `/api/cli/exec/stream?id=${encodeURIComponent(payload.execId)}`,
      );
      eventSourceRef.current = eventSource;
      eventSource.addEventListener("message", (streamEvent) => {
        if (runIdRef.current !== runId) {
          return;
        }
        handleMessage(streamEvent);
      });
      eventSource.addEventListener("error", () => {
        if (runIdRef.current !== runId) {
          return;
        }
        handleStreamError();
      });
    } catch (error) {
      if (
        (error as { name?: string } | null)?.name === "AbortError" ||
        runIdRef.current !== runId
      ) {
        return;
      }

      setError(
        error instanceof Error ? error.message : "Command execution failed.",
      );
      cleanupStream();
    }
  }, [canRun, cleanupStream, commandBody, handleMessage, handleStreamError]);

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {command.label}
          </h3>
          {command.description ? (
            <p className="text-xs text-[var(--text-muted)]">
              {command.description}
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="solid"
          size="sm"
          leftIcon={<Play className="size-4" aria-hidden="true" />}
          onClick={() => void handleRun()}
          isLoading={isRunning}
          disabled={!canRun}
        >
          Run
        </Button>
      </div>

      <div className="mt-4 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2">
        <code className="block whitespace-pre-wrap break-all font-mono text-xs text-[var(--text-primary)]">
          {command.command}
        </code>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 px-3 py-2 text-sm text-[var(--accent-danger)]"
        >
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="mt-4">
          <ResultCard
            result={result}
            onContinueInSession={dispatchContinueInSession}
          />
        </div>
      ) : null}
    </article>
  );
}
