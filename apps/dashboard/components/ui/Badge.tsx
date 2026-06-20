import type * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.ComponentPropsWithRef<"span"> {
  variant?: "default" | "success" | "outline" | "destructive";
  size?: "sm" | "md";
}

const BADGE_VARIANT_STYLES = {
  default:
    "bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-color)]",
  success:
    "bg-[var(--accent-success)]/10 text-[var(--accent-success)] border-[var(--accent-success)]/20",
  destructive:
    "bg-[var(--accent-danger)]/10 text-[var(--accent-danger)] border-[var(--accent-danger)]/20",
  outline:
    "bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-color)]",
} as const;

const BADGE_SIZE_STYLES = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
} as const;

function Badge({ className, variant = "default", size = "sm", ref, ...props }: BadgeProps) {
  return (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center rounded uppercase font-bold tracking-wider border transition-colors",
        BADGE_VARIANT_STYLES[variant],
        BADGE_SIZE_STYLES[size],
        className,
      )}
      {...props}
    />
  );
}

export { Badge };
