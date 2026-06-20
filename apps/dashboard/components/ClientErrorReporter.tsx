"use client";

import { useEffect } from "react";
import { emitClientError } from "@/lib/self-heal-event";

const BATCH_INTERVAL_MS = 5_000;
const MAX_PER_BATCH = 5;
const MAX_UNIQUE_PER_SESSION = 50;
const DEDUP_WINDOW_MS = 60_000;
const FLUSH_KEY = "__augur_error_reporter_flush";

interface ErrorEntry {
  level: "error" | "warning";
  message: string;
  source: string;
  url: string;
  stack?: string;
  component?: string;
  timestamp: string;
  fingerprint: string;
  count: number;
}

function fingerprint(message: string, source?: string, line?: number): string {
  const key = `${(message || "").slice(0, 200)}|${source || ""}|${line || 0}`;
  // Simple hash to keep fingerprints short
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0;
  }
  return String(Math.abs(hash));
}

// Known noise patterns to ignore
const IGNORE_PATTERNS = [
  "ResizeObserver loop",
  "ResizeObserver loop completed with undelivered notifications",
  // React StrictMode double-render in dev
  "findDOMNode is deprecated",
];

function shouldIgnore(message: string): boolean {
  return IGNORE_PATTERNS.some((p) => message.includes(p));
}

export default function ClientErrorReporter() {
  useEffect(() => {
    const pending = new Map<string, ErrorEntry>();
    const seen = new Set<string>();
    let timer: ReturnType<typeof setInterval> | null = null;

    function flush() {
      if (pending.size === 0) return;
      const batch = Array.from(pending.values()).slice(0, MAX_PER_BATCH);
      pending.clear();

      for (const entry of batch) {
        emitClientError(entry);
      }
    }

    function record(entry: Omit<ErrorEntry, "timestamp" | "count">) {
      if (seen.size >= MAX_UNIQUE_PER_SESSION) return;
      if (shouldIgnore(entry.message)) return;

      const fp = entry.fingerprint;

      // Dedup within window
      const existing = pending.get(fp);
      if (existing) {
        existing.count++;
        return;
      }

      if (seen.has(fp)) return;
      seen.add(fp);

      // Auto-expire from dedup set after window
      setTimeout(() => seen.delete(fp), DEDUP_WINDOW_MS);

      pending.set(fp, {
        ...entry,
        timestamp: new Date().toISOString(),
        count: 1,
      });
    }

    // 1. Intercept console.error
    const originalError = console.error;
    console.error = (...args: unknown[]) => {
      originalError.apply(console, args);
      try {
        const message = args
          .map((a) =>
            typeof a === "string"
              ? a
              : a instanceof Error
                ? a.message
                : String(a),
          )
          .join(" ");

        record({
          level: "error",
          message: message.slice(0, 500),
          source: "console.error",
          url: window.location.pathname,
          stack: args.find((a) => a instanceof Error)
            ? (args.find((a) => a instanceof Error) as Error).stack?.slice(
                0,
                1000,
              )
            : undefined,
          fingerprint: fingerprint(message),
        });
      } catch {
        // Never throw from the error reporter
      }
    };

    // 2. window.onerror
    const onError = (
      event: string | Event,
      source?: string,
      lineno?: number,
      _colno?: number,
      error?: Error,
    ) => {
      const message = error?.message || String(event);
      record({
        level: "error",
        message: message.slice(0, 500),
        source: "window.onerror",
        url: window.location.pathname,
        stack: error?.stack?.slice(0, 1000),
        fingerprint: fingerprint(message, source, lineno),
      });
    };
    window.onerror = onError;

    // 3. Unhandled promise rejections
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message =
        reason instanceof Error
          ? reason.message
          : String(reason || "Unhandled rejection");
      record({
        level: "error",
        message: message.slice(0, 500),
        source: "unhandledrejection",
        url: window.location.pathname,
        stack:
          reason instanceof Error ? reason.stack?.slice(0, 1000) : undefined,
        fingerprint: fingerprint(message),
      });
    };
    window.addEventListener("unhandledrejection", onRejection);

    // Start batch flush timer (globalThis guard prevents HMR interval leak)
    if (!(globalThis as any)[FLUSH_KEY]) {
      (globalThis as any)[FLUSH_KEY] = setInterval(flush, BATCH_INTERVAL_MS);
    }
    timer = (globalThis as any)[FLUSH_KEY];

    return () => {
      console.error = originalError;
      window.onerror = null;
      window.removeEventListener("unhandledrejection", onRejection);
      if (timer) {
        clearInterval(timer);
        delete (globalThis as any)[FLUSH_KEY];
      }
      flush(); // Flush remaining on unmount
    };
  }, []);

  return null;
}
