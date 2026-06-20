"use client";

import * as React from "react";
import Link from "next/link";
import { LayoutDashboard } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TabItem } from "@/lib/tabs/types";
import { resolveIcon } from "@/lib/icon-map";
import { cn } from "@/lib/utils";

interface TabIconProps {
  icon: string | LucideIcon | React.ReactNode | undefined;
  className: string;
}

export function TabIcon({ icon, className }: TabIconProps) {
  if (!icon) return null;
  if (typeof icon === "string") {
    return React.createElement(resolveIcon(icon, LayoutDashboard), { className });
  }
  if (typeof icon === "function") {
    return React.createElement(icon as LucideIcon, { className });
  }
  if (React.isValidElement(icon)) {
    return React.cloneElement(
      icon as React.ReactElement<{ className?: string }>,
      { className },
    );
  }
  return null;
}

interface TabLinkProps {
  tab: TabItem;
  active: boolean;
}

export function TabLink({ tab, active }: TabLinkProps) {
  const iconClass = cn(
    "size-4 transition-colors duration-200",
    active
      ? "text-[var(--accent-primary)]"
      : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]",
  );

  return (
    <Link
      href={tab.href || "#"}
      prefetch={false}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex min-h-[44px] items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200 whitespace-nowrap",
        active
          ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
      )}
    >
      <TabIcon icon={tab.icon} className={iconClass} />
      <span>{tab.label}</span>
      {tab.badge != null && (
        <span className="ml-1 min-w-[18px] h-[18px] flex items-center justify-center text-[10px] font-semibold rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1">
          {tab.badge}
        </span>
      )}
      {active && (
        <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-6 h-0.5 bg-[var(--accent-primary)] rounded-full" />
      )}
    </Link>
  );
}
