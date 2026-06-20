/**
 * @jest-environment node
 */

import {
  EXEC_STREAM_CANCEL_CLEANUP_MS,
  EXEC_STREAM_TIMEOUT_MS,
  GET,
} from "@/app/api/cli/exec/stream/route";
import { execStore, type ExecEntry } from "@/app/api/cli/exec/exec-store";

function makeEntry(overrides: Partial<ExecEntry> = {}): ExecEntry {
  return {
    prompt: "Summarize this",
    cliId: "claude",
    startedAt: Date.now(),
    output: [],
    done: false,
    answer: null,
    sessionId: null,
    error: null,
    cleanupTimer: null,
    ...overrides,
  };
}

async function readSsePayload(response: Response): Promise<Record<string, unknown>> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("missing response body");
  const { value } = await reader.read();
  const text = new TextDecoder().decode(value);
  const json = text.replace(/^data: /, "").trim();
  return JSON.parse(json) as Record<string, unknown>;
}

describe("GET /api/cli/exec/stream", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  it("returns 400 when id is missing", async () => {
    const response = await GET(new Request("http://localhost/api/cli/exec/stream") as never);

    expect(response.status).toBe(400);
  });

  it("emits done payload and deletes completed entries", async () => {
    const execId = "exec-stream-done";
    execStore.set(execId, makeEntry({
      done: true,
      answer: "Final answer",
      sessionId: "sess-1",
    }));

    const response = await GET(
      new Request(`http://localhost/api/cli/exec/stream?id=${execId}`) as never,
    );
    const payload = await readSsePayload(response);

    expect(payload).toMatchObject({
      type: "done",
      answer: "Final answer",
      sessionId: "sess-1",
      cliId: "claude",
    });
    expect(execStore.get(execId)).toBeUndefined();
  });

  it("emits error payload and deletes failed entries", async () => {
    const execId = "exec-stream-error";
    execStore.set(execId, makeEntry({
      done: true,
      error: "CLI exited with code 1",
    }));

    const response = await GET(
      new Request(`http://localhost/api/cli/exec/stream?id=${execId}`) as never,
    );
    const payload = await readSsePayload(response);

    expect(payload).toMatchObject({
      type: "error",
      error: "CLI exited with code 1",
      cliId: "claude",
    });
    expect(execStore.get(execId)).toBeUndefined();
  });

  it("kills and deletes running entries on timeout", async () => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date("2026-04-20T10:00:00Z").getTime());
    const execId = "exec-stream-timeout";
    const kill = jest.fn();
    execStore.set(execId, makeEntry({
      kill,
      startedAt: Date.now() - EXEC_STREAM_TIMEOUT_MS - 1,
    }));

    const response = await GET(
      new Request(`http://localhost/api/cli/exec/stream?id=${execId}`) as never,
    );
    const payload = await readSsePayload(response);

    expect(payload).toEqual({ type: "error", error: "timeout" });
    expect(kill).toHaveBeenCalled();
    expect(execStore.get(execId)).toBeUndefined();
  });

  it("schedules bounded cleanup when a stream is cancelled before completion", async () => {
    jest.useFakeTimers();
    const execId = "exec-stream-cancel";
    const kill = jest.fn();
    execStore.set(execId, makeEntry({ kill }));

    const response = await GET(
      new Request(`http://localhost/api/cli/exec/stream?id=${execId}`) as never,
    );
    const reader = response.body?.getReader();
    if (!reader) throw new Error("missing response body");

    await reader.read();
    await reader.cancel();
    expect(execStore.get(execId)).toBeDefined();

    jest.advanceTimersByTime(EXEC_STREAM_CANCEL_CLEANUP_MS);

    expect(kill).toHaveBeenCalled();
    expect(execStore.get(execId)).toBeUndefined();
  });
});
