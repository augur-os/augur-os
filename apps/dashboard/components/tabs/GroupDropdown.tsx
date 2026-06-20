"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import type { TabItem, TabEntry } from "@/lib/tabs/types";
import { TabIcon, TabLink } from "./TabLink";
import React, { useRef, useState, useEffect } from "react";

export function GroupDropdown({
  group,
  isTabActive,
}: {
  group: TabEntry & { children: TabItem[] };
  isTabActive: (tab: TabItem) => boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const isActive = group.children.some(isTabActive);

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <div className="flex items-center">
        <Link
          href={group.href || "#"}
          prefetch={false}
          className={cn(
            "group relative flex items-center gap-2 pl-4 pr-1 py-2.5 rounded-l-xl text-sm font-medium transition-all duration-200 whitespace-nowrap",
            isActive
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
          )}
        >
          <TabIcon
            icon={group.icon}
            className={cn(
              "w-4 h-4 transition-colors duration-200",
              isActive
                ? "text-[var(--accent-primary)]"
                : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]",
            )}
          />
          <span>{group.label}</span>
          {isActive && (
            <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-6 h-0.5 bg-[var(--accent-primary)] rounded-full" />
          )}
        </Link>
        <button type="button"
          onClick={() => setOpen((o) => !o)}
          aria-label={`${open ? 'Close' : 'Open'} ${group.label} submenu`}
          aria-expanded={open}
          className={cn(
            "flex items-center pr-3 pl-1 py-2.5 rounded-r-xl text-sm transition-all duration-200",
            isActive
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
          )}
        >
          <ChevronDown
            className={cn(
              "w-3.5 h-3.5 transition-transform",
              open && "rotate-180",
            )}
          />
        </button>
      </div>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[180px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-lg p-1">
          {group.children.map((child) => (
            <div
              key={child.href || child.id}
              role="presentation"
              onClick={() => setOpen(false)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  setOpen(false);
                }
              }}
            >
              <TabLink tab={child} active={isTabActive(child)} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
