import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";
import type { ColorScheme } from "./glassCardStyles";

interface DefaultHeaderContentProps {
  Icon?: LucideIcon;
  title?: string;
  subtitle?: string;
  scheme: ColorScheme;
}

export function DefaultHeaderContent({
  Icon,
  title,
  subtitle,
  scheme,
}: DefaultHeaderContentProps) {
  return (
    <div className="flex items-center gap-3">
      {Icon && (
        <div
          className={cn(
            "p-2.5 rounded-xl bg-gradient-to-br shadow-sm",
            scheme.gradient,
          )}
        >
          <Icon className="size-5 text-white" />
        </div>
      )}
      {(title || subtitle) && (
        <div>
          {title && (
            <h3 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
              {title}
            </h3>
          )}
          {subtitle && (
            <p className="text-sm text-[var(--text-secondary)]">{subtitle}</p>
          )}
        </div>
      )}
    </div>
  );
}
