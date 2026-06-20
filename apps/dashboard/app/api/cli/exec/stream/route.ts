import { NextRequest } from "next/server";
import { execStore } from "../exec-store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const EXEC_STREAM_POLL_INTERVAL_MS = 100;
export const EXEC_STREAM_TIMEOUT_MS = 120_000;
export const EXEC_STREAM_CANCEL_CLEANUP_MS = 120_000;

export async function GET(request: NextRequest): Promise<Response> {
  const execId = new URL(request.url).searchParams.get("id");
  if (!execId) {
    return new Response("Missing id", { status: 400 });
  }

  const encoder = new TextEncoder();
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (payload: Record<string, unknown>) => {
        if (cancelled) return;
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      };

      const close = () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
        controller.close();
      };

      const clearEntryCleanup = () => {
        const entry = execStore.get(execId);
        if (entry?.cleanupTimer) {
          clearTimeout(entry.cleanupTimer);
          entry.cleanupTimer = null;
        }
      };

      const startedPollingAt = execStore.get(execId)?.startedAt ?? Date.now();
      clearEntryCleanup();

      const poll = () => {
        const entry = execStore.get(execId);
        if (!entry) {
          send({ type: "error", error: "exec not found" });
          close();
          return;
        }

        if (Date.now() - startedPollingAt > EXEC_STREAM_TIMEOUT_MS) {
          send({ type: "error", error: "timeout" });
          try {
            entry.kill?.();
          } catch {
            // Best effort: the process may already have exited.
          }
          execStore.delete(execId);
          close();
          return;
        }

        if (entry.done) {
          if (entry.error) {
            send({
              type: "error",
              error: entry.error,
              durationMs: Date.now() - entry.startedAt,
              cliId: entry.cliId,
            });
            execStore.delete(execId);
            close();
            return;
          }

          send({
            type: "done",
            answer: entry.answer ?? "",
            sessionId: entry.sessionId ?? "",
            durationMs: Date.now() - entry.startedAt,
            cliId: entry.cliId,
            ...(entry.error ? { error: entry.error } : {}),
          });
          execStore.delete(execId);
          close();
          return;
        }

        send({ type: "running" });
        timer = setTimeout(poll, EXEC_STREAM_POLL_INTERVAL_MS);
      };

      poll();
    },

    cancel() {
      cancelled = true;
      if (timer) clearTimeout(timer);
      const entry = execStore.get(execId);
      if (!entry || entry.cleanupTimer) return;
      entry.cleanupTimer = setTimeout(() => {
        const latest = execStore.get(execId);
        if (!latest) return;
        try {
          latest.kill?.();
        } catch {
          // Best effort: the process may already have exited.
        }
        execStore.delete(execId);
      }, EXEC_STREAM_CANCEL_CLEANUP_MS);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
