"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FolderOpen, Pin, PinOff } from "lucide-react";
import { toast } from "sonner";
import { mcpCall } from "@/lib/mcp/client";
import type { ArtifactEntry } from "@/lib/browse/pages-merge";
import { useChatStore } from "@/lib/stores/chatStore";
import { useActionRunner } from "@/hooks/useActionRunner";
import { handleArtifactMessage } from "@/lib/artifacts/bridge";
import type { ActionDef } from "@/lib/actions/types";

interface PinListResponse {
  pins?: Array<{ url?: string }>;
}

interface PinMutationResponse {
  added?: boolean;
  removed?: boolean;
  error?: string;
}

function kindClass(kind: ArtifactEntry["kind"]) {
  return kind === "saved"
    ? "border-sky-500/25 bg-sky-500/10 text-sky-500"
    : "border-amber-500/25 bg-amber-500/10 text-amber-500";
}

export function ArtifactChrome({
  artifact,
  rawSrc,
}: {
  artifact: ArtifactEntry;
  rawSrc: string;
}) {
  const [pinned, setPinned] = useState(false);
  const [pinning, setPinning] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const openChat = useChatStore((s) => s.openChat);
  const { runAction } = useActionRunner();

  // ADR-808: constrained HTML→AI bridge. The artifact iframe runs at an opaque
  // origin (no allow-same-origin), so postMessage is the only channel; the
  // injected window.augur shim is the sole API. ask() opens chat (human-
  // confirmed); runAction() dispatches a DECLARED action of the owning skill
  // only — undefined skill → runAction disabled.
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      void handleArtifactMessage(event, {
        slug: artifact.slug,
        ownerSkill: artifact.skill,
        expectedSource: iframeRef.current?.contentWindow ?? null,
        openChat: (p) =>
          openChat({
            mode: p.mode as "ide",
            initialPrompt: p.initialPrompt,
            draft: p.draft,
            context: p.context,
          }),
        listSkillActions: (skillId) =>
          mcpCall<{ actions: Array<{ id: string } & Record<string, unknown>> }>(
            "list-skill-actions",
            { skill_id: skillId },
          ),
        runAction: async (action) => {
          await runAction(action as unknown as ActionDef);
        },
      });
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [artifact.slug, artifact.skill, openChat, runAction]);

  useEffect(() => {
    let alive = true;
    void mcpCall<PinListResponse>("pin-list", {}, { fallback: { pins: [] } })
      .then((data) => {
        if (alive) {
          setPinned(Boolean(data.pins?.some((pin) => pin.url === artifact.url)));
        }
      });
    return () => {
      alive = false;
    };
  }, [artifact.url]);

  const togglePin = async () => {
    setPinning(true);
    try {
      const result = pinned
        ? await mcpCall<PinMutationResponse>("pin-remove", { url: artifact.url })
        : await mcpCall<PinMutationResponse>("pin-add", {
            url: artifact.url,
            title: artifact.title,
            kind: artifact.kind,
            hub: artifact.hub,
          });
      if (result.error) throw new Error(result.error);
      setPinned(!pinned);
      toast.success(pinned ? "Removed pin" : "Pinned");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Pin update failed");
    } finally {
      setPinning(false);
    }
  };

  const revealSource = async () => {
    try {
      const result = await mcpCall<{ success?: boolean; error?: string }>(
        "reveal-in-finder",
        { path: artifact.path },
      );
      if (result.error || result.success === false) {
        throw new Error(result.error || "Reveal failed");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reveal failed");
    }
  };

  return (
    <main className="flex min-h-[100dvh] flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <header className="shrink-0 border-b border-[var(--border-color)] bg-[var(--bg-card)]/90 px-4 py-3 backdrop-blur">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
              <Link
                href="/browse?category=pages"
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 py-1.5 font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
              >
                <ArrowLeft className="size-3.5" />
                Pages
              </Link>
              <span className={`rounded-full border px-2 py-0.5 font-semibold uppercase tracking-[0.12em] ${kindClass(artifact.kind)}`}>
                {artifact.kind}
              </span>
              <span className="rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-0.5 font-medium uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                {artifact.hub}
              </span>
            </div>
            <h1 className="truncate text-lg font-semibold leading-6 tracking-tight">
              {artifact.title}
            </h1>
            <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">
              {artifact.path}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={togglePin}
              disabled={pinning}
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              {pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
              {pinned ? "Unpin" : "Pin"}
            </button>
            <button
              type="button"
              onClick={revealSource}
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              <FolderOpen className="size-4" />
              Source
            </button>
            <a
              href={rawSrc}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              <ExternalLink className="size-4" />
              Raw
            </a>
          </div>
        </div>
      </header>
      <iframe
        ref={iframeRef}
        title={artifact.title}
        src={rawSrc}
        sandbox="allow-downloads allow-forms allow-modals allow-popups allow-scripts"
        referrerPolicy="no-referrer"
        className="min-h-0 flex-1 border-0 bg-white"
      />
    </main>
  );
}
