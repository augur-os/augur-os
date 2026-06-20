"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";
import { normalizeArtifactSlug } from "@/lib/artifacts/slug";
import type { ArtifactEntry } from "@/lib/browse/pages-merge";
import { mcpCall } from "@/lib/mcp/client";
import { ArtifactChrome } from "./ArtifactChrome";

interface ArtifactsListResponse {
  artifacts?: ArtifactEntry[];
}

type ArtifactRouteState =
  | { status: "idle" }
  | { status: "ready"; slug: string; artifact: ArtifactEntry }
  | { status: "missing"; slug: string }
  | { status: "error"; slug: string; message: string };

type CurrentArtifactRouteState = ArtifactRouteState | { status: "loading" };

function ArtifactStatusShell({
  title,
  description,
  tone = "neutral",
}: {
  title: string;
  description: string;
  tone?: "neutral" | "error";
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
        </div>
      </section>
    </main>
  );
}

export function ArtifactRouteClient({ slug }: { slug: string }) {
  const normalized = useMemo(() => normalizeArtifactSlug(slug), [slug]);
  const [state, setState] = useState<ArtifactRouteState>({ status: "idle" });

  useEffect(() => {
    if (!normalized) {
      return undefined;
    }

    const controller = new AbortController();
    void mcpCall<ArtifactsListResponse>("artifacts-list", {}, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        const artifact = Array.isArray(data.artifacts)
          ? data.artifacts.find((entry) => entry.slug === normalized)
          : undefined;
        setState(artifact ? { status: "ready", slug: normalized, artifact } : { status: "missing", slug: normalized });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Artifact metadata failed to load";
        setState({ status: "error", slug: normalized, message });
      });

    return () => controller.abort();
  }, [normalized]);

  if (!normalized) {
    return (
      <ArtifactStatusShell
        title="Artifact not found"
        description="This saved artifact is not present in the current Pages index."
        tone="error"
      />
    );
  }

  const currentState: CurrentArtifactRouteState =
    state.status !== "idle" && "slug" in state && state.slug === normalized
      ? state
      : { status: "loading" };

  if (currentState.status === "ready") {
    return (
      <ArtifactChrome
        artifact={currentState.artifact}
        rawSrc={`/api/artifact/${encodeURIComponent(currentState.artifact.slug)}/raw`}
      />
    );
  }

  if (currentState.status === "missing") {
    return (
      <ArtifactStatusShell
        title="Artifact not found"
        description="This saved artifact is not present in the current Pages index."
        tone="error"
      />
    );
  }

  if (currentState.status === "error") {
    return (
      <ArtifactStatusShell
        title="Artifact failed to open"
        description={currentState.message}
        tone="error"
      />
    );
  }

  return (
    <ArtifactStatusShell
      title="Opening artifact"
      description="Loading artifact metadata from the dashboard MCP bridge."
    />
  );
}
