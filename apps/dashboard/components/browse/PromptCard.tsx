"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play } from "lucide-react";

import ResultCard from "@/components/browse/ResultCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";
import { extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";
import type { PromptResult, SkillPrompt } from "@/lib/browse/types";

interface PromptCardProps {
  prompt: SkillPrompt;
  onResult: (result: PromptResult) => void;
}

function createInitialValues(variables: string[]): Record<string, string> {
  return variables.reduce<Record<string, string>>((acc, variable) => {
    acc[variable] = "";
    return acc;
  }, {});
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

export function PromptCard(props: PromptCardProps) {
  return <PromptCardInner key={`${props.prompt.id}:${props.prompt.prompt}`} {...props} />;
}

function PromptCardInner({ prompt, onResult }: PromptCardProps) {
  const variables = useMemo(
    () => extractVariables(prompt.prompt),
    [prompt.prompt],
  );
  const initialValues = useMemo(
    () => createInitialValues(variables),
    [variables],
  );

  const [values, setValues] = useState<Record<string, string>>(initialValues);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PromptResult | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

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

  const resolvedPrompt = useMemo(
    () => resolvePromptBody(prompt.prompt, values),
    [prompt.prompt, values],
  );
  const canRun =
    !isRunning && variables.every((variable) => values[variable]?.trim());

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
            : "Prompt execution failed.",
        );
        cleanupStream();
        return;
      }

      if (!isDonePayload(payload)) {
        return;
      }

      const nextResult: PromptResult = {
        promptId: prompt.id,
        input: resolvedPrompt,
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
      onResult(nextResult);
    },
    [cleanupStream, onResult, prompt.id, resolvedPrompt],
  );

  const handleStreamError = useCallback(() => {
    setError("Prompt execution failed.");
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
        body: JSON.stringify({ prompt: resolvedPrompt }),
        signal: controller.signal,
      });

      const isCurrentRun = () =>
        runIdRef.current === runId && !controller.signal.aborted;

      if (!isCurrentRun()) {
        return;
      }

      if (!response.ok) {
        let message = `Prompt execution failed (${response.status}).`;
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
          // Fall back to the status-based message.
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
        setError("Prompt execution did not return an exec id.");
        cleanupStream();
        return;
      }

      const eventSource = new EventSource(
        `/api/cli/exec/stream?id=${encodeURIComponent(payload.execId)}`,
      );
      eventSourceRef.current = eventSource;
      eventSource.addEventListener("message", (event) => {
        if (runIdRef.current !== runId) {
          return;
        }
        handleMessage(event);
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
        error instanceof Error ? error.message : "Prompt execution failed.",
      );
      cleanupStream();
    }
  }, [canRun, cleanupStream, handleMessage, handleStreamError, resolvedPrompt]);

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {prompt.label}
          </h3>
          {prompt.description ? (
            <p className="text-xs text-[var(--text-muted)]">
              {prompt.description}
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

      {variables.length > 0 ? (
        <div
          className={cn(
            "mt-4 grid gap-3",
            variables.length > 1 ? "sm:grid-cols-2" : "grid-cols-1",
          )}
        >
          {variables.map((variable) => (
            <label key={variable} className="space-y-1">
              <span className="text-xs font-medium text-[var(--text-secondary)]">
                {variable}
              </span>
              <Input
                aria-label={variable}
                value={values[variable] ?? ""}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setValues((current) => ({
                    ...current,
                    [variable]: nextValue,
                  }));
                }}
                disabled={isRunning}
                placeholder={`Enter ${variable}`}
                required
              />
            </label>
          ))}
        </div>
      ) : null}

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
