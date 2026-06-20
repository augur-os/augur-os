import type * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.ComponentPropsWithRef<"input">;

function Input({ className, type, ref, ...props }: InputProps) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)] disabled:cursor-not-allowed disabled:opacity-50 text-[var(--text-primary)]",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
}

export { Input };
