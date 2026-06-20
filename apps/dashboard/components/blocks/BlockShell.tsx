"use client";

import type { LucideIcon } from "lucide-react";
import { ExternalLink } from "lucide-react";
import { StaleDataBadge } from "./StaleDataBadge";

type BlockColor =
  | "cyan"
  | "purple"
  | "emerald"
  | "amber"
  | "blue"
  | "rose"
  | "violet"
  | "pink";

const COLOR_MAP: Record<
  BlockColor,
  { border: string; gradient: string; glow: string }
> = {
  cyan: {
    border: "border-cyan-500/20 hover:border-cyan-500/40",
    gradient: "from-cyan-500 to-blue-500",
    glow: "group-hover:shadow-cyan-500/10",
  },
  purple: {
    border: "border-purple-500/20 hover:border-purple-500/40",
    gradient: "from-purple-500 to-pink-500",
    glow: "group-hover:shadow-purple-500/10",
  },
  emerald: {
    border: "border-emerald-500/20 hover:border-emerald-500/40",
    gradient: "from-emerald-500 to-teal-500",
    glow: "group-hover:shadow-emerald-500/10",
  },
  amber: {
    border: "border-amber-500/20 hover:border-amber-500/40",
    gradient: "from-amber-500 to-orange-500",
    glow: "group-hover:shadow-amber-500/10",
  },
  blue: {
    border: "border-blue-500/20 hover:border-blue-500/40",
    gradient: "from-blue-500 to-indigo-500",
    glow: "group-hover:shadow-blue-500/10",
  },
  rose: {
    border: "border-rose-500/20 hover:border-rose-500/40",
    gradient: "from-rose-500 to-pink-500",
    glow: "group-hover:shadow-rose-500/10",
  },
  violet: {
    border: "border-violet-500/20 hover:border-violet-500/40",
    gradient: "from-violet-500 to-purple-500",
    glow: "group-hover:shadow-violet-500/10",
  },
  pink: {
    border: "border-pink-500/20 hover:border-pink-500/40",
    gradient: "from-pink-500 to-rose-500",
    glow: "group-hover:shadow-pink-500/10",
  },
};

interface BlockShellProps {
  title: string;
  icon: LucideIcon;
  color?: BlockColor;
  onExpand?: () => void;
  expandLabel?: string;
  staleError?: string | null;
  children: React.ReactNode;
}

export function BlockShell({
  title,
  icon: Icon,
  color = "cyan",
  onExpand,
  expandLabel = "Open",
  staleError,
  children,
}: BlockShellProps) {
  const scheme = COLOR_MAP[color];

  return (
    <section
      aria-label={title}
      className={`group relative h-full flex flex-col rounded-2xl border bg-[var(--bg-card)] shadow-sm overflow-hidden transition-all duration-300 ${scheme.border} ${scheme.glow}`}
    >
      {/* Shine line */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 flex items-center gap-2.5 px-4 py-3 border-b border-[var(--border-color)]/50">
        <div
          className={`p-1.5 rounded-lg bg-gradient-to-br ${scheme.gradient}`}
        >
          <Icon className="size-3.5 text-white" aria-hidden="true" />
        </div>
        <h3
          className="text-sm font-semibold text-[var(--text-primary)] flex-1"
        >
          {title}
        </h3>
        {staleError && <StaleDataBadge error={staleError} />}
        {onExpand && (
          <button type="button"
            onClick={onExpand}
            aria-label={`${expandLabel} ${title}`}
            className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-[var(--accent-primary)] transition-colors"
          >
            {expandLabel}
            <ExternalLink className="size-3" aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Body */}
      <div aria-live="polite" className="relative z-10 flex-1 overflow-auto">
        {children}
      </div>
    </section>
  );
}
