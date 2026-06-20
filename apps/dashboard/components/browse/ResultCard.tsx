"use client";

import { Copy, ArrowRight } from "lucide-react";

import Markdown from "@/components/Markdown";
import { Button } from "@/components/ui/Button";
import type { PromptResult } from "@/lib/browse/types";

interface ResultCardProps {
  result: PromptResult;
  onContinueInSession: (sessionId: string) => void;
  basePath?: string;
}

export function ResultCard({
  result,
  onContinueInSession,
  basePath = "/",
}: ResultCardProps) {
  const sessionId = result.sessionId.trim();

  const handleCopy = () => {
    void navigator.clipboard.writeText(result.answer);
  };

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {result.promptId}
          </h3>
          <p className="mt-1 text-xs text-[var(--text-muted)] flex items-center gap-2">
            <span>{formatDuration(result.durationMs)}</span>
            <span aria-hidden="true">•</span>
            <span>{result.cliId}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={handleCopy}
            aria-label="Copy result"
            title="Copy result"
          >
            <Copy className="size-4" aria-hidden="true" />
          </Button>

          {sessionId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onContinueInSession(sessionId)}
              leftIcon={<ArrowRight className="size-4" aria-hidden="true" />}
            >
              Continue in session
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-4">
        <Markdown markdown={result.answer} basePath={basePath} />
      </div>
    </article>
  );
}

function formatDuration(durationMs: number): string {
  if (durationMs < 1000) {
    return `${Math.max(0, Math.round(durationMs))}ms`;
  }

  const seconds = durationMs / 1000;
  if (Number.isInteger(seconds)) {
    return `${seconds}s`;
  }

  return `${seconds.toFixed(2).replace(/\.?0+$/, "")}s`;
}

export default ResultCard;
