export interface CliExecResult {
  answer: string;
  sessionId?: string;
  cliId?: string;
  durationMs?: number;
}

interface CliExecDonePayload extends CliExecResult {
  type: "done";
}

interface CliExecErrorPayload {
  type: "error";
  error?: string;
}

interface CliExecStartPayload {
  execId?: string;
  error?: string;
}

interface RunCliExecPromptOptions {
  signal?: AbortSignal;
  onStream?: (source: EventSource) => void;
  onStreamClose?: (source: EventSource) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDonePayload(value: unknown): value is CliExecDonePayload {
  return isRecord(value) && value.type === "done" && typeof value.answer === "string";
}

function isErrorPayload(value: unknown): value is CliExecErrorPayload {
  return isRecord(value) && value.type === "error";
}

function abortError(): DOMException {
  return new DOMException("CLI execution aborted.", "AbortError");
}

async function parseErrorResponse(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as CliExecStartPayload;
    if (payload.error) return payload.error;
  } catch {
    // Fall through to status-based message.
  }
  return `CLI execution failed (${response.status}).`;
}

export async function runCliExecPrompt(
  prompt: string,
  options: RunCliExecPromptOptions = {},
): Promise<CliExecResult> {
  const response = await fetch("/api/cli/exec", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }

  const payload = (await response.json()) as CliExecStartPayload;
  if (!payload.execId) {
    throw new Error(payload.error || "CLI execution did not return an exec id.");
  }

  if (options.signal?.aborted) {
    throw abortError();
  }

  return new Promise<CliExecResult>((resolve, reject) => {
    const source = new EventSource(
      `/api/cli/exec/stream?id=${encodeURIComponent(payload.execId ?? "")}`,
    );
    let settled = false;

    const cleanup = () => {
      source.close();
      options.signal?.removeEventListener("abort", onAbort);
      options.onStreamClose?.(source);
    };

    const settleSuccess = (value: CliExecResult) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(value);
    };

    const settleError = (error: Error | DOMException) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };

    const onAbort = () => settleError(abortError());

    options.onStream?.(source);
    options.signal?.addEventListener("abort", onAbort, { once: true });

    source.addEventListener("message", (event) => {
      let message: unknown;
      try {
        message = JSON.parse(event.data as string) as unknown;
      } catch {
        settleError(new Error("Failed to read CLI execution stream."));
        return;
      }

      if (isErrorPayload(message)) {
        settleError(new Error(message.error || "CLI execution failed."));
        return;
      }

      if (isDonePayload(message)) {
        settleSuccess({
          answer: message.answer,
          sessionId: message.sessionId,
          cliId: message.cliId,
          durationMs: message.durationMs,
        });
      }
    });

    source.addEventListener("error", () => {
      settleError(new Error("CLI execution stream failed."));
    });
  });
}
