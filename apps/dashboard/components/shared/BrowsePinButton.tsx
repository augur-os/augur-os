"use client";

import { Pin } from "lucide-react";

interface BrowsePinButtonProps {
  title: string;
  pinned: boolean;
  onToggle: () => void;
  className?: string;
}

export function BrowsePinButton({ title, pinned, onToggle, className = "" }: BrowsePinButtonProps) {
  return (
    <button
      type="button"
      aria-label={`${pinned ? "Unpin" : "Pin"} ${title}`}
      aria-pressed={pinned}
      title={pinned ? "Unpin" : "Pin"}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
          event.stopPropagation();
        }
      }}
      className={`inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
        pinned
          ? "border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
          : "border-[var(--border-color)] bg-[var(--bg-primary)]/70 text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      } ${className}`}
    >
      <Pin className="size-4" />
    </button>
  );
}
