"use client";

type QueueItem = {
  url: string;
  body: string;
  keepalive: boolean;
};

type EnqueueOptions = {
  delayMs?: number;
  keepalive?: boolean;
};

const REQUEST_TIMEOUT_MS = 3000;
const DEFAULT_DELAY_MS = 1500;

let queue: QueueItem[] = [];
let flushScheduled = false;
let flushInFlight = false;
let delayTimer: number | null = null;

function scheduleFlush(delayMs: number): void {
  if (flushScheduled) {
    return;
  }

  flushScheduled = true;

  delayTimer = window.setTimeout(() => {
    flushScheduled = false;
    delayTimer = null;
    void flushQueue();
  }, Math.max(0, delayMs));
}

async function flushQueue(): Promise<void> {
  if (flushInFlight || queue.length === 0) {
    return;
  }

  flushInFlight = true;
  try {
    await flushNextQueueItem();
  } finally {
    flushInFlight = false;
  }
}

async function flushNextQueueItem(): Promise<void> {
  const next = queue.shift();
  if (!next) {
    return;
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    await fetch(next.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: next.body,
      keepalive: next.keepalive,
      signal: controller.signal,
    });
  } catch {
    // Best-effort analytics should never block interactive work.
  } finally {
    window.clearTimeout(timeout);
  }

  return flushNextQueueItem();
}

export function enqueueBestEffortJson(
  url: string,
  payload: Record<string, unknown>,
  options: EnqueueOptions = {},
): void {
  if (typeof window === "undefined") {
    return;
  }

  if (typeof navigator !== "undefined" && "onLine" in navigator && !navigator.onLine) {
    return;
  }

  queue.push({
    url,
    body: JSON.stringify(payload),
    keepalive: options.keepalive ?? true,
  });

  scheduleFlush(options.delayMs ?? DEFAULT_DELAY_MS);
}

export function __resetBestEffortQueueForTests(): void {
  queue = [];
  flushScheduled = false;
  flushInFlight = false;
  if (delayTimer) {
    window.clearTimeout(delayTimer);
    delayTimer = null;
  }
}
