import type * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps extends React.ComponentPropsWithRef<"select"> {
  variant?: "default" | "outline" | "ghost";
}

function Select({ className, variant: _variant = "default", ref, ...props }: SelectProps) {
  return (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] shadow-sm placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)] disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    </div>
  );
}

export { Select };
