"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { normalizeArtifactSlug } from "@/lib/artifacts/slug";
import type { ArtifactEntry } from "@/lib/browse/pages-merge";
import { ArtifactChrome } from "./ArtifactChrome";

interface ArtifactMetaResponse {
  found: boolean;
  artifact?: {
    slug: string;
    title: string;
    kind: ArtifactEntry["kind"];
    hub: string;
    tags: string[];
    url: string;
  };
}

// After this many seconds of iframe-level errors, reassure the user.
const REASSURE_AFTER_MS = 3_000;
// Hard cap before we surface a retriable error instead of spinning indefinitely.
const LOAD_TIMEOUT_MS = 45_000;

/** Construct a minimal ArtifactEntry from just the slug, used as the initial
 *  skeleton while meta is loading non-blocking. Optional fields that the chrome
 *  needs (path, url, etc.) are safe-defaulted so the iframe renders immediately.
 */
function skeletonEntry(slug: string): ArtifactEntry {
  return {
    slug,
    title: slug.replace(/-/g, " "),
    kind: "saved",
    hub: "",
    url: "",
    path: "",
    tags: [],
    promoted_at: "",
    created_at: "",
  };
}

type IframeState =
  | { status: "idle" }
  | { status: "loaded" }
  | { status: "error"; message: string };

function ArtifactStatusShell({
  title,
  description,
  tone = "neutral",
  action,
}: {
  title: string;
  description: string;
  tone?: "neutral" | "error";
  action?: ReactNode;
}) {
  return (
    <main className="flex min-h-[100dvh] flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <header className="shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-card)]/90 px-4 py-3 backdrop-blur">
        <Link
          href="/browse?category=pages"
          className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          <ArrowLeft className="size-3.5" />
          Pages
        </Link>
      </header>
      <section className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="max-w-md text-center">
          <div
            className={`mx-auto mb-4 flex size-11 items-center justify-center rounded-full border ${
              tone === "error"
                ? "border-red-500/25 bg-red-500/10 text-red-500"
                : "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)]"
            }`}
          >
            {tone === "error" ? (
              <AlertCircle className="size-5" />
            ) : (
              <Loader2 className="size-5 animate-spin" />
            )}
          </div>
          <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            {description}
          </p>
          {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
        </div>
      </section>
    </main>
  );
}

export function ArtifactRouteClient({ slug }: { slug: string }) {
  const normalized = useMemo(() => normalizeArtifactSlug(slug), [slug]);

  // The artifact entry used by ArtifactChrome. Starts as a slug-derived
  // skeleton so the iframe renders immediately; filled in when meta resolves.
  const [artifact, setArtifact] = useState<ArtifactEntry | null>(null);
  // null = loading/ok; "missing" = 404; string = error message
  const [metaStatus, setMetaStatus] = useState<null | "missing" | string>(null);

  // iframe-level error fallback: only shown when the iframe itself errors.
  const [iframeState, setIframeState] = useState<IframeState>({ status: "idle" });
  // Bumping this re-runs the iframe error fallback (the Retry affordance).
  const [reload, setReload] = useState(0);
  // Seconds the current iframe-error attempt has been pending.
  const [elapsedSec, setElapsedSec] = useState(0);

  // Holds a cancel function for the active ticker + timeout so onIframeLoad can
  // clear them without a stale-closure problem.
  const cancelTimeoutRef = useRef<(() => void) | null>(null);

  const retry = useCallback(() => {
    setIframeState({ status: "idle" });
    setReload((v) => v + 1);
  }, []);

  // Called by ArtifactChrome when the iframe fires its load event (cross-origin
  // sandboxed iframes still fire onLoad, so this is reliable).
  const handleIframeLoad = useCallback(() => {
    cancelTimeoutRef.current?.();
    cancelTimeoutRef.current = null;
    setIframeState({ status: "loaded" });
  }, []);

  // Called by ArtifactChrome when the iframe fires an error event.
  const handleIframeError = useCallback(() => {
    cancelTimeoutRef.current?.();
    cancelTimeoutRef.current = null;
    setIframeState({
      status: "error",
      message: "The artifact could not be loaded.",
    });
  }, []);

  // Step 1: render the iframe skeleton as soon as we have a valid slug.
  useEffect(() => {
    if (!normalized) return;
    setArtifact(skeletonEntry(normalized));
    setMetaStatus(null);
  }, [normalized]);

  // Step 2: fetch metadata non-blocking; fill chrome title/kind/tags when ready.
  useEffect(() => {
    if (!normalized) return;

    const controller = new AbortController();

    void fetch(`/api/artifact/${encodeURIComponent(normalized)}/meta`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (controller.signal.aborted) return;
        if (!res.ok) {
          // Unexpected error: leave the skeleton in place (iframe may still work).
          // A missing artifact is NOT an error here — the meta route returns 200 with
          // found:false so the browser logs no console error on the not-found path.
          return;
        }
        const data = (await res.json()) as ArtifactMetaResponse;
        if (controller.signal.aborted) return;
        if (!data.found || !data.artifact) {
          setMetaStatus("missing");
          return;
        }
        const { slug: s, title, kind, hub, tags, url } = data.artifact;
        setArtifact((prev) =>
          prev
            ? { ...prev, slug: s, title, kind, hub, tags, url }
            : skeletonEntry(s),
        );
      })
      .catch(() => {
        // Fetch aborted or network error: leave the skeleton; iframe may still work.
      });

    return () => {
      controller.abort();
    };
  }, [normalized]);

  // Elapsed ticker + hard timeout — only active while the iframe is still loading
  // (status "idle"). onIframeLoad cancels both via cancelTimeoutRef so a
  // successfully-loaded artifact is never replaced by the error shell.
  useEffect(() => {
    if (iframeState.status !== "idle") return;

    setElapsedSec(0);
    const startedAt = Date.now();
    const ticker = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1_000);
    const timeout = window.setTimeout(() => {
      window.clearInterval(ticker);
      cancelTimeoutRef.current = null;
      setIframeState({
        status: "error",
        message:
          "The artifact did not respond in time. The dashboard MCP bridge may still be warming up.",
      });
    }, LOAD_TIMEOUT_MS);

    // Expose cancellation so handleIframeLoad can clear this timer eagerly.
    cancelTimeoutRef.current = () => {
      window.clearInterval(ticker);
      window.clearTimeout(timeout);
    };

    return () => {
      window.clearInterval(ticker);
      window.clearTimeout(timeout);
      cancelTimeoutRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  if (!normalized) {
    return (
      <ArtifactStatusShell
        title="Artifact not found"
        description="This saved artifact is not present in the current Pages index."
        tone="error"
      />
    );
  }

  if (metaStatus === "missing") {
    return (
      <ArtifactStatusShell
        title="Artifact not found"
        description="This saved artifact is not present in the current Pages index."
        tone="error"
      />
    );
  }

  // Once the skeleton (or real meta) is ready, render ArtifactChrome
  // unconditionally — the iframe is the critical-path render.
  if (artifact) {
    if (iframeState.status === "error") {
      const warming = elapsedSec >= REASSURE_AFTER_MS / 1000;
      return (
        <ArtifactStatusShell
          title="Artifact failed to open"
          description={
            warming
              ? `${iframeState.message} (${elapsedSec}s)`
              : iframeState.message
          }
          tone="error"
          action={
            <button
              type="button"
              onClick={retry}
              className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              <RefreshCw className="size-3.5" />
              Retry
            </button>
          }
        />
      );
    }

    return (
      <ArtifactChrome
        key={reload}
        artifact={artifact}
        rawSrc={`/api/artifact/${encodeURIComponent(normalized)}/raw`}
        onIframeLoad={handleIframeLoad}
        onIframeError={handleIframeError}
      />
    );
  }

  // Should not be reached for a valid slug, but keep a brief loading shell
  // in case the skeleton effect hasn't fired yet (first render tick).
  return (
    <ArtifactStatusShell
      title="Opening artifact"
      description="Loading artifact…"
    />
  );
}
